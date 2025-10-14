# -*- coding: utf-8 -*-
# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

import frappe
import unittest
from frappe.utils import getdate, get_datetime


class TestBulkAttendance(unittest.TestCase):
	def setUp(self):
		self.bulk_attendance = frappe.get_doc({
			"doctype": "Bulk Attendance",
			"title": "Test Bulk Attendance",
			"from_date": getdate(),
			"to_date": getdate()
		})
		self.bulk_attendance.insert()

	def tearDown(self):
		frappe.delete_doc("Bulk Attendance", self.bulk_attendance.name)

	def test_validate_date_range(self):
		"""Test date validation"""
		self.bulk_attendance.from_date = getdate("2025-01-15")
		self.bulk_attendance.to_date = getdate("2025-01-10")

		with self.assertRaises(frappe.ValidationError):
			self.bulk_attendance.validate()

	def test_get_status_logic(self):
		"""Test status determination logic"""
		# Test Present status
		status = self.bulk_attendance.get_status(
			get_datetime("2025-01-15 09:00:00"),
			get_datetime("2025-01-15 17:00:00")
		)
		self.assertEqual(status, "Present")

		# Test Error status (only checkin)
		status = self.bulk_attendance.get_status(
			get_datetime("2025-01-15 09:00:00"),
			None
		)
		self.assertEqual(status, "Error")

		# Test Error status (only checkout)
		status = self.bulk_attendance.get_status(
			None,
			get_datetime("2025-01-15 17:00:00")
		)
		self.assertEqual(status, "Error")

		# Test Absent status
		status = self.bulk_attendance.get_status(None, None)
		self.assertEqual(status, "Absent")

	def test_load_data_functionality(self):
		"""Test data loading functionality"""
		# Create test employee checkin records
		employee = frappe.get_doc({
			"doctype": "Employee",
			"employee_name": "Test Employee",
			"employee_number": "EMP001"
		}).insert()

		checkin = frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": employee.name,
			"log_type": "IN",
			"time": get_datetime("2025-01-15 09:00:00")
		}).insert()

		checkout = frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": employee.name,
			"log_type": "OUT",
			"time": get_datetime("2025-01-15 17:00:00")
		}).insert()

		# Load data
		self.bulk_attendance.from_date = getdate("2025-01-15")
		self.bulk_attendance.to_date = getdate("2025-01-15")
		self.bulk_attendance.load_data()

		# Check if data was loaded correctly
		self.assertGreater(len(self.bulk_attendance.attendance_data), 0)

		# Check first item
		item = self.bulk_attendance.attendance_data[0]
		self.assertEqual(item.employee, employee.name)
		self.assertEqual(item.status, "Present")
		self.assertEqual(str(item.check_in_date), "2025-01-15")
		self.assertEqual(str(item.check_out_date), "2025-01-15")

		# Clean up test data
		frappe.delete_doc("Employee Checkin", checkin.name)
		frappe.delete_doc("Employee Checkin", checkout.name)
		frappe.delete_doc("Employee", employee.name)

	def test_bulk_update_functionality(self):
		"""Test bulk update functionality"""
		# Create test data
		employee = frappe.get_doc({
			"doctype": "Employee",
			"employee_name": "Test Employee 2",
			"employee_number": "EMP002"
		}).insert()

		checkin = frappe.get_doc({
			"doctype": "Employee Checkin",
			"employee": employee.name,
			"log_type": "IN",
			"time": get_datetime("2025-01-15 09:00:00")
		}).insert()

		# Load and modify data
		self.bulk_attendance.from_date = getdate("2025-01-15")
		self.bulk_attendance.to_date = getdate("2025-01-15")
		self.bulk_attendance.load_data()

		# Modify the checkin time
		item = self.bulk_attendance.attendance_data[0]
		item.check_in_time = "10:00:00"

		# Perform bulk update
		self.bulk_attendance.bulk_update()

		# Verify the change was applied
		updated_checkin = frappe.get_doc("Employee Checkin", checkin.name)
		self.assertEqual(str(updated_checkin.time.time()), "10:00:00")

		# Clean up test data
		frappe.delete_doc("Employee Checkin", checkin.name)
		frappe.delete_doc("Employee", employee.name)

