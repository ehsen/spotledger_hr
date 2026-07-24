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
        # For attendance-based employees, calculate salary before standard validation
        if self.should_calculate_from_attendance():
            self.calculate_attendance_based_salary()
        else:
            # For regular employees, ensure earnings/deductions are cleared so parent validation
            # will reload them from salary structure
            if not hasattr(self, '_custom_calculation_done'):
                self.set("earnings", [])
                self.set("deductions", [])

        # Always call parent validation (standard Frappe HRMS flow)
        super().validate()

        # For regular employees, if no components were loaded, add basic salary component
        if not self.should_calculate_from_attendance():
            self.add_basic_salary_component()

        # Ensure tax components are added for both attendance and regular employees
        super().add_tax_components()

    def on_submit(self):
        """Link advance deduction records to salary slip to prevent duplicate application"""
        super().on_submit()
        
        # Link Employee Advance Deduction records to this salary slip
        if self.should_calculate_from_attendance():
            self.link_advance_deductions_to_salary_slip()
    
    def on_cancel(self):
        """Remove salary slip reference from Employee Advance Deduction records when cancelled"""
        super().on_cancel()
        
        # Unlink Employee Advance Deduction records when salary slip is cancelled
        if self.should_calculate_from_attendance():
            self.unlink_advance_deductions_from_salary_slip()
    
    def should_calculate_from_attendance(self):
        """
        Check if employee requires attendance-based salary calculation
        Returns True if custom_generate_salary_based_on_attendance is enabled
        """
        if not self.employee:
            return False

        employee = frappe.get_cached_doc("Employee", self.employee)

        # Check if salary should be generated based on attendance
        return employee.get("custom_generate_salary_based_on_attendance", 0)
    
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
        
        # Get days worked (actual present days from attendance)
        days_worked = attendance_summary.get('days_worked', 0)
        
        # Get payment_days from parent SalarySlip class (already accounts for holidays/leave)
        # This is calculated by the parent class based on leave and attendance
        payment_days_total = self.payment_days if self.payment_days else days_in_month

        # Calculate per day and per hour salary based on payment days (includes holidays)
        per_day_salary = base_salary / days_in_month
        
        # Get required factory hours from employee's attendance rule
        required_hours = self.get_required_factory_hours()
        hourly_rate = self.calculate_hourly_rate(base_salary, days_in_month, required_hours)
        
        # Get overtime multipliers from Attendance Rule
        overtime_multiplier = self.get_overtime_multiplier()
        gzt_overtime_multiplier = self.get_gzt_overtime_multiplier()

        # Calculate gross salary based on days worked
        gross_salary = per_day_salary * payment_days_total

        # Get deficiency hours from attendance records (already calculated by AttendanceRuleEngine)
        deficiency_hours = attendance_summary.get('deficiency_hours', 0)
        deficiency_amount = deficiency_hours * hourly_rate
        
        # Calculate overtime amounts with multipliers
        overtime_hours = attendance_summary.get('overtime_hours', 0)
        gzt_overtime_hours = attendance_summary.get('gzt_overtime_hours', 0)
        overtime_amount = overtime_hours * hourly_rate * overtime_multiplier
        gzt_overtime_amount = gzt_overtime_hours * hourly_rate * gzt_overtime_multiplier
        
        # Get employee advances with IDs for linking to prevent duplicates
        advances_data = self.get_employee_advances_with_ids()
        advances_amount = advances_data['total_amount']
        advances_records = advances_data['records']

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
                'amount':  overtime_amount
            })
        
        if gzt_overtime_amount > 0:
            self.append('earnings', {
                'salary_component': 'Overtime GZT',
                'amount': gzt_overtime_amount
            })
        
        # Add deduction components
        if deficiency_amount > 0:
            self.append('deductions', {
                'salary_component': 'Deficiency',
                'amount': deficiency_amount
            })
        
        if advances_amount > 0:
            self.append('deductions', {
                'salary_component': 'Advances',
                'amount': advances_amount
            })
        
        # Mark that custom calculation has been done
        self._custom_calculation_done = True

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
        Returns dict with days_worked, deficiency_hours, overtime_hours, gzt_overtime_hours
        Note: payment_days is calculated by parent SalarySlip class, not here
        Deficiency is already calculated by AttendanceRuleEngine and stored in custom_deficiency_hours
        """
        # Get days worked (count of Present attendance only)
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
        
        # Get deficiency hours from attendance records (calculated by AttendanceRuleEngine)
        deficiency = frappe.db.sql("""
            SELECT IFNULL(SUM(custom_deficiency_hours), 0) as deficiency_hours
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
            'deficiency_hours': deficiency.get('deficiency_hours', 0),
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
    
    def get_overtime_multiplier(self):
        """
        Get overtime multiplier from employee's attendance rule
        Defaults to 1.0 (no multiplier) if not found
        Used to calculate overtime pay: overtime_hours * hourly_rate * multiplier
        """
        employee = frappe.get_cached_doc("Employee", self.employee)
        attendance_rule_name = employee.get("custom_attendance_rule")
        
        if attendance_rule_name:
            attendance_rule = frappe.get_cached_doc("Attendance Rule", attendance_rule_name)
            multiplier = flt(attendance_rule.overtime_multiplier, 2)
            return multiplier if multiplier > 0 else 1.0
        
        # Default to 1.0 (100%) if no attendance rule
        return 1.0
    
    def get_gzt_overtime_multiplier(self):
        """
        Get gazetted holiday overtime multiplier from employee's attendance rule
        Defaults to 1.0 (no multiplier) if not found
        Used to calculate gazetted overtime pay: gzt_overtime_hours * hourly_rate * multiplier
        """
        employee = frappe.get_cached_doc("Employee", self.employee)
        attendance_rule_name = employee.get("custom_attendance_rule")
        
        if attendance_rule_name:
            attendance_rule = frappe.get_cached_doc("Attendance Rule", attendance_rule_name)
            multiplier = flt(attendance_rule.gazetted_overtime_multiplier, 2)
            return multiplier if multiplier > 0 else 1.0
        
        # Default to 1.0 (100%) if no attendance rule
        return 1.0
    
    def calculate_hourly_rate(self, monthly_salary, days_in_month, required_hours):
        """
        Calculate hourly rate for overtime calculation
        Formula: monthly_salary / (days_in_month × required_factory_hours)
        """
        if days_in_month <= 0 or required_hours <= 0:
            return 0
        
        return monthly_salary / (days_in_month * required_hours)
    
    def link_advance_deductions_to_salary_slip(self):
        """
        Link Employee Advance Deduction records to this salary slip
        This prevents the same advance from being deducted multiple times across payroll periods
        """
        try:
            advances_data = self.get_employee_advances_with_ids()
            advances_records = advances_data['records']
            
            if not advances_records:
                return
            
            # Update each Employee Advance Deduction record with salary slip reference
            for advance in advances_records:
                frappe.db.set_value(
                    'Employee Advance Deduction',
                    advance.get('name'),
                    'salary_slip',
                    self.name,
                    update_modified=False
                )
            
            frappe.db.commit()

        except Exception as e:
            frappe.log_error(
                message=f"Error linking advance deductions: {str(e)}",
                title="Error Linking Advances to Salary Slip"
            )
    
    def unlink_advance_deductions_from_salary_slip(self):
        """
        Remove salary slip reference from Employee Advance Deduction records
        This is called when salary slip is cancelled, allowing advances to be reused
        """
        try:
            # Find all Employee Advance Deduction records linked to this salary slip
            linked_advances = frappe.db.sql("""
                SELECT name
                FROM `tabEmployee Advance Deduction`
                WHERE salary_slip = %(salary_slip)s
                AND docstatus = 1
            """, {
                'salary_slip': self.name
            }, as_dict=1)
            
            if not linked_advances:
                return
            
            # Remove salary slip reference from each record
            for advance in linked_advances:
                frappe.db.set_value(
                    'Employee Advance Deduction',
                    advance.get('name'),
                    'salary_slip',
                    '',
                    update_modified=False
                )
            
            frappe.db.commit()

        except Exception as e:
            frappe.log_error(
                message=f"Error unlinking advance deductions: {str(e)}",
                title="Error Unlinking Advances from Salary Slip"
            )
    
    def get_employee_advances(self):
        """
        Get sum of employee advance deductions for the payroll period
        Fetches from Employee Advance Deduction doctype where posting_date falls within payroll period
        Returns total deduction amount
        """
        advances = frappe.db.sql("""
            SELECT IFNULL(SUM(deduction_amount), 0) as total_advance
            FROM `tabEmployee Advance Deduction`
            WHERE employee = %(employee)s
            AND posting_date BETWEEN %(start_date)s AND %(end_date)s
            AND docstatus = 1
            AND (salary_slip IS NULL OR salary_slip = '')
        """, {
            'employee': self.employee,
            'start_date': self.start_date,
            'end_date': self.end_date
        }, as_dict=1)[0]
        
        return flt(advances.get('total_advance', 0))
    
    def get_employee_advances_with_ids(self):
        """
        Get employee advance deductions for the payroll period along with their IDs for linking
        Returns list of deduction records and total amount
        """
        advances = frappe.db.sql("""
            SELECT name, deduction_amount
            FROM `tabEmployee Advance Deduction`
            WHERE employee = %(employee)s
            AND posting_date BETWEEN %(start_date)s AND %(end_date)s
            AND docstatus = 1
            AND (salary_slip IS NULL OR salary_slip = '')
        """, {
            'employee': self.employee,
            'start_date': self.start_date,
            'end_date': self.end_date
        }, as_dict=1)
        
        total_amount = flt(sum(adv.get('deduction_amount', 0) for adv in advances))
        
        return {
            'records': advances,
            'total_amount': total_amount
        }

    def add_basic_salary_component(self):
        """
        Add basic salary component for regular employees when salary structure has no components
        """
        base_salary = self.get_base_salary_from_structure()

        if base_salary and base_salary > 0:
            # Add basic salary as earning
            self.append('earnings', {
                'salary_component': 'Gross Salary',
                'amount': base_salary
            })

        # Check for employee advances and add as deductions
        advances_data = self.get_employee_advances_with_ids()
        advances_amount = advances_data['total_amount']

        if advances_amount > 0:
            self.append('deductions', {
                'salary_component': 'Advances',
                'amount': advances_amount
            })


    def ensure_tax_components(self):
        """
        Ensure tax components are added to deductions for both attendance and regular employees
        The parent class will handle the actual tax calculation
        """
        try:
            # Only proceed if we have salary structure
            if not self.salary_structure:
                return

            # Set salary structure doc if not already set
            

            # Add tax components using ERPNext's built-in logic
            # This will add tax components to deductions if they don't exist
            #self.add_tax_components()
            self.append('deductions', {
                'salary_component': 'Income Tax',
                'amount': 0
            })

        except Exception as e:
            frappe.log_error(
                message=f"Error ensuring tax components: {str(e)}",
                title="Tax Components Error"
            )


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

