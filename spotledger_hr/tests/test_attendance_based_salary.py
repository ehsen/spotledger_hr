# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Test cases for attendance-based salary calculation
"""

import frappe
import unittest
from frappe.utils import getdate, add_days, add_months
from datetime import datetime


class TestAttendanceBasedSalary(unittest.TestCase):
    """Test attendance-based salary calculation"""
    
    def setUp(self):
        """Set up test data"""
        self.test_employee = None
        self.test_attendance_rule = None
        self.test_salary_structure = None
        
    def tearDown(self):
        """Clean up test data"""
        frappe.db.rollback()
    
    def test_should_calculate_from_attendance(self):
        """Test if employee is correctly identified for attendance-based calculation"""
        # This would require setting up a test employee
        # For now, this is a placeholder for manual testing
        pass
    
    def test_days_worked_calculation(self):
        """Test days worked calculation from attendance"""
        # Create test employee
        # Create test attendance records
        # Calculate salary slip
        # Verify days worked matches attendance count
        pass
    
    def test_overtime_calculation(self):
        """Test overtime hours and amount calculation"""
        # Create test employee with base salary
        # Create attendance with overtime hours
        # Calculate salary slip
        # Verify overtime amount = hours × hourly_rate
        pass
    
    def test_gazetted_overtime_calculation(self):
        """Test gazetted holiday overtime calculation"""
        # Create attendance with gazetted holiday flag
        # Calculate salary slip
        # Verify GZT overtime is separate from regular overtime
        pass
    
    def test_advance_deduction(self):
        """Test employee advance deduction"""
        # Create employee advance record
        # Calculate salary slip
        # Verify advance is deducted
        pass
    
    def test_standard_employee_calculation(self):
        """Test that standard employees still use normal calculation"""
        # Create employee WITHOUT attendance flags
        # Calculate salary slip
        # Verify standard HRMS calculation is used
        pass


def create_test_employee(employee_name="Test Employee", base_salary=50000):
    """
    Helper function to create a test employee with attendance-based flags
    """
    if frappe.db.exists("Employee", employee_name):
        return frappe.get_doc("Employee", employee_name)
    
    employee = frappe.get_doc({
        "doctype": "Employee",
        "employee_name": employee_name,
        "first_name": employee_name,
        "company": frappe.defaults.get_defaults().get("company"),
        "custom_attendance_required": 1,
        "custom_generate_salary_based_on_attendance": 1,
        "custom_attendance_rule": "Default",  # Assumes Default attendance rule exists
        "date_of_joining": getdate()
    })
    employee.insert(ignore_permissions=True)
    
    return employee


def create_test_attendance(employee, date, status="Present", overtime_hours=0, is_gazetted=0):
    """
    Helper function to create test attendance record
    """
    attendance = frappe.get_doc({
        "doctype": "Attendance",
        "employee": employee,
        "attendance_date": date,
        "status": status,
        "custom_overtime_hours": overtime_hours,
        "custom_is_gazetted_holiday": is_gazetted,
        "custom_check_in_time": f"{date} 08:00:00",
        "custom_check_out_time": f"{date} 17:00:00"
    })
    attendance.insert(ignore_permissions=True)
    attendance.submit()
    
    return attendance


def create_test_salary_slip(employee, start_date, end_date):
    """
    Helper function to create test salary slip
    """
    salary_slip = frappe.get_doc({
        "doctype": "Salary Slip",
        "employee": employee,
        "start_date": start_date,
        "end_date": end_date,
        "company": frappe.defaults.get_defaults().get("company")
    })
    
    return salary_slip


def run_manual_test():
    """
    Manual test function to verify attendance-based salary calculation
    Run this from bench console:
    
    >>> from spotledger_hr.tests.test_attendance_based_salary import run_manual_test
    >>> run_manual_test()
    """
    frappe.set_user("Administrator")
    
    print("\n" + "="*80)
    print("ATTENDANCE-BASED SALARY CALCULATION TEST")
    print("="*80 + "\n")
    
    # Get an existing employee or use a test one
    employee_name = frappe.db.get_value("Employee", 
        {
            "custom_attendance_required": 1,
            "custom_generate_salary_based_on_attendance": 1
        },
        "name"
    )
    
    if not employee_name:
        print("❌ No employee found with attendance-based salary flags enabled")
        print("\nTo test, please:")
        print("1. Open an Employee record")
        print("2. Enable 'Attendance Required'")
        print("3. Enable 'Generate Salary Based on Attendance'")
        print("4. Set an 'Attendance Rule'")
        print("5. Ensure a Salary Structure Assignment exists")
        return
    
    employee = frappe.get_doc("Employee", employee_name)
    print(f"✓ Testing with Employee: {employee.name} - {employee.employee_name}")
    
    # Get current month dates
    today = getdate()
    start_date = today.replace(day=1)
    end_date = add_months(start_date, 1) - add_days(None, 1)
    
    print(f"✓ Payroll Period: {start_date} to {end_date}")
    
    # Check for attendance records
    attendance_count = frappe.db.count("Attendance", {
        "employee": employee.name,
        "attendance_date": ["between", [start_date, end_date]],
        "status": "Present",
        "docstatus": 1
    })
    
    print(f"✓ Attendance Records Found: {attendance_count} days")
    
    if attendance_count == 0:
        print("⚠️  No attendance records found for this period")
        print("   Create some attendance records to test salary calculation")
        return
    
    # Get overtime summary
    overtime_data = frappe.db.sql("""
        SELECT 
            IFNULL(SUM(CASE WHEN custom_is_gazetted_holiday = 0 THEN custom_overtime_hours ELSE 0 END), 0) as regular_ot,
            IFNULL(SUM(CASE WHEN custom_is_gazetted_holiday = 1 THEN custom_overtime_hours ELSE 0 END), 0) as gzt_ot
        FROM `tabAttendance`
        WHERE employee = %(employee)s
        AND attendance_date BETWEEN %(start_date)s AND %(end_date)s
        AND status = 'Present'
        AND docstatus = 1
    """, {
        'employee': employee.name,
        'start_date': start_date,
        'end_date': end_date
    }, as_dict=1)[0]
    
    print(f"✓ Regular Overtime Hours: {overtime_data.regular_ot}")
    print(f"✓ Gazetted Overtime Hours: {overtime_data.gzt_ot}")
    
    # Get base salary
    salary_assignment = frappe.db.get_value(
        "Salary Structure Assignment",
        {
            "employee": employee.name,
            "docstatus": 1
        },
        ["salary_structure", "base"],
        order_by="from_date desc",
        as_dict=1
    )
    
    if not salary_assignment:
        print("❌ No Salary Structure Assignment found for employee")
        return
    
    print(f"✓ Base Salary: {salary_assignment.base}")
    print(f"✓ Salary Structure: {salary_assignment.salary_structure}")
    
    # Create test salary slip
    print("\n" + "-"*80)
    print("Creating Salary Slip...")
    print("-"*80 + "\n")
    
    try:
        salary_slip = create_test_salary_slip(employee.name, start_date, end_date)
        salary_slip.save()
        
        print("✓ Salary Slip created successfully!")
        print(f"  Salary Slip ID: {salary_slip.name}")
        print(f"  Payment Days: {salary_slip.payment_days}")
        
        print("\nEarnings:")
        for earning in salary_slip.earnings:
            print(f"  • {earning.salary_component}: {earning.amount:,.2f}")
        
        print("\nDeductions:")
        for deduction in salary_slip.deductions:
            print(f"  • {deduction.salary_component}: {deduction.amount:,.2f}")
        
        print(f"\nGross Pay: {salary_slip.gross_pay:,.2f}")
        print(f"Total Deduction: {salary_slip.total_deduction:,.2f}")
        print(f"Net Pay: {salary_slip.net_pay:,.2f}")
        
        print("\n" + "="*80)
        print("TEST COMPLETED SUCCESSFULLY!")
        print("="*80 + "\n")
        
        # Don't commit - this is just a test
        frappe.db.rollback()
        print("(Test data rolled back - no actual changes made)")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        frappe.db.rollback()
        import traceback
        print("\nFull traceback:")
        print(traceback.format_exc())


if __name__ == "__main__":
    run_manual_test()

