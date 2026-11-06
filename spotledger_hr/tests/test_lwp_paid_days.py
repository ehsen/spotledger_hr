"""Native Leave Without Pay honoured by CustomSalarySlip._paid_days().

Synthetic fixtures only; run on the bfi dev site (rolled back after each test).
July 2026: Wed 1st; Fridays 3/10/17/24/31; Sundays 5/12/19/26; 31 days.
"""
import unittest

import frappe

from spotledger_hr.tests import test_friday_absence_policy as fixtures


class TestLeaveWithoutPayPaidDays(unittest.TestCase):
    setUp = fixtures.TestFridayAbsencePolicy.setUp
    tearDown = fixtures.TestFridayAbsencePolicy.tearDown
    attendance = fixtures.TestFridayAbsencePolicy.attendance
    change_rule = fixtures.TestFridayAbsencePolicy.change_rule

    def leave_type(self, name, is_lwp):
        if not frappe.db.exists('Leave Type', name):
            frappe.get_doc(dict(doctype='Leave Type', leave_type_name=name, is_lwp=is_lwp, include_holiday=1)).insert()
        return name

    def leave(self, date, leave_type='_LWP Test', docstatus=1, is_lwp=1):
        self.leave_type(leave_type, is_lwp)
        doc = frappe.get_doc(dict(doctype='Attendance', name=frappe.generate_hash(length=12), employee=self.employee,
                                  attendance_date=date, status='On Leave', leave_type=leave_type,
                                  docstatus=docstatus, company=self.company))
        doc.db_insert()
        return doc.name

    def relocate(self, **values):
        frappe.db.set_value('Employee', self.employee, values)
        frappe.clear_document_cache('Employee', self.employee)

    # -- regression ----------------------------------------------------

    def test_no_lwp_is_identical_to_today(self):
        self.attendance('2026-07-06')
        self.attendance('2026-07-05')  # Sunday stays paid
        self.assertEqual(self.slip._paid_days(), 30)
        self.assertEqual(self.slip._lwp_days(), 0)

    # -- any weekday ---------------------------------------------------

    def test_lwp_on_weekday_sunday_friday_and_holiday(self):
        for date, expected in [('2026-07-07', 30), ('2026-07-05', 30), ('2026-07-03', 30), ('2026-07-14', 30)]:
            with self.subTest(date=date):
                frappe.db.delete('Attendance', {'employee': self.employee})
                self.leave(date)
                self.assertEqual(self.slip._paid_days(), expected)
                self.assertEqual(self.slip._lwp_days(), 1)

    def test_lwp_friday_gives_no_credit_and_no_deficiency(self):
        self.leave('2026-07-03')
        self.assertEqual(self.slip._paid_days(), 30)
        self.assertEqual(self.slip._deficiency_hours(), 0)
        # contrast: an Absent Friday is credited back but charged 5.5h
        frappe.db.delete('Attendance', {'employee': self.employee})
        self.attendance('2026-07-03')
        self.assertEqual(self.slip._paid_days(), 31)
        self.assertEqual(self.slip._deficiency_hours(), 5.5)

    def test_range_with_sundays_and_fridays_is_fully_unpaid(self):
        # 2-20 July: 19 days including Fridays 3/10/17 and Sundays 5/12/19
        for day in range(2, 21):
            self.leave('2026-07-%02d' % day)
        self.assertEqual(self.slip._lwp_days(), 19)
        self.assertEqual(self.slip._paid_days(), 12)
        self.assertEqual(self.slip._deficiency_hours(), 0)

    # -- combination ---------------------------------------------------

    def test_absent_and_lwp_on_different_dates_both_deducted(self):
        self.attendance('2026-07-06')
        self.leave('2026-07-07')
        self.assertEqual(self.slip._paid_days(), 29)

    def test_same_date_counted_once(self):
        self.leave('2026-07-07')
        self.leave('2026-07-07')  # duplicate rows still one date
        self.assertEqual(self.slip._paid_days(), 30)

    def test_paid_leave_type_is_not_subtracted(self):
        self.leave('2026-07-07', leave_type='_Paid Test', is_lwp=0)
        self.assertEqual(self.slip._paid_days(), 31)
        self.assertEqual(self.slip._lwp_days(), 0)

    def test_draft_and_cancelled_lwp_ignored(self):
        self.leave('2026-07-07', docstatus=0)
        self.leave('2026-07-08', docstatus=2)
        self.assertEqual(self.slip._paid_days(), 31)

    def test_floor_at_zero(self):
        for day in range(1, 32):
            self.leave('2026-07-%02d' % day)
        self.attendance('2026-07-06')
        self.assertEqual(self.slip._paid_days(), 0)

    # -- window --------------------------------------------------------

    def test_lwp_outside_period_has_no_effect(self):
        self.leave('2026-06-30')
        self.leave('2026-08-01')
        self.assertEqual(self.slip._paid_days(), 31)
        self.assertEqual(self.slip._lwp_days(), 0)

    def test_joining_mid_month(self):
        self.relocate(date_of_joining='2026-07-11')
        self.slip = fixtures.CustomSalarySlip(dict(doctype='Salary Slip', employee=self.employee, start_date='2026-07-01', end_date='2026-07-31'))
        self.leave('2026-07-05')  # before joining: ignored
        self.assertEqual(self.slip._paid_days(), 21)
        self.leave('2026-07-15')
        self.assertEqual(self.slip._paid_days(), 20)

    def test_relieving_mid_month(self):
        self.relocate(relieving_date='2026-07-18')
        self.leave('2026-07-20')  # after relieving: ignored
        self.assertEqual(self.slip._paid_days(), 18)
        self.leave('2026-07-10')
        self.assertEqual(self.slip._paid_days(), 17)

    # -- slip level ----------------------------------------------------

    def test_native_payroll_entry_flat_formula_with_lwp(self):
        """Payroll Entry -> create_salary_slips picks the leave up and sets
        the slip's leave_without_pay; Attendance rows are left untouched."""
        self.attendance('2026-07-06')   # absent weekday
        self.leave('2026-07-03')        # Friday LWP
        self.leave('2026-07-05')        # Sunday LWP
        formulas = [('LW Gross', 'Earning', 'round(base / days_in_month() * paid_days())'),
                    ('LW Deficiency', 'Deduction', 'round(deficiency_hours() * hourly_rate())')]
        structure = frappe.get_doc(dict(doctype='Salary Structure', name='_LWP Test Wages', company=self.company, currency='PKR', payroll_frequency='Monthly', is_active='Yes'))
        for index, (name, kind, formula) in enumerate(formulas):
            frappe.get_doc(dict(doctype='Salary Component', salary_component=name, salary_component_abbr='LW' + str(index), type=kind, depends_on_payment_days=0)).insert()
            structure.append('earnings' if kind == 'Earning' else 'deductions', dict(salary_component=name, amount_based_on_formula=1, formula=formula, depends_on_payment_days=0))
        structure.insert().submit()
        if not frappe.db.exists('Fiscal Year', {'year_start_date': ['<=', '2026-07-01'], 'year_end_date': ['>=', '2026-07-31'], 'disabled': 0}):
            frappe.get_doc(dict(doctype='Fiscal Year', year='_LWP 2026', year_start_date='2026-01-01', year_end_date='2026-12-31')).insert()
        frappe.get_doc(dict(doctype='Salary Structure Assignment', employee=self.employee, company=self.company, salary_structure=structure.name, from_date='2026-07-01', base=23000, currency='PKR')).insert().submit()
        holiday = frappe.get_doc(dict(doctype='Holiday List', holiday_list_name='_LWP Holidays', from_date='2026-01-01', to_date='2026-12-31', holidays=[dict(holiday_date='2026-07-05', description='Sunday', weekly_off=1)])).insert()
        frappe.get_doc(dict(doctype='Holiday List Assignment', applicable_for='Company', assigned_to=self.company, holiday_list=holiday.name, from_date='2026-01-01')).insert().submit()
        before = frappe.get_all('Attendance', filters={'employee': self.employee}, fields=['*'])
        pe = frappe.get_doc(dict(doctype='Payroll Entry', company=self.company, currency='PKR', exchange_rate=1, payroll_frequency='Monthly', start_date='2026-07-01', end_date='2026-07-31', posting_date='2026-07-31', cost_center='Main - FPT', payroll_payable_account=frappe.db.get_value('Company', self.company, 'default_payroll_payable_account'), employees=[dict(employee=self.employee)]))
        pe.insert()
        pe.create_salary_slips()
        names = frappe.get_all('Salary Slip', filters={'payroll_entry': pe.name}, pluck='name')
        self.assertEqual(len(names), 1, pe.error_message)
        slip = frappe.get_doc('Salary Slip', names[0])
        self.assertEqual((slip.payment_days, slip.leave_without_pay), (28, 2))
        amounts = {row.salary_component: row.amount for row in slip.earnings + slip.deductions}
        # zero-amount deduction is not materialised: no Friday deficiency
        self.assertEqual(amounts, {'LW Gross': round(23000 / 31 * 28)})
        slip.save()
        self.assertEqual((slip.payment_days, slip.leave_without_pay), (28, 2))
        self.assertEqual(before, frappe.get_all('Attendance', filters={'employee': self.employee}, fields=['*']))

    # -- native Leave Application flow ---------------------------------

    def application(self, from_date, to_date, leave_type='Leave Without Pay'):
        self.leave_type(leave_type, 1)
        if not frappe.db.exists('Holiday List', '_LWP App Holidays'):
            holiday = frappe.get_doc(dict(doctype='Holiday List', holiday_list_name='_LWP App Holidays', from_date='2026-01-01', to_date='2026-12-31', holidays=[
                dict(holiday_date='2026-07-05', description='Sunday', weekly_off=1),
                dict(holiday_date='2026-07-14', description='Gazetted')])).insert()
            frappe.get_doc(dict(doctype='Holiday List Assignment', applicable_for='Company', assigned_to=self.company, holiday_list=holiday.name, from_date='2026-01-01')).insert().submit()
        return frappe.get_doc(dict(doctype='Leave Application', employee=self.employee, company=self.company, leave_type=leave_type,
                                   from_date=from_date, to_date=to_date, status='Approved', leave_approver='Administrator', posting_date='2026-07-31'))

    def test_leave_application_over_sunday_and_gazetted_holiday(self):
        for from_date, to_date in [('2026-07-05', '2026-07-05'), ('2026-07-14', '2026-07-14'), ('2026-07-03', '2026-07-06')]:
            with self.subTest(from_date=from_date):
                frappe.db.delete('Attendance', {'employee': self.employee})
                frappe.db.delete('Leave Application', {'employee': self.employee})
                app = self.application(from_date, to_date)
                app.insert()
                app.submit()
                rows = frappe.get_all('Attendance', filters={'employee': self.employee, 'docstatus': 1}, fields=['attendance_date', 'status', 'leave_type'])
                days = (frappe.utils.getdate(to_date) - frappe.utils.getdate(from_date)).days + 1
                self.assertEqual(len(rows), days)
                self.assertTrue(all(r.status == 'On Leave' and r.leave_type == 'Leave Without Pay' for r in rows))
                self.assertEqual(self.slip._lwp_days(), days)
                self.assertEqual(self.slip._paid_days(), 31 - days)

    def test_leave_application_rejected_over_present_attendance(self):
        self.attendance('2026-07-07', 'Present')
        with self.assertRaises(frappe.ValidationError) as ctx:
            self.application('2026-07-07', '2026-07-07').insert().submit()
        self.assertIn('Attendance', str(ctx.exception))
        self.assertIn('already marked', str(ctx.exception))


def run():
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TestLeaveWithoutPayPaidDays))
    if not result.wasSuccessful():
        raise AssertionError('LWP paid days tests failed')
