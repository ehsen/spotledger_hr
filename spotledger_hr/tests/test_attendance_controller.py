import unittest
from frappe.tests.utils import FrappeTestCase
import frappe
from frappe.utils import get_datetime
from spotledger_hr.attendance_rule_engine import get_time_after_grace

class TestGraceTimeLogic(FrappeTestCase):
    def setUp(self):
        self.rule = frappe.get_doc({
            "doctype": "Attendance Rule",
            "company": "Test Company",
            "factory_start_time": "08:00:00",
            "factory_end_time": "17:00:00",
            "required_factory_hours": 8.5,
            "checkin_grace_minutes": 15,
            "checkin_max_grace_minutes": 30,
            "checkout_grace_minutes": 15,
            "checkout_max_grace_minutes": 30
        })

    def test_checkin_before_grace(self):
        result = get_time_after_grace("2024-01-01 08:05:00", 10, 30, "08:00:00", "2024-01-01")
        expected = get_datetime("2024-01-01 08:00:00")
        self.assertEqual(result, expected)

    def test_checkin_within_max_grace(self):
        result = get_time_after_grace("2024-01-01 08:20:00", 10, 30, "08:00:00", "2024-01-01")
        expected = get_datetime("2024-01-01 08:30:00")
        self.assertEqual(result, expected)

    def test_checkin_after_max_grace(self):
        result = get_time_after_grace("2024-01-01 08:40:00", 10, 30, "08:00:00", "2024-01-01")
        expected = get_datetime("2024-01-01 08:40:00")
        self.assertEqual(result, expected)

    def test_checkout_before_grace(self):
        result = get_time_after_grace("2024-01-01 16:55:00", 5, 20, "17:00:00", "2024-01-01")
        expected = get_datetime("2024-01-01 17:00:00")
        self.assertEqual(result, expected)

    def test_checkout_within_max_grace(self):
        result = get_time_after_grace("2024-01-01 17:10:00", 5, 20, "17:00:00", "2024-01-01")
        expected = get_datetime("2024-01-01 17:20:00")
        self.assertEqual(result, expected)

    def test_checkout_after_max_grace(self):
        result = get_time_after_grace("2024-01-01 17:30:00", 5, 20, "17:00:00", "2024-01-01")
        expected = get_datetime("2024-01-01 17:30:00")
        self.assertEqual(result, expected)