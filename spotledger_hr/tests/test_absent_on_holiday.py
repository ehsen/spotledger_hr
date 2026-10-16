"""Synthetic fixtures only; every test rolls back. Run on the bfi dev site."""
import unittest
import frappe
from spotledger_hr.spotledger_hr.doctype.bulk_attendance.bulk_attendance import BulkAttendance

NAMED = '2026-08-14'      # Friday, named holiday (Independence Day)
WEEKLY = '2026-08-16'     # Sunday, weekly off
WORKDAY = '2026-08-17'    # Monday, ordinary day


class TestAbsentOnHoliday(unittest.TestCase):
	def setUp(self):
		assert frappe.local.site == 'bfi.local', 'Run on the bfi dev site'
		frappe.flags.in_test = True
		frappe.in_test = True
		if not frappe.db.exists('Warehouse Type', 'Transit'):
			frappe.get_doc(dict(doctype='Warehouse Type', name='Transit')).insert()
		if not frappe.db.exists('Gender', 'Male'):
			frappe.get_doc(dict(doctype='Gender', gender='Male')).insert()
		self.company = '_Holiday Absent Test'
		if not frappe.db.exists('Company', self.company):
			frappe.get_doc(dict(doctype='Company', company_name=self.company, abbr='HAT', default_currency='PKR', country='Pakistan')).insert()
		self.holiday_list = self.make_holiday_list('_HAT Holidays')
		self.rule = frappe.get_doc(dict(doctype='Attendance Rule', name='_HAT Rule', company=self.company, factory_start_time='08:00:00', factory_end_time='17:00:00', wage_rate_hours=8.5, required_factory_hours=8.5, break_duration_minutes=30, overtime_multiplier=1.5)).insert()
		self.employee = self.make_employee('Synthetic Holiday Worker', holiday_list=self.holiday_list)

	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_cache()

	def make_holiday_list(self, name):
		doc = frappe.get_doc(dict(doctype='Holiday List', holiday_list_name=name, from_date='2026-01-01', to_date='2026-12-31'))
		doc.append('holidays', dict(holiday_date=NAMED, description='Independence Day', weekly_off=0))
		doc.append('holidays', dict(holiday_date=WEEKLY, description='Sunday', weekly_off=1))
		return doc.insert().name

	def make_employee(self, first_name, holiday_list=None):
		return frappe.get_doc(dict(doctype='Employee', first_name=first_name, custom_father_name='Synthetic Parent', gender='Male', date_of_birth='1990-01-01', date_of_joining='2026-01-01', company=self.company, custom_attendance_rule=self.rule.name, holiday_list=holiday_list)).insert().name

	def attendance(self, date, employee=None, status='Absent', **extra):
		return frappe.get_doc(dict(doctype='Attendance', employee=employee or self.employee, attendance_date=date, status=status, company=self.company, custom_manual_attendance=1, **extra))

	def test_absent_on_named_holiday_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.attendance(NAMED).insert()

	def test_absent_on_ordinary_day_allowed(self):
		self.attendance(WORKDAY).insert()

	def test_weekly_off_behaviour_unchanged(self):
		self.attendance(WEEKLY).insert()

	def test_company_default_list_used_when_employee_has_none(self):
		frappe.db.set_value('Company', self.company, 'default_holiday_list', self.holiday_list)
		frappe.clear_cache()
		emp = self.make_employee('Synthetic No List')
		frappe.db.set_value('Employee', emp, 'holiday_list', None)
		frappe.clear_document_cache('Employee', emp)
		with self.assertRaises(frappe.ValidationError):
			self.attendance(NAMED, employee=emp).insert()

	def test_no_holiday_list_anywhere_does_not_block(self):
		emp = self.make_employee('Synthetic No List')
		frappe.db.set_value('Employee', emp, 'holiday_list', None)
		frappe.db.set_value('Company', self.company, 'default_holiday_list', None)
		frappe.clear_cache()
		self.attendance(NAMED, employee=emp).insert()

	def test_rule_allows_absent_on_holiday(self):
		frappe.db.set_value('Attendance Rule', self.rule.name, 'allow_absent_on_holiday', 1)
		frappe.clear_document_cache('Attendance Rule', self.rule.name)
		self.attendance(NAMED).insert()

	def test_present_on_holiday_stays_present(self):
		doc = self.attendance(NAMED, status='Present').insert()
		self.assertEqual(doc.status, 'Present')

	def test_bulk_status_holiday_vs_absent(self):
		bulk = BulkAttendance({'doctype': 'Bulk Attendance'})
		self.assertEqual(bulk.get_status(None, None, self.employee, NAMED), 'Holiday')
		self.assertEqual(bulk.get_status(None, None, self.employee, WORKDAY), 'Absent')
		self.assertEqual(bulk.get_status(None, None, self.employee, WEEKLY), 'Absent')
		self.assertEqual(bulk.get_status(None, None), 'Absent')
		self.assertEqual(bulk.get_status('2026-08-14 09:00:00', '2026-08-14 17:00:00', self.employee, NAMED), 'Present')

	def test_bulk_create_skips_holiday_rows(self):
		frappe.db.set_value('Employee', self.employee, 'custom_attendance_required', 1)
		bulk = frappe.get_doc(dict(doctype='Bulk Attendance', from_date=NAMED, to_date=WORKDAY))
		bulk.append('attendance_data', dict(employee=self.employee, employee_name='x', day=NAMED, status='Holiday'))
		bulk.append('attendance_data', dict(employee=self.employee, employee_name='x', day=WORKDAY, status='Absent'))
		bulk.insert()
		result = bulk.bulk_create_attendance()
		self.assertEqual((result['successful'], result['skipped_holidays'], result['failed']), (1, 1, 0), result['failed_records'])
		self.assertFalse(frappe.db.exists('Attendance', dict(employee=self.employee, attendance_date=NAMED)))
