# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Custom Salary Slip Controller
Implements attendance-based salary calculation for eligible employees
while maintaining standard Frappe HRMS behavior for others
"""

import frappe
from frappe import _
from frappe.utils import getdate, flt
import calendar
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip


class CustomSalarySlip(SalarySlip):
    """
    Extended Salary Slip controller with attendance-based salary calculation
    """
    
    def validate(self):
        """Override validate to inject attendance-based salary calculation"""
        # Check if employee requires attendance-based salary
        if self.should_calculate_from_attendance():
            # Calculate salary based on attendance before standard validation
            self.calculate_attendance_based_salary()
        
        # Call parent validation (standard Frappe HRMS flow)
        super().validate()
    
    def should_calculate_from_attendance(self):
        """
        Check if employee requires attendance-based salary calculation
        Returns True if both custom flags are enabled
        """
        if not self.employee:
            return False
        
        employee = frappe.get_cached_doc("Employee", self.employee)
        
        # Check both required flags
        attendance_required = employee.get("custom_attendance_required", 0)
        salary_based_on_attendance = employee.get("custom_generate_salary_based_on_attendance", 0)
        
        return attendance_required and salary_based_on_attendance
    
    def calculate_attendance_based_salary(self):
        """
        Main method to calculate salary based on attendance records
        Clears existing components and generates new ones from attendance data
        """
        if not self.start_date or not self.end_date:
            frappe.throw(_("Start Date and End Date are required for attendance-based salary calculation"))
        
        # Get attendance summary
        attendance_summary = self.get_attendance_hours_summary()
        
        # Get base salary from Salary Structure
        base_salary = self.get_base_salary_from_structure()
        
        if not base_salary:
            frappe.msgprint(_("No active Salary Structure found for employee {0}. Using standard calculation.").format(self.employee))
            return
        
        # Calculate days in month
        days_in_month = self.get_days_in_month()
        
        # Get days worked from attendance
        days_worked = attendance_summary.get('days_worked', 0)
        
        # Calculate per day and per hour salary
        per_day_salary = base_salary / days_in_month
        
        # Get required factory hours from employee's attendance rule
        required_hours = self.get_required_factory_hours()
        hourly_rate = self.calculate_hourly_rate(base_salary, days_in_month, required_hours)
        
        # Calculate gross salary based on days worked
        gross_salary = per_day_salary * days_worked
        
        # Calculate overtime amounts
        overtime_amount = attendance_summary.get('overtime_hours', 0) * hourly_rate
        gzt_overtime_amount = attendance_summary.get('gzt_overtime_hours', 0) * hourly_rate
        
        # Get employee advances
        advances = self.get_employee_advances()
        
        # Clear existing earnings and deductions
        self.earnings = []
        self.deductions = []
        
        # Add earnings components
        if gross_salary > 0:
            self.append('earnings', {
                'salary_component': 'Gross Salary',
                'amount': gross_salary
            })
        
        if overtime_amount > 0:
            self.append('earnings', {
                'salary_component': 'Overtime',
                'amount': overtime_amount
            })
        
        if gzt_overtime_amount > 0:
            self.append('earnings', {
                'salary_component': 'Overtime GZT',
                'amount': gzt_overtime_amount
            })
        
        # Add deduction components
        if advances > 0:
            self.append('deductions', {
                'salary_component': 'Advances',
                'amount': advances
            })
        
        # Set additional fields for reference
        self.payment_days = days_worked
        
        # Add custom fields if they exist
        if hasattr(self, 'custom_attendance_based_calculation'):
            self.custom_attendance_based_calculation = 1
    
    def get_base_salary_from_structure(self):
        """
        Get base salary amount from employee's active Salary Structure
        """
        if not self.salary_structure:
            # Try to get active salary structure for employee
            salary_structure = frappe.db.get_value(
                "Salary Structure Assignment",
                {
                    "employee": self.employee,
                    "docstatus": 1,
                    "from_date": ("<=", self.start_date)
                },
                ["salary_structure", "base"],
                order_by="from_date desc",
                as_dict=1
            )
            
            if salary_structure:
                self.salary_structure = salary_structure.salary_structure
                return flt(salary_structure.base)
        else:
            # Get base from salary structure assignment
            base = frappe.db.get_value(
                "Salary Structure Assignment",
                {
                    "employee": self.employee,
                    "salary_structure": self.salary_structure,
                    "docstatus": 1
                },
                "base"
            )
            return flt(base)
        
        return 0
    
    def get_days_in_month(self):
        """
        Get total days in the month of payroll period
        """
        cur_date = getdate(self.start_date)
        return calendar.monthrange(cur_date.year, cur_date.month)[1]
    
    def get_attendance_hours_summary(self):
        """
        Query attendance records and get summary of hours worked
        Returns dict with days_worked, overtime_hours, gzt_overtime_hours
        """
        # Get days worked (count of Present attendance)
        days_worked = frappe.db.sql("""
            SELECT COUNT(*) as days_worked
            FROM `tabAttendance`
            WHERE employee = %(employee)s
            AND attendance_date BETWEEN %(start_date)s AND %(end_date)s
            AND status = 'Present'
            AND docstatus = 1
        """, {
            'employee': self.employee,
            'start_date': self.start_date,
            'end_date': self.end_date
        }, as_dict=1)[0]
        
        # Get regular overtime hours (excluding gazetted holidays)
        overtime = frappe.db.sql("""
            SELECT IFNULL(SUM(custom_overtime_hours), 0) as overtime_hours
            FROM `tabAttendance`
            WHERE employee = %(employee)s
            AND attendance_date BETWEEN %(start_date)s AND %(end_date)s
            AND status = 'Present'
            AND (custom_is_gazetted_holiday = 0 OR custom_is_gazetted_holiday IS NULL)
            AND docstatus = 1
        """, {
            'employee': self.employee,
            'start_date': self.start_date,
            'end_date': self.end_date
        }, as_dict=1)[0]
        
        # Get gazetted overtime hours
        gzt_overtime = frappe.db.sql("""
            SELECT IFNULL(SUM(custom_overtime_hours), 0) as gzt_overtime_hours
            FROM `tabAttendance`
            WHERE employee = %(employee)s
            AND attendance_date BETWEEN %(start_date)s AND %(end_date)s
            AND status = 'Present'
            AND custom_is_gazetted_holiday = 1
            AND docstatus = 1
        """, {
            'employee': self.employee,
            'start_date': self.start_date,
            'end_date': self.end_date
        }, as_dict=1)[0]
        
        return {
            'days_worked': days_worked.get('days_worked', 0),
            'overtime_hours': overtime.get('overtime_hours', 0),
            'gzt_overtime_hours': gzt_overtime.get('gzt_overtime_hours', 0)
        }
    
    def get_required_factory_hours(self):
        """
        Get required factory hours from employee's attendance rule
        Defaults to 8 hours if not found
        """
        employee = frappe.get_cached_doc("Employee", self.employee)
        attendance_rule_name = employee.get("custom_attendance_rule")
        
        if attendance_rule_name:
            attendance_rule = frappe.get_cached_doc("Attendance Rule", attendance_rule_name)
            return flt(attendance_rule.required_factory_hours, 2)
        
        # Default to 8 hours if no attendance rule
        return 8.0
    
    def calculate_hourly_rate(self, monthly_salary, days_in_month, required_hours):
        """
        Calculate hourly rate for overtime calculation
        Formula: monthly_salary / (days_in_month × required_factory_hours)
        """
        if days_in_month <= 0 or required_hours <= 0:
            return 0
        
        return monthly_salary / (days_in_month * required_hours)
    
    def get_employee_advances(self):
        """
        Get sum of employee advances for the payroll period
        """
        advances = frappe.db.sql("""
            SELECT IFNULL(SUM(advance_amount), 0) as total_advance
            FROM `tabEmployee Advance`
            WHERE employee = %(employee)s
            AND posting_date BETWEEN %(start_date)s AND %(end_date)s
            AND docstatus = 1
        """, {
            'employee': self.employee,
            'start_date': self.start_date,
            'end_date': self.end_date
        }, as_dict=1)[0]
        
        return flt(advances.get('total_advance', 0))


# Helper functions for compatibility with legacy code
def get_days_in_month(date):
    """Get total days in month for given date"""
    cur_date = getdate(date)
    return calendar.monthrange(cur_date.year, cur_date.month)[1]


def per_day_salary(monthly_salary: float, payroll_start_date) -> float:
    """Calculate per day salary"""
    return monthly_salary / get_days_in_month(payroll_start_date)


def per_hour_salary(per_day_salary: float, required_hours: float = 8.0) -> float:
    """Calculate per hour salary"""
    return per_day_salary / required_hours


def salary_as_per_days_worked(per_day_salary: float, days_worked: int) -> float:
    """Calculate salary based on days worked"""
    return per_day_salary * days_worked

