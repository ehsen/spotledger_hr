# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Comprehensive tests for Attendance Rule Engine
"""

import frappe
import unittest
from datetime import datetime, timedelta
from frappe.tests.utils import FrappeTestCase
from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
from spotledger_hr.tests.fixtures.attendance_test_data import (
    STANDARD_ATTENDANCE_RULE,
    TEST_DATES,
    GRACE_PERIOD_SCENARIOS,
    BREAK_CALCULATION_SCENARIOS,
    OVERTIME_SCENARIOS,
    DEFICIENCY_SCENARIOS,
    FRIDAY_LOGIC_SCENARIOS,
    OVERNIGHT_SHIFT_SCENARIOS,
    COMPLETE_ATTENDANCE_SCENARIOS,
    EDGE_CASE_SCENARIOS,
    TEST_EMPLOYEES,
    TEST_HOLIDAY_LIST
)


class TestAttendanceRuleEngine(FrappeTestCase):
    """Test cases for Attendance Rule Engine"""

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
    
    def test_engine_initialization(self):
        """Test engine initialization"""
        engine = AttendanceRuleEngine(self.employee, self.attendance_date)
        
        self.assertIsNotNone(engine.rule)
        self.assertEqual(engine.employee, self.employee)
        self.assertEqual(engine.attendance_date, self.attendance_date)
        self.assertFalse(engine.is_friday)  # Monday
        self.assertFalse(engine.is_gazetted)  # Not a holiday
    
    def test_friday_detection(self):
        """Test Friday detection"""
        engine = AttendanceRuleEngine(self.employee, TEST_DATES["friday"])
        self.assertTrue(engine.is_friday)
        
        engine = AttendanceRuleEngine(self.employee, TEST_DATES["regular_monday"])
        self.assertFalse(engine.is_friday)
    
    def test_gazetted_holiday_detection(self):
        """Test gazetted holiday detection"""
        engine = AttendanceRuleEngine(self.employee, TEST_DATES["holiday"])
        self.assertTrue(engine.is_gazetted)
        
        engine = AttendanceRuleEngine(self.employee, TEST_DATES["regular_monday"])
        self.assertFalse(engine.is_gazetted)
    
    def test_get_current_datetime(self):
        """Test datetime creation utility"""
        engine = AttendanceRuleEngine(self.employee, self.attendance_date)
        
        dt = engine.get_current_datetime("2024-01-15", "07:30:00")
        expected = datetime(2024, 1, 15, 7, 30, 0)
        self.assertEqual(dt, expected)
        
        # Test with add_day
        dt_next = engine.get_current_datetime("2024-01-15", "07:30:00", add_day=True)
        expected_next = datetime(2024, 1, 16, 7, 30, 0)
        self.assertEqual(dt_next, expected_next)
    
    def test_get_break_times(self):
        """Test break time calculation"""
        engine = AttendanceRuleEngine(self.employee, TEST_DATES["regular_monday"])
        break_times = engine.get_break_times()
        
        self.assertEqual(break_times['start'].hour, 12)
        self.assertEqual(break_times['start'].minute, 0)
        self.assertEqual(break_times['end'].hour, 12)
        self.assertEqual(break_times['end'].minute, 30)
        
        # Test Friday break times
        engine_friday = AttendanceRuleEngine(self.employee, TEST_DATES["friday"])
        friday_break_times = engine_friday.get_break_times()
        
        self.assertEqual(friday_break_times['start'].hour, 12)
        self.assertEqual(friday_break_times['start'].minute, 30)
        self.assertEqual(friday_break_times['end'].hour, 14)
        self.assertEqual(friday_break_times['end'].minute, 0)


class TestGracePeriodLogic(FrappeTestCase):
    """Test cases for grace period logic"""

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
        
        if not frappe.db.exists("Attendance Rule", "Test Company"):
            frappe.get_doc(STANDARD_ATTENDANCE_RULE).insert()
        
        if not frappe.db.exists("Employee", "TEST-EMP-001"):
                frappe.get_doc({
                    "doctype": "Employee",
                    "employee": "TEST-EMP-001",
                    "employee_name": "Test Employee 1",
                    "first_name": "Test",
                    "last_name": "Employee 1",
                    "company": "Test Company",
                    "custom_attendance_rule": "Test Company",
                    "gender": "Male",
                    "date_of_birth": "1990-01-01",
                    "date_of_joining": "2020-01-01",
                    "status": "Active"
                }).insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_checkin_grace_periods(self):
        """Test check-in grace period logic"""
        engine = AttendanceRuleEngine(self.employee, self.attendance_date)
        
        for scenario in GRACE_PERIOD_SCENARIOS:
            if "checkin" in scenario["name"]:
                with self.subTest(scenario=scenario["name"]):
                    adjusted_time = engine.get_time_after_grace_in(scenario["check_in"])
                    expected_time = datetime.strptime(
                        f"{self.attendance_date} {scenario['expected_adjusted_checkin']}", 
                        "%Y-%m-%d %H:%M:%S"
                    )
                    self.assertEqual(adjusted_time, expected_time, scenario["description"])
    
    def test_checkout_grace_periods(self):
        """Test check-out grace period logic"""
        engine = AttendanceRuleEngine(self.employee, self.attendance_date)
        
        for scenario in GRACE_PERIOD_SCENARIOS:
            if "checkout" in scenario["name"]:
                with self.subTest(scenario=scenario["name"]):
                    adjusted_time = engine.get_time_after_grace_out(scenario["check_out"])
                    expected_time = datetime.strptime(
                        f"{self.attendance_date} {scenario['expected_adjusted_checkout']}", 
                        "%Y-%m-%d %H:%M:%S"
                    )
                    self.assertEqual(adjusted_time, expected_time, scenario["description"])


class TestBreakCalculations(FrappeTestCase):
    """Test cases for break calculation logic"""

    def get_employee_by_number(self, employee_number):
        """Get employee name by employee number"""
        return frappe.db.get_value("Employee", {"employee_number": employee_number}, "name")

    def setUp(self):
        """Set up test data"""
        self.create_test_data()
        self.employee_number = "TEST-EMP-001"
        self.employee = self.get_employee_by_number(self.employee_number)
    
    def create_test_data(self):
        """Create test data"""
        if not frappe.db.exists("Company", "Test Company"):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "USD"
            }).insert()
        
        if not frappe.db.exists("Attendance Rule", "Test Company"):
            frappe.get_doc(STANDARD_ATTENDANCE_RULE).insert()
        
        if not frappe.db.exists("Employee", "TEST-EMP-001"):
                frappe.get_doc({
                    "doctype": "Employee",
                    "employee": "TEST-EMP-001",
                    "employee_name": "Test Employee 1",
                    "first_name": "Test",
                    "last_name": "Employee 1",
                    "company": "Test Company",
                    "custom_attendance_rule": "Test Company",
                    "gender": "Male",
                    "date_of_birth": "1990-01-01",
                    "date_of_joining": "2020-01-01",
                    "status": "Active"
                }).insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_break_duration_calculations(self):
        """Test break duration calculations"""
        for scenario in BREAK_CALCULATION_SCENARIOS:
            with self.subTest(scenario=scenario["name"]):
                date = TEST_DATES.get(scenario.get("date", "regular_monday"))
                engine = AttendanceRuleEngine(self.employee, date)
                
                break_duration = engine.get_break_duration(
                    scenario["check_in"], 
                    scenario["check_out"]
                )
                
                self.assertEqual(
                    break_duration, 
                    scenario["expected_break_duration"], 
                    scenario["description"]
                )


class TestOvertimeCalculations(FrappeTestCase):
    """Test cases for overtime calculation logic"""

    def get_employee_by_number(self, employee_number):
        """Get employee name by employee number"""
        return frappe.db.get_value("Employee", {"employee_number": employee_number}, "name")

    def setUp(self):
        """Set up test data"""
        self.create_test_data()
        self.employee_number = "TEST-EMP-001"
        self.employee = self.get_employee_by_number(self.employee_number)
    
    def create_test_data(self):
        """Create test data"""
        if not frappe.db.exists("Company", "Test Company"):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "USD"
            }).insert()
        
        if not frappe.db.exists("Attendance Rule", "Test Company"):
            frappe.get_doc(STANDARD_ATTENDANCE_RULE).insert()
        
        if not frappe.db.exists("Employee", "TEST-EMP-001"):
                frappe.get_doc({
                    "doctype": "Employee",
                    "employee": "TEST-EMP-001",
                    "employee_name": "Test Employee 1",
                    "first_name": "Test",
                    "last_name": "Employee 1",
                    "company": "Test Company",
                    "custom_attendance_rule": "Test Company",
                    "gender": "Male",
                    "date_of_birth": "1990-01-01",
                    "date_of_joining": "2020-01-01",
                    "status": "Active"
                }).insert()
        
        if not frappe.db.exists("Holiday List", "Test Holiday List"):
            frappe.get_doc(TEST_HOLIDAY_LIST).insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_overtime_calculations(self):
        """Test overtime calculations"""
        for scenario in OVERTIME_SCENARIOS:
            with self.subTest(scenario=scenario["name"]):
                date = TEST_DATES.get(scenario.get("date", "regular_monday"))
                engine = AttendanceRuleEngine(self.employee, date)
                
                # Update rule if needed for specific scenarios
                if scenario.get("ignore_break_in_overtime"):
                    engine.rule.ignore_break_in_overtime = True
                
                overtime = engine.calculate_overtime(
                    scenario["check_in"], 
                    scenario["check_out"]
                )
                
                self.assertAlmostEqual(
                    overtime, 
                    scenario["expected_overtime"], 
                    places=1,
                    msg=scenario["description"]
                )


class TestDeficiencyCalculations(FrappeTestCase):
    """Test cases for deficiency calculation logic"""

    def get_employee_by_number(self, employee_number):
        """Get employee name by employee number"""
        return frappe.db.get_value("Employee", {"employee_number": employee_number}, "name")

    def setUp(self):
        """Set up test data"""
        self.create_test_data()
        self.employee_number = "TEST-EMP-001"
        self.employee = self.get_employee_by_number(self.employee_number)
    
    def create_test_data(self):
        """Create test data"""
        if not frappe.db.exists("Company", "Test Company"):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "USD"
            }).insert()
        
        if not frappe.db.exists("Attendance Rule", "Test Company"):
            frappe.get_doc(STANDARD_ATTENDANCE_RULE).insert()
        
        if not frappe.db.exists("Employee", "TEST-EMP-001"):
                frappe.get_doc({
                    "doctype": "Employee",
                    "employee": "TEST-EMP-001",
                    "employee_name": "Test Employee 1",
                    "first_name": "Test",
                    "last_name": "Employee 1",
                    "company": "Test Company",
                    "custom_attendance_rule": "Test Company",
                    "gender": "Male",
                    "date_of_birth": "1990-01-01",
                    "date_of_joining": "2020-01-01",
                    "status": "Active"
                }).insert()
        
        if not frappe.db.exists("Holiday List", "Test Holiday List"):
            frappe.get_doc(TEST_HOLIDAY_LIST).insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_deficiency_calculations(self):
        """Test deficiency calculations"""
        for scenario in DEFICIENCY_SCENARIOS:
            with self.subTest(scenario=scenario["name"]):
                date = TEST_DATES.get(scenario.get("date", "regular_monday"))
                engine = AttendanceRuleEngine(self.employee, date)
                
                # Update rule if needed for specific scenarios
                if scenario.get("allow_negative_hours") is not None:
                    engine.rule.allow_negative_hours = scenario["allow_negative_hours"]
                
                deficiency = engine.calculate_deficiency(
                    scenario["check_in"], 
                    scenario["check_out"]
                )
                
                self.assertAlmostEqual(
                    deficiency, 
                    scenario["expected_deficiency"], 
                    places=1,
                    msg=scenario["description"]
                )


class TestFridayLogic(FrappeTestCase):
    """Test cases for Friday special logic"""

    def get_employee_by_number(self, employee_number):
        """Get employee name by employee number"""
        return frappe.db.get_value("Employee", {"employee_number": employee_number}, "name")

    def setUp(self):
        """Set up test data"""
        self.create_test_data()
        self.employee_number = "TEST-EMP-001"
        self.employee = self.get_employee_by_number(self.employee_number)
    
    def create_test_data(self):
        """Create test data"""
        if not frappe.db.exists("Company", "Test Company"):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "USD"
            }).insert()
        
        if not frappe.db.exists("Attendance Rule", "Test Company"):
            frappe.get_doc(STANDARD_ATTENDANCE_RULE).insert()
        
        if not frappe.db.exists("Employee", "TEST-EMP-001"):
                frappe.get_doc({
                    "doctype": "Employee",
                    "employee": "TEST-EMP-001",
                    "employee_name": "Test Employee 1",
                    "first_name": "Test",
                    "last_name": "Employee 1",
                    "company": "Test Company",
                    "custom_attendance_rule": "Test Company",
                    "gender": "Male",
                    "date_of_birth": "1990-01-01",
                    "date_of_joining": "2020-01-01",
                    "status": "Active"
                }).insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_friday_prayer_break_logic(self):
        """Test Friday prayer break checkout logic"""
        for scenario in FRIDAY_LOGIC_SCENARIOS:
            with self.subTest(scenario=scenario["name"]):
                date = TEST_DATES[scenario["date"]]
                engine = AttendanceRuleEngine(self.employee, date)
                
                adjusted_time = engine.get_time_after_grace_out(scenario["check_out"])
                expected_time = datetime.strptime(
                    f"{date} {scenario['expected_adjusted_checkout']}", 
                    "%Y-%m-%d %H:%M:%S"
                )
                
                self.assertEqual(adjusted_time, expected_time, scenario["description"])


class TestOvernightShifts(FrappeTestCase):
    """Test cases for overnight shift handling"""

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
        
        if not frappe.db.exists("Attendance Rule", "Test Company"):
            frappe.get_doc(STANDARD_ATTENDANCE_RULE).insert()
        
        if not frappe.db.exists("Employee", "TEST-EMP-001"):
                frappe.get_doc({
                    "doctype": "Employee",
                    "employee": "TEST-EMP-001",
                    "employee_name": "Test Employee 1",
                    "first_name": "Test",
                    "last_name": "Employee 1",
                    "company": "Test Company",
                    "custom_attendance_rule": "Test Company",
                    "gender": "Male",
                    "date_of_birth": "1990-01-01",
                    "date_of_joining": "2020-01-01",
                    "status": "Active"
                }).insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_overnight_shift_handling(self):
        """Test overnight shift handling"""
        engine = AttendanceRuleEngine(self.employee, self.attendance_date)
        
        for scenario in OVERNIGHT_SHIFT_SCENARIOS:
            with self.subTest(scenario=scenario["name"]):
                adjusted_checkin, adjusted_checkout = engine.handle_overnight_shift(
                    scenario["check_in"], 
                    scenario["check_out"]
                )
                
                self.assertEqual(adjusted_checkin, scenario["expected_adjusted_checkin"])
                self.assertEqual(adjusted_checkout, scenario["expected_adjusted_checkout"])


class TestCompleteAttendanceCalculations(FrappeTestCase):
    """Test cases for complete attendance calculations"""

    def get_employee_by_number(self, employee_number):
        """Get employee name by employee number"""
        return frappe.db.get_value("Employee", {"employee_number": employee_number}, "name")

    def setUp(self):
        """Set up test data"""
        self.create_test_data()
        self.employee_number = "TEST-EMP-001"
        self.employee = self.get_employee_by_number(self.employee_number)
    
    def create_test_data(self):
        """Create test data"""
        if not frappe.db.exists("Company", "Test Company"):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "USD"
            }).insert()
        
        if not frappe.db.exists("Attendance Rule", "Test Company"):
            frappe.get_doc(STANDARD_ATTENDANCE_RULE).insert()
        
        if not frappe.db.exists("Employee", "TEST-EMP-001"):
                frappe.get_doc({
                    "doctype": "Employee",
                    "employee": "TEST-EMP-001",
                    "employee_name": "Test Employee 1",
                    "first_name": "Test",
                    "last_name": "Employee 1",
                    "company": "Test Company",
                    "custom_attendance_rule": "Test Company",
                    "gender": "Male",
                    "date_of_birth": "1990-01-01",
                    "date_of_joining": "2020-01-01",
                    "status": "Active"
                }).insert()
        
        if not frappe.db.exists("Holiday List", "Test Holiday List"):
            frappe.get_doc(TEST_HOLIDAY_LIST).insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_complete_attendance_calculations(self):
        """Test complete attendance calculations"""
        for scenario in COMPLETE_ATTENDANCE_SCENARIOS:
            with self.subTest(scenario=scenario["name"]):
                date = TEST_DATES[scenario["date"]]
                engine = AttendanceRuleEngine(self.employee, date)
                
                summary = engine.calculate_attendance_summary(
                    scenario["check_in"], 
                    scenario["check_out"]
                )
                
                expected = scenario["expected"]
                
                self.assertAlmostEqual(summary["total_hours"], expected["total_hours"], places=1)
                self.assertAlmostEqual(summary["regular_hours"], expected["regular_hours"], places=1)
                self.assertAlmostEqual(summary["overtime_hours"], expected["overtime_hours"], places=1)
                self.assertAlmostEqual(summary["deficiency_hours"], expected["deficiency_hours"], places=1)
                self.assertEqual(summary["is_friday"], expected["is_friday"])
                self.assertEqual(summary["is_gazetted_holiday"], expected["is_gazetted_holiday"])


class TestEdgeCases(FrappeTestCase):
    """Test cases for edge cases and error conditions"""

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
        
        if not frappe.db.exists("Attendance Rule", "Test Company"):
            frappe.get_doc(STANDARD_ATTENDANCE_RULE).insert()
        
        if not frappe.db.exists("Employee", "TEST-EMP-001"):
                frappe.get_doc({
                    "doctype": "Employee",
                    "employee": "TEST-EMP-001",
                    "employee_name": "Test Employee 1",
                    "first_name": "Test",
                    "last_name": "Employee 1",
                    "company": "Test Company",
                    "custom_attendance_rule": "Test Company",
                    "gender": "Male",
                    "date_of_birth": "1990-01-01",
                    "date_of_joining": "2020-01-01",
                    "status": "Active"
                }).insert()
    
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_edge_cases(self):
        """Test edge cases"""
        engine = AttendanceRuleEngine(self.employee, self.attendance_date)
        
        for scenario in EDGE_CASE_SCENARIOS:
            with self.subTest(scenario=scenario["name"]):
                summary = engine.calculate_attendance_summary(
                    scenario["check_in"], 
                    scenario["check_out"]
                )
                
                expected = scenario["expected"]
                
                self.assertAlmostEqual(summary["total_hours"], expected["total_hours"], places=1)
                self.assertAlmostEqual(summary["regular_hours"], expected["regular_hours"], places=1)
                self.assertAlmostEqual(summary["overtime_hours"], expected["overtime_hours"], places=1)
                self.assertAlmostEqual(summary["deficiency_hours"], expected["deficiency_hours"], places=1)
    
    def test_invalid_employee(self):
        """Test error handling for invalid employee"""
        with self.assertRaises(Exception):
            AttendanceRuleEngine("INVALID-EMP", self.attendance_date)
    
    def test_missing_attendance_rule(self):
        """Test error handling for missing attendance rule"""
        # Create employee without attendance rule
        if not frappe.db.exists("Employee", "TEST-EMP-NO-RULE"):
            frappe.get_doc({
                "doctype": "Employee",
                "employee": "TEST-EMP-NO-RULE",
                "employee_name": "Test Employee No Rule",
                "company": "Test Company"
            }).insert()
        
        with self.assertRaises(Exception):
            AttendanceRuleEngine("TEST-EMP-NO-RULE", self.attendance_date)
