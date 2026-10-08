"""Synthetic fixtures only; execute exclusively on an isolated test site."""
import unittest
import frappe
from spotledger_hr.controllers.salary_slip_controller import CustomSalarySlip


class TestFridayAbsencePolicy(unittest.TestCase):
    def setUp(self):
        assert frappe.local.site == 'friday-policy-test.local', 'Isolated site required'
        frappe.flags.in_test = True
        frappe.in_test = True
        if not frappe.db.exists('Warehouse Type', 'Transit'):
            frappe.get_doc(dict(doctype='Warehouse Type', name='Transit')).insert()
        if not frappe.db.exists('Gender', 'Male'):
            frappe.get_doc(dict(doctype='Gender', gender='Male')).insert()
        self.company = '_Friday Policy Test'
        if not frappe.db.exists('Company', self.company):
            frappe.get_doc(dict(doctype='Company', company_name=self.company, abbr='FPT', default_currency='PKR', country='Pakistan')).insert()
        self.rule = frappe.get_doc(dict(doctype='Attendance Rule', name='_Friday Test Rule', company=self.company, factory_start_time='08:00:00', factory_end_time='17:00:00', wage_rate_hours=8.5, required_factory_hours=8.5, break_duration_minutes=30, overtime_multiplier=1.5, friday_absence_deficiency_hours=5.5, friday_absence_policy_from_date='2026-07-01')).insert()
        self.employee = frappe.get_doc(dict(doctype='Employee', first_name='Synthetic Friday Worker', custom_father_name='Synthetic Parent', gender='Male', date_of_birth='1990-01-01', date_of_joining='2026-01-01', company=self.company, custom_attendance_rule=self.rule.name)).insert().name
        self.slip = CustomSalarySlip(dict(doctype='Salary Slip', employee=self.employee, start_date='2026-07-01', end_date='2026-07-31'))

    def tearDown(self):
        frappe.db.rollback()
        frappe.clear_cache()

    def attendance(self, date, status='Absent', docstatus=1, deficiency=0, overtime=0):
        # Raw synthetic rows intentionally exercise duplicate/cancelled corruption
        # without weakening production Attendance validation.
        doc = frappe.get_doc(dict(doctype='Attendance', name=frappe.generate_hash(length=12), employee=self.employee, attendance_date=date, status=status, docstatus=docstatus, company=self.company, custom_deficiency_hours=deficiency, custom_overtime_hours=overtime))
        doc.db_insert()
        return doc.name

    def change_rule(self, **values):
        self.rule.update(values)
        self.rule.save()
        frappe.clear_document_cache('Attendance Rule', self.rule.name)

    def test_default_off_and_missing_employee_rule(self):
        self.attendance('2026-07-03')
        self.change_rule(friday_absence_deficiency_hours=0, friday_absence_policy_from_date=None)
        self.assertEqual((self.slip._paid_days(), self.slip._deficiency_hours()), (30, 0))
        frappe.db.set_value('Employee', self.employee, 'custom_attendance_rule', None)
        frappe.clear_document_cache('Employee', self.employee)
        self.assertEqual((self.slip._paid_days(), self.slip._deficiency_hours()), (30, 0))

    def test_distinct_dates_boundaries_statuses_and_idempotency(self):
        self.change_rule(friday_absence_policy_from_date='2026-07-10')
        for date in ['2026-06-26','2026-07-03','2026-07-10','2026-07-10','2026-07-31','2026-08-07']:
            self.attendance(date, deficiency=99)
        self.attendance('2026-07-17', docstatus=0)
        self.attendance('2026-07-24', docstatus=2)
        self.attendance('2026-07-24', 'Present', deficiency=1.35)
        self.attendance('2026-07-05')  # Sunday stays paid
        self.attendance('2026-07-04')  # Saturday stays unpaid
        self.attendance('2026-07-06')  # weekday stays unpaid
        self.attendance('2026-07-17', 'Half Day')
        self.attendance('2026-07-24', 'On Leave')
        before = frappe.get_all('Attendance', filters={'employee': self.employee}, fields=['*'])
        for _ in range(3):
            self.assertEqual(self.slip._paid_days(), 28)
            self.assertAlmostEqual(self.slip._deficiency_hours(), 12.35)
        self.assertEqual(before, frappe.get_all('Attendance', filters={'employee': self.employee}, fields=['*']))
        self.slip.start_date, self.slip.end_date = '2026-08-01', '2026-08-31'
        self.assertEqual((self.slip._paid_days(), self.slip._deficiency_hours()), (31, 5.5))

    def test_driver_and_trainee_rules_do_not_inherit_policy(self):
        self.attendance('2026-07-03')
        for name in ['Synthetic Driver', 'Synthetic Trainee']:
            rule = frappe.copy_doc(self.rule)
            rule.name = name
            rule.friday_absence_deficiency_hours = 0
            rule.overtime_multiplier = 0
            rule.insert()
            frappe.db.set_value('Employee', self.employee, 'custom_attendance_rule', rule.name)
            frappe.clear_document_cache('Employee', self.employee)
            self.assertEqual((self.slip._paid_days(), self.slip._deficiency_hours()), (30, 0))
            self.assertEqual(self.slip._overtime_multiplier(), 0)
        self.assertEqual(self.slip._required_hours(), 8)

    def test_native_payroll_entry_generation(self):
        friday = self.attendance('2026-07-03')
        for date in ['2026-07-04', '2026-07-06', '2026-07-07']:
            self.attendance(date)
        self.attendance('2026-07-25', 'Present', deficiency=1.35, overtime=15)
        before = frappe.get_all('Attendance', filters={'employee': self.employee}, fields=['*'])
        formulas = [('FP Gross','Earning','round(base / days_in_month() * paid_days())'),
                    ('FP Overtime','Earning','round(overtime_hours() * hourly_rate() * overtime_multiplier())'),
                    ('FP Deficiency','Deduction','round(deficiency_hours() * hourly_rate())'),
                    ('FP Advance','Deduction','round(pending_advance())')]
        structure = frappe.get_doc(dict(doctype='Salary Structure', name='_Friday Test Wages', company=self.company, currency='PKR', payroll_frequency='Monthly', is_active='Yes'))
        for index, (name, kind, formula) in enumerate(formulas):
            frappe.get_doc(dict(doctype='Salary Component', salary_component=name, salary_component_abbr='FP'+str(index), type=kind, depends_on_payment_days=0)).insert()
            structure.append('earnings' if kind=='Earning' else 'deductions', dict(salary_component=name, amount_based_on_formula=1, formula=formula, depends_on_payment_days=0))
        structure.insert().submit()
        if not frappe.db.exists('Fiscal Year', '_Friday 2026'):
            frappe.get_doc(dict(doctype='Fiscal Year', year='_Friday 2026', year_start_date='2026-01-01', year_end_date='2026-12-31')).insert()
        assignment = frappe.get_doc(dict(doctype='Salary Structure Assignment', employee=self.employee, company=self.company, salary_structure=structure.name, from_date='2026-07-01', base=23000, currency='PKR')).insert()
        assignment.submit()
        preview = assignment._get_component_eval_context()
        self.assertEqual(preview['deficiency_hours'](), 0)
        self.assertEqual(preview['pending_advance'](), 0)
        self.assertEqual(preview['paid_days'](), preview.payment_days)
        advance = frappe.get_doc(dict(doctype='Employee Advance Deduction', name='_Friday Synthetic Advance', employee=self.employee, posting_date='2026-07-01', deduction_amount=7000, docstatus=1))
        advance.db_insert()
        holiday = frappe.get_doc(dict(doctype='Holiday List', holiday_list_name='_Friday Holidays', from_date='2026-01-01', to_date='2026-12-31', holidays=[dict(holiday_date='2026-07-05', description='Sunday', weekly_off=1)])).insert()
        frappe.get_doc(dict(doctype='Holiday List Assignment', applicable_for='Company', assigned_to=self.company, holiday_list=holiday.name, from_date='2026-01-01')).insert().submit()
        pe = frappe.get_doc(dict(doctype='Payroll Entry', company=self.company, currency='PKR', exchange_rate=1, payroll_frequency='Monthly', start_date='2026-07-01', end_date='2026-07-31', posting_date='2026-07-31', cost_center='Main - FPT', payroll_payable_account=frappe.db.get_value('Company', self.company, 'default_payroll_payable_account'), employees=[dict(employee=self.employee)]))
        pe.insert()
        pe.create_salary_slips()
        names = frappe.get_all('Salary Slip', filters={'payroll_entry': pe.name}, pluck='name')
        self.assertEqual(len(names), 1, pe.error_message)
        slip = frappe.get_doc('Salary Slip', names[0])
        amounts = {row.salary_component: row.amount for row in slip.earnings + slip.deductions}
        self.assertEqual(amounts, {'FP Gross':20774, 'FP Overtime':2087, 'FP Deficiency':635, 'FP Advance':7000})
        self.assertEqual((slip.payment_days, slip.net_pay, slip.docstatus), (28, 15226, 0))
        self.assertEqual(slip.total_deduction, 7635)  # no tax
        slip.save()
        self.assertEqual(slip.net_pay, 15226)
        self.assertEqual(before, frappe.get_all('Attendance', filters={'employee': self.employee}, fields=['*']))
        row = frappe.get_doc('Attendance', friday)
        self.assertEqual(row.status, 'Absent')
        self.assertFalse(row.custom_check_in_time)
        self.assertFalse(row.custom_check_out_time)
        self.assertEqual(row.custom_deficiency_hours, 0)
        self.assertEqual(frappe.db.count('Employee Checkin', {'employee':self.employee}), 0)
        print('Native Payroll Entry: Gross20774 OT2087 Def635 Advance7000 Tax0 Net15226 payment_days28; Attendance unchanged')

    def test_negative_charge_rejected(self):
        self.rule.friday_absence_deficiency_hours = -1
        with self.assertRaises(frappe.ValidationError):
            self.rule.save()

    def test_positive_charge_requires_date(self):
        self.rule.friday_absence_policy_from_date = None
        with self.assertRaises(frappe.ValidationError):
            self.rule.save()

    def test_friday_paid_with_payroll_deficiency(self):
        self.attendance('2026-07-03')
        for date in ['2026-07-04','2026-07-06','2026-07-07']:
            self.attendance(date)
        self.attendance('2026-07-25', 'Present', deficiency=1.35, overtime=15)
        self.assertEqual(self.slip._paid_days(), 28)
        self.assertAlmostEqual(self.slip._deficiency_hours(), 6.85)


def run():
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TestFridayAbsencePolicy))
    if not result.wasSuccessful():
        raise AssertionError('Friday policy tests failed')
