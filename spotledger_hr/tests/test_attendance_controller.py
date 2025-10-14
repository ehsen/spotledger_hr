# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Tests for Custom Attendance Controller
"""

import frappe
import unittest
from datetime import datetime, timedelta
from frappe.tests.utils import FrappeTestCase
from spotledger_hr.controllers.attendance_controller import (
    AttendanceController,
    calculate_attendance_preview,
    bulk_calculate_attendance,
    get_attendance_rule_summary,
    validate_attendance_rule_configuration
)
from spotledger_hr.tests.fixtures.attendance_test_data import (
    STANDARD_ATTENDANCE_RULE,
    TEST_DATES,
    TEST_EMPLOYEES,
    TEST_HOLIDAY_LIST
)


class TestAttendanceController(FrappeTestCase):
    """Test cases for Custom Attendance Controller"""

    def get_employee_by_number(self, employee_number):
        """Get employee name by employee number"""
        return frappe.db.get_value("Employee", {"employee_number": employee_number}, "name")

    def setUp(self):
        """Set up test data"""
        self.create_test_data()
        self.employee_number = "TEST-EMP-001"
        self.employee = self.get_employee_by_number(self.employee_number)
        self.attendance_date = TEST_DATES["regular_monday"]
    
    def create_test_data(self):
        """Create test data"""
        # Create test company
        if not frappe.db.exists("Company", "Test Company"):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "USD"
            }).insert()
        
        # Create test holiday list
        if not frappe.db.exists("Holiday List", "Test Holiday List"):
            frappe.get_doc(TEST_HOLIDAY_LIST).insert()
        
        # Create test attendance rule
        if not frappe.db.exists("Attendance Rule", "Test Company"):
            frappe.get_doc(STANDARD_ATTENDANCE_RULE).insert()
        
        # Create test employees
        for emp_data in TEST_EMPLOYEES:
            # Check if employee exists by employee_number
            employee_exists = False
            if emp_data.get("employee_number"):
                existing_employee = frappe.db.get_value("Employee", {"employee_number": emp_data["employee_number"]}, "name")
                if existing_employee:
                    employee_exists = True

            if not employee_exists:
                employee_doc = frappe.get_doc({
                    "doctype": "Employee",
                    "employee_name": emp_data["employee_name"],
                    "first_name": emp_data["first_name"],
                    "last_name": emp_data["last_name"],
                    "company": emp_data["company"],
                    "custom_attendance_rule": emp_data["custom_attendance_rule"],
                    "gender": emp_data["gender"],
                    "date_of_birth": emp_data["date_of_birth"],
                    "date_of_joining": emp_data["date_of_joining"],
                    "status": emp_data["status"],
                    "holiday_list": "Test Holiday List"
                })

                # Set employee_number and naming_series if provided
                if emp_data.get("employee_number"):
                    employee_doc.employee_number = emp_data["employee_number"]
                if emp_data.get("naming_series"):
                    employee_doc.naming_series = emp_data["naming_series"]

                employee_doc.insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_attendance_controller_initialization(self):
        """Test attendance controller initialization"""
        attendance_doc = frappe.get_doc({
            "doctype": "Attendance",
            "employee": self.employee,
            "attendance_date": self.attendance_date,
            "check_in": f"{self.attendance_date} 07:30:00",
            "check_out": f"{self.attendance_date} 16:00:00",
            "status": "Present"
        })
        
        # Convert to custom controller
        controller = AttendanceController(attendance_doc.as_dict())
        
        self.assertEqual(controller.employee, self.employee)
        self.assertEqual(controller.attendance_date, self.attendance_date)
    
    def test_attendance_metrics_calculation(self):
        """Test attendance metrics calculation"""
        attendance_doc = frappe.get_doc({
            "doctype": "Attendance",
            "employee": self.employee,
            "attendance_date": self.attendance_date,
            "check_in": f"{self.attendance_date} 07:30:00",
            "check_out": f"{self.attendance_date} 16:00:00",
            "status": "Present"
        })
        
        controller = AttendanceController(attendance_doc.as_dict())
        controller.calculate_attendance_metrics()
        
        # Check if custom fields are populated
        self.assertIsNotNone(controller.custom_regular_hours)
        self.assertIsNotNone(controller.custom_overtime_hours)
        self.assertIsNotNone(controller.custom_deficiency_hours)
        self.assertIsNotNone(controller.custom_total_hours)
        self.assertIsNotNone(controller.custom_break_duration_minutes)
        self.assertIsNotNone(controller.custom_is_friday)
        self.assertIsNotNone(controller.custom_is_gazetted_holiday)
    
    def test_attendance_validation(self):
        """Test attendance validation"""
        attendance_doc = frappe.get_doc({
            "doctype": "Attendance",
            "employee": self.employee,
            "attendance_date": self.attendance_date,
            "check_in": f"{self.attendance_date} 07:30:00",
            "check_out": f"{self.attendance_date} 16:00:00",
            "status": "Present"
        })
        
        controller = AttendanceController(attendance_doc.as_dict())
        controller.validate()
        
        # Should not raise any exceptions
        self.assertTrue(True)
    
    def test_overtime_attendance_calculation(self):
        """Test overtime attendance calculation"""
        attendance_doc = frappe.get_doc({
            "doctype": "Attendance",
            "employee": self.employee,
            "attendance_date": self.attendance_date,
            "check_in": f"{self.attendance_date} 07:30:00",
            "check_out": f"{self.attendance_date} 17:30:00",  # 10 hours
            "status": "Present"
        })
        
        controller = AttendanceController(attendance_doc.as_dict())
        controller.calculate_attendance_metrics()
        
        # Should have overtime
        self.assertGreater(controller.custom_overtime_hours, 0)
        self.assertEqual(controller.status, "Present")
    
    def test_deficiency_attendance_calculation(self):
        """Test deficiency attendance calculation"""
        attendance_doc = frappe.get_doc({
            "doctype": "Attendance",
            "employee": self.employee,
            "attendance_date": self.attendance_date,
            "check_in": f"{self.attendance_date} 07:30:00",
            "check_out": f"{self.attendance_date} 15:00:00",  # 7.5 hours
            "status": "Present"
        })
        
        controller = AttendanceController(attendance_doc.as_dict())
        controller.calculate_attendance_metrics()
        
        # Should have deficiency
        self.assertGreater(controller.custom_deficiency_hours, 0)
        self.assertEqual(controller.status, "Half Day")
    
    def test_friday_attendance_calculation(self):
        """Test Friday attendance calculation"""
        friday_date = TEST_DATES["friday"]
        attendance_doc = frappe.get_doc({
            "doctype": "Attendance",
            "employee": self.employee,
            "attendance_date": friday_date,
            "check_in": f"{friday_date} 07:30:00",
            "check_out": f"{friday_date} 16:00:00",
            "status": "Present"
        })
        
        controller = AttendanceController(attendance_doc.as_dict())
        controller.calculate_attendance_metrics()
        
        # Should be Friday
        self.assertTrue(controller.custom_is_friday)
        self.assertFalse(controller.custom_is_gazetted_holiday)
    
    def test_gazetted_holiday_attendance_calculation(self):
        """Test gazetted holiday attendance calculation"""
        holiday_date = TEST_DATES["holiday"]
        attendance_doc = frappe.get_doc({
            "doctype": "Attendance",
            "employee": self.employee,
            "attendance_date": holiday_date,
            "check_in": f"{holiday_date} 07:30:00",
            "check_out": f"{holiday_date} 16:00:00",
            "status": "Present"
        })
        
        controller = AttendanceController(attendance_doc.as_dict())
        controller.calculate_attendance_metrics()
        
        # Should be gazetted holiday
        self.assertTrue(controller.custom_is_gazetted_holiday)
        # Should have overtime (all hours * multiplier)
        self.assertGreater(controller.custom_overtime_hours, 0)


class TestAttendanceControllerAPI(FrappeTestCase):
    """Test cases for Attendance Controller API functions"""

    def get_employee_by_number(self, employee_number):
        """Get employee name by employee number"""
        return frappe.db.get_value("Employee", {"employee_number": employee_number}, "name")

    def setUp(self):
        """Set up test data"""
        self.create_test_data()
        self.employee_number = "TEST-EMP-001"
        self.employee = self.get_employee_by_number(self.employee_number)
        self.attendance_date = TEST_DATES["regular_monday"]
    
    def create_test_data(self):
        """Create test data"""
        if not frappe.db.exists("Company", "Test Company"):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "USD"
            }).insert()
        
        if not frappe.db.exists("Holiday List", "Test Holiday List"):
            frappe.get_doc(TEST_HOLIDAY_LIST).insert()
        
        if not frappe.db.exists("Attendance Rule", "Test Company"):
            frappe.get_doc(STANDARD_ATTENDANCE_RULE).insert()
        
        for emp_data in TEST_EMPLOYEES:
            if not frappe.db.exists("Employee", emp_data["name"]):
                frappe.get_doc({
                    "doctype": "Employee",
                    "employee": emp_data["name"],
                    "employee_name": emp_data["employee_name"],
                    "first_name": emp_data["first_name"],
                    "last_name": emp_data["last_name"],
                    "company": emp_data["company"],
                    "custom_attendance_rule": emp_data["custom_attendance_rule"],
                    "gender": emp_data["gender"],
                    "date_of_birth": emp_data["date_of_birth"],
                    "date_of_joining": emp_data["date_of_joining"],
                    "status": emp_data["status"],
                    "holiday_list": "Test Holiday List"
                }).insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_calculate_attendance_preview(self):
        """Test attendance preview calculation"""
        result = calculate_attendance_preview(
            self.employee,
            self.attendance_date,
            f"{self.attendance_date} 07:30:00",
            f"{self.attendance_date} 16:00:00"
        )
        
        self.assertTrue(result['success'])
        self.assertIn('data', result)
        self.assertIn('total_hours', result['data'])
        self.assertIn('regular_hours', result['data'])
        self.assertIn('overtime_hours', result['data'])
        self.assertIn('deficiency_hours', result['data'])
    
    def test_calculate_attendance_preview_error(self):
        """Test attendance preview calculation with invalid data"""
        result = calculate_attendance_preview(
            "INVALID-EMP",
            self.attendance_date,
            f"{self.attendance_date} 07:30:00",
            f"{self.attendance_date} 16:00:00"
        )
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_bulk_calculate_attendance(self):
        """Test bulk attendance calculation"""
        attendance_records = [
            {
                'employee': self.employee,
                'attendance_date': self.attendance_date,
                'check_in': f"{self.attendance_date} 07:30:00",
                'check_out': f"{self.attendance_date} 16:00:00"
            },
            {
                'employee': self.employee,
                'attendance_date': TEST_DATES["regular_tuesday"],
                'check_in': f"{TEST_DATES['regular_tuesday']} 07:30:00",
                'check_out': f"{TEST_DATES['regular_tuesday']} 17:00:00"
            }
        ]
        
        result = bulk_calculate_attendance(attendance_records)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_processed'], 2)
        self.assertEqual(result['successful'], 2)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(len(result['results']), 2)
    
    def test_bulk_calculate_attendance_with_errors(self):
        """Test bulk attendance calculation with some errors"""
        attendance_records = [
            {
                'employee': self.employee,
                'attendance_date': self.attendance_date,
                'check_in': f"{self.attendance_date} 07:30:00",
                'check_out': f"{self.attendance_date} 16:00:00"
            },
            {
                'employee': "INVALID-EMP",
                'attendance_date': self.attendance_date,
                'check_in': f"{self.attendance_date} 07:30:00",
                'check_out': f"{self.attendance_date} 16:00:00"
            }
        ]
        
        result = bulk_calculate_attendance(attendance_records)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['total_processed'], 2)
        self.assertEqual(result['successful'], 1)
        self.assertEqual(result['failed'], 1)
        self.assertEqual(len(result['errors']), 1)
    
    def test_get_attendance_rule_summary(self):
        """Test getting attendance rule summary"""
        result = get_attendance_rule_summary(self.employee)
        
        self.assertTrue(result['success'])
        self.assertIn('data', result)
        self.assertIn('factory_start_time', result['data'])
        self.assertIn('factory_end_time', result['data'])
        self.assertIn('required_factory_hours', result['data'])
        self.assertIn('checkin_grace_minutes', result['data'])
        self.assertIn('checkout_grace_minutes', result['data'])
    
    def test_get_attendance_rule_summary_error(self):
        """Test getting attendance rule summary with invalid employee"""
        result = get_attendance_rule_summary("INVALID-EMP")
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_validate_attendance_rule_configuration(self):
        """Test attendance rule configuration validation"""
        result = validate_attendance_rule_configuration("Test Company")
        
        self.assertTrue(result['success'])
        self.assertTrue(result['is_valid'])
        self.assertEqual(len(result['validation_results']), 0)
    
    def test_validate_attendance_rule_configuration_invalid(self):
        """Test attendance rule configuration validation with invalid rule"""
        # Create invalid rule
        invalid_rule = {
            "doctype": "Attendance Rule",
            "company": "Invalid Company",
            "factory_start_time": "07:30:00",
            "factory_end_time": "06:00:00",  # End before start
            "required_factory_hours": 8.5,
            "checkin_grace_minutes": 30,  # Greater than max
            "checkin_max_grace_minutes": 10,
            "checkout_grace_minutes": 5,
            "checkout_max_grace_minutes": 20,
            "break_duration_minutes": 30,
            "regular_break_start": "12:30:00",  # After end
            "regular_break_end": "12:00:00",
            "friday_break_start": "12:30:00",
            "friday_break_end": "14:00:00",
            "gazetted_overtime_multiplier": 0.5,  # Less than 1.0
            "force_hours_on_friday": True,
            "allow_negative_hours": False,
            "enable_friday_logic": True,
            "consider_check_out_next_day": True,
            "allow_absent_on_holiday": False,
            "ignore_break_in_overtime": False
        }
        
        if not frappe.db.exists("Attendance Rule", "Invalid Company"):
            frappe.get_doc(invalid_rule).insert()
        
        result = validate_attendance_rule_configuration("Invalid Company")
        
        self.assertTrue(result['success'])
        self.assertFalse(result['is_valid'])
        self.assertGreater(len(result['validation_results']), 0)
    
    def test_validate_attendance_rule_configuration_error(self):
        """Test attendance rule configuration validation with non-existent rule"""
        result = validate_attendance_rule_configuration("Non-existent Company")
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)


class TestAttendanceControllerIntegration(FrappeTestCase):
    """Integration tests for Attendance Controller"""

    def get_employee_by_number(self, employee_number):
        """Get employee name by employee number"""
        return frappe.db.get_value("Employee", {"employee_number": employee_number}, "name")

    def setUp(self):
        """Set up test data"""
        self.create_test_data()
        self.employee_number = "TEST-EMP-001"
        self.employee = self.get_employee_by_number(self.employee_number)
        self.attendance_date = TEST_DATES["regular_monday"]
    
    def create_test_data(self):
        """Create test data"""
        if not frappe.db.exists("Company", "Test Company"):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "USD"
            }).insert()
        
        if not frappe.db.exists("Holiday List", "Test Holiday List"):
            frappe.get_doc(TEST_HOLIDAY_LIST).insert()
        
        if not frappe.db.exists("Attendance Rule", "Test Company"):
            frappe.get_doc(STANDARD_ATTENDANCE_RULE).insert()
        
        for emp_data in TEST_EMPLOYEES:
            if not frappe.db.exists("Employee", emp_data["name"]):
                frappe.get_doc({
                    "doctype": "Employee",
                    "employee": emp_data["name"],
                    "employee_name": emp_data["employee_name"],
                    "first_name": emp_data["first_name"],
                    "last_name": emp_data["last_name"],
                    "company": emp_data["company"],
                    "custom_attendance_rule": emp_data["custom_attendance_rule"],
                    "gender": emp_data["gender"],
                    "date_of_birth": emp_data["date_of_birth"],
                    "date_of_joining": emp_data["date_of_joining"],
                    "status": emp_data["status"],
                    "holiday_list": "Test Holiday List"
                }).insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_complete_attendance_workflow(self):
        """Test complete attendance workflow from creation to submission"""
        # Create attendance record
        attendance_doc = frappe.get_doc({
            "doctype": "Attendance",
            "employee": self.employee,
            "attendance_date": self.attendance_date,
            "check_in": f"{self.attendance_date} 07:30:00",
            "check_out": f"{self.attendance_date} 16:00:00",
            "status": "Present"
        })
        
        # Convert to custom controller and validate
        controller = AttendanceController(attendance_doc.as_dict())
        controller.validate()
        
        # Check calculated fields
        self.assertIsNotNone(controller.custom_regular_hours)
        self.assertIsNotNone(controller.custom_overtime_hours)
        self.assertIsNotNone(controller.custom_deficiency_hours)
        self.assertIsNotNone(controller.custom_total_hours)
        
        # Save the document
        attendance_doc.insert()
        
        # Submit the document
        attendance_doc.submit()
        
        # Verify submission
        self.assertEqual(attendance_doc.docstatus, 1)
        
        # Clean up
        attendance_doc.cancel()
        attendance_doc.delete()
    
    def test_attendance_with_different_scenarios(self):
        """Test attendance with different scenarios"""
        scenarios = [
            {
                "name": "perfect_attendance",
                "check_in": "07:30:00",
                "check_out": "16:00:00",
                "expected_status": "Present"
            },
            {
                "name": "overtime_attendance",
                "check_in": "07:30:00",
                "check_out": "17:30:00",
                "expected_status": "Present"
            },
            {
                "name": "deficiency_attendance",
                "check_in": "07:30:00",
                "check_out": "15:00:00",
                "expected_status": "Half Day"
            }
        ]
        
        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                attendance_doc = frappe.get_doc({
                    "doctype": "Attendance",
                    "employee": self.employee,
                    "attendance_date": self.attendance_date,
                    "check_in": f"{self.attendance_date} {scenario['check_in']}",
                    "check_out": f"{self.attendance_date} {scenario['check_out']}",
                    "status": "Present"
                })
                
                controller = AttendanceController(attendance_doc.as_dict())
                controller.validate()
                
                self.assertEqual(controller.status, scenario["expected_status"])