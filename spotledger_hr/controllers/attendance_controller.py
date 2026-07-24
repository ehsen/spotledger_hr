# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Custom Attendance Controller for ERPNext 15 HRMS Integration
Extends ERPNext's Attendance DocType with comprehensive attendance rule calculations
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, add_days
from frappe.exceptions import ValidationError
from hrms.hr.doctype.attendance.attendance import Attendance
try:
    from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
except ImportError:
    AttendanceRuleEngine = None
from typing import Dict, Any, Optional, List
import sqlite3
import datetime
from copy import deepcopy


class AttendanceController(Attendance):
    """Custom Attendance Controller with enhanced calculation logic"""
    
    def validate(self):
        """Validate attendance record and calculate metrics"""
        super().validate()
        
        # Fetch check-in/check-out times from Employee Checkin if not manual
        if not self.custom_manual_attendance:
            self.fetch_checkin_checkout_from_employee_checkin()
        
        # Calculate attendance metrics using our custom fields
        if self.custom_check_in_time and self.custom_check_out_time:
            self.calculate_attendance_metrics()
            self.validate_attendance_data()
    
    def fetch_checkin_checkout_from_employee_checkin(self):
        """Fetch check-in and check-out times from Employee Checkin records"""
        if not self.employee or not self.attendance_date:
            return
        
        # Get Employee Checkin records for this employee and date
        next_date = add_days(self.attendance_date, 0)
        checkins = frappe.get_all(
            "Employee Checkin",
            filters={
                "employee": self.employee,
                "attendance": ["in", ["", None]],  # Not already linked to an attendance
                "time": ["between", [
                    f"{self.attendance_date} 00:00:00",
                    f"{next_date} 23:59:59"
                ]]
            },
            fields=["name", "time", "log_type"],
            order_by="time asc"
        )
        
        if not checkins:
            return
        
        # Find first IN and last OUT
        check_in_record = None
        check_out_record = None
        
        for checkin in checkins:
            if checkin.log_type == "IN" and not check_in_record:
                check_in_record = checkin
            elif checkin.log_type == "OUT":
                check_out_record = checkin
        
        # Set the times
        if check_in_record:
            self.custom_check_in_time = check_in_record.time
        
        if check_out_record:
            self.custom_check_out_time = check_out_record.time
    
    def calculate_attendance_metrics(self):
        """Calculate comprehensive attendance metrics using Attendance Rule Engine"""
        if AttendanceRuleEngine is None:
            frappe.msgprint(_("Attendance Rule Engine not available. Using default values."), 
                          alert=True, indicator='orange')
            self.working_hours = 0
            return
            
        try:
            # Initialize attendance rule engine
            engine = AttendanceRuleEngine(self.employee, self.attendance_date)

            # Get check-in and check-out times from our custom fields
            check_in_time = get_datetime(self.custom_check_in_time).strftime('%H:%M:%S')
            check_out_time = get_datetime(self.custom_check_out_time).strftime('%H:%M:%S')

            # Calculate comprehensive attendance summary
            summary = engine.calculate_attendance_summary(check_in_time, check_out_time)
            
            # Update attendance record with calculated values
            self.update_attendance_fields(summary)
            
        except frappe.ValidationError:
            # Re-raise validation errors (like missing holiday list)
            raise
        except Exception as e:
            # Log other errors but don't block attendance creation
            frappe.log_error(f"Error calculating attendance metrics: {str(e)}", "Attendance Calculation Error")
            # Set default values if calculation fails
            self.working_hours = 0
            frappe.msgprint(_("Could not calculate attendance metrics. Please check attendance rule configuration."), 
                          alert=True, indicator='orange')
    
    def update_attendance_fields(self, summary: Dict[str, Any]):
        """Update attendance record with calculated metrics"""
        # Basic calculated fields - cap values to prevent database errors
        self.custom_regular_hours = min(summary.get('regular_hours', 0), 24)  # Max 24 hours
        self.custom_overtime_hours = min(summary.get('overtime_hours', 0), 24)  # Max 24 hours
        self.custom_deficiency_hours = min(summary.get('deficiency_hours', 0), 24)  # Max 24 hours
        self.custom_total_hours = min(summary.get('total_hours', 0), 48)  # Max 48 hours

        # Break information
        self.custom_break_duration_minutes = min(summary.get('break_duration_minutes', 0), 1440)  # Max 24 hours in minutes
        
        # Day type flags
        self.custom_is_friday = summary.get('is_friday', False)
        self.custom_is_gazetted_holiday = summary.get('is_gazetted_holiday', False)
        
        # Adjusted times
        if summary.get('adjusted_check_in'):
            # Ensure it's a datetime object and convert to string if needed
            check_in_dt = summary['adjusted_check_in']
            if hasattr(check_in_dt, 'strftime'):
                self.custom_adjusted_check_in = check_in_dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                self.custom_adjusted_check_in = str(check_in_dt)[:19]  # Limit string length

        if summary.get('adjusted_check_out'):
            # Ensure it's a datetime object and convert to string if needed
            check_out_dt = summary['adjusted_check_out']
            if hasattr(check_out_dt, 'strftime'):
                self.custom_adjusted_check_out = check_out_dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                self.custom_adjusted_check_out = str(check_out_dt)[:19]  # Limit string length
        
        # Calculate working hours for ERPNext compatibility
        self.working_hours = summary.get('regular_hours', 0)
        
        # Set status based on deficiency
        if summary.get('deficiency_hours', 0) > 0:
            if self.status != 'Absent':
                self.status = 'Present'  # Mark as half day if there's deficiency
        elif summary.get('regular_hours', 0) >= 8.0:  # Assuming 8 hours is full day
            self.status = 'Present'
    
    def validate_attendance_data(self):
        """Validate attendance data for consistency"""
        if self.custom_check_in_time and self.custom_check_out_time:
            check_in_dt = get_datetime(self.custom_check_in_time)
            check_out_dt = get_datetime(self.custom_check_out_time)
            
            # Check if check-out is before check-in (overnight shift)
            if check_out_dt < check_in_dt:
                # This is handled by the engine, but we can add additional validation
                pass
            
            # Validate working hours
            if hasattr(self, 'working_hours') and self.working_hours < 0:
                frappe.throw(_("Working hours cannot be negative. Please check in-time and out-time."))
    
    def on_submit(self):
        """Additional processing on attendance submission"""
        # Note: Parent Attendance class doesn't have on_submit method, so we don't call super()
        
        # Log attendance submission
        frappe.logger().info(f"Attendance submitted for {self.employee} on {self.attendance_date}")
        
        # Trigger any additional workflows if needed
        self.trigger_attendance_workflows()
    
    def trigger_attendance_workflows(self):
        """Trigger additional workflows based on attendance metrics"""
        # Example: Send notifications for excessive overtime or deficiency
        if hasattr(self, 'custom_overtime_hours') and self.custom_overtime_hours > 4:
            self.send_overtime_notification()
        
        if hasattr(self, 'custom_deficiency_hours') and self.custom_deficiency_hours > 2:
            self.send_deficiency_notification()
    
    def send_overtime_notification(self):
        """Send notification for excessive overtime"""
        # Implementation for overtime notification
        pass
    
    def send_deficiency_notification(self):
        """Send notification for excessive deficiency"""
        # Implementation for deficiency notification
        pass


@frappe.whitelist()
def test_attendance_calculation(employee: str, attendance_date: str, check_in_time: str, check_out_time: str) -> Dict[str, Any]:
    """
    Test attendance calculation without creating records
    """
    try:
        from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
        engine = AttendanceRuleEngine(employee, attendance_date)
        summary = engine.calculate_attendance_summary(check_in_time, check_out_time)
        return {'success': True, 'summary': summary}
    except Exception as e:
        frappe.log_error(f"Test failed: {str(e)}", "TEST")
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def calculate_attendance_preview(employee: str, attendance_date: str, check_in_time: str, check_out_time: str) -> Dict[str, Any]:
    """
    Calculate attendance preview without saving
    Useful for frontend validation and preview
    
    Args:
        employee: Employee ID
        attendance_date: Attendance date
        check_in_time: Check-in datetime
        check_out_time: Check-out datetime
    """
    try:
        engine = AttendanceRuleEngine(employee, attendance_date)
        
        # Extract time portion from datetime
        check_in = get_datetime(check_in_time).strftime('%H:%M:%S')
        check_out = get_datetime(check_out_time).strftime('%H:%M:%S')
        
        summary = engine.calculate_attendance_summary(check_in, check_out)
        
        return {
            'success': True,
            'data': summary
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@frappe.whitelist()
def bulk_calculate_attendance(attendance_records: list) -> Dict[str, Any]:
    """
    Bulk calculate attendance for multiple records
    
    Args:
        attendance_records: List of attendance records with check_in_time and check_out_time
    """
    results = []
    errors = []
    
    for record in attendance_records:
        try:
            engine = AttendanceRuleEngine(record['employee'], record['attendance_date'])
            
            # Use custom check-in/check-out fields
            check_in_time = get_datetime(record['check_in_time']).strftime('%H:%M:%S')
            check_out_time = get_datetime(record['check_out_time']).strftime('%H:%M:%S')
            
            summary = engine.calculate_attendance_summary(check_in_time, check_out_time)
            
            results.append({
                'employee': record['employee'],
                'attendance_date': record['attendance_date'],
                'summary': summary
            })
            
        except Exception as e:
            errors.append({
                'employee': record.get('employee', 'Unknown'),
                'attendance_date': record.get('attendance_date', 'Unknown'),
                'error': str(e)
            })
    
    return {
        'success': len(errors) == 0,
        'results': results,
        'errors': errors,
        'total_processed': len(attendance_records),
        'successful': len(results),
        'failed': len(errors)
    }


@frappe.whitelist()
def get_attendance_rule_summary(employee: str) -> Dict[str, Any]:
    """
    Get attendance rule summary for an employee
    """
    try:
        engine = AttendanceRuleEngine(employee, getdate().strftime('%Y-%m-%d'))
        rule = engine.rule
        
        return {
            'success': True,
            'data': {
                'factory_start_time': rule.factory_start_time,
                'factory_end_time': rule.factory_end_time,
                'required_factory_hours': rule.required_factory_hours,
                'checkin_grace_minutes': rule.checkin_grace_minutes,
                'checkin_max_grace_minutes': rule.checkin_max_grace_minutes,
                'checkout_grace_minutes': rule.checkout_grace_minutes,
                'checkout_max_grace_minutes': rule.checkout_max_grace_minutes,
                'break_duration_minutes': rule.break_duration_minutes,
                'regular_break_start': rule.regular_break_start,
                'regular_break_end': rule.regular_break_end,
                'friday_break_start': rule.friday_break_start,
                'friday_break_end': rule.friday_break_end,
                'gazetted_overtime_multiplier': rule.gazetted_overtime_multiplier,
                'force_hours_on_friday': rule.force_hours_on_friday,
                'allow_negative_hours': rule.allow_negative_hours,
                'enable_friday_logic': rule.enable_friday_logic,
                'consider_check_out_next_day': rule.consider_check_out_next_day,
                'allow_absent_on_holiday': rule.allow_absent_on_holiday,
                'ignore_break_in_overtime': rule.ignore_break_in_overtime
            }
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@frappe.whitelist()
def validate_attendance_rule_configuration(company: str) -> Dict[str, Any]:
    """
    Validate attendance rule configuration for a company
    """
    try:
        rule = frappe.get_doc("Attendance Rule", company)
        
        validation_results = []
        
        # Validate basic configuration
        if not rule.factory_start_time:
            validation_results.append("Factory start time is not set")
        
        if not rule.factory_end_time:
            validation_results.append("Factory end time is not set")
        
        if not rule.required_factory_hours:
            validation_results.append("Required factory hours is not set")
        
        # Validate grace periods
        if rule.checkin_grace_minutes > rule.checkin_max_grace_minutes:
            validation_results.append("Check-in grace minutes cannot be greater than max grace minutes")
        
        if rule.checkout_grace_minutes > rule.checkout_max_grace_minutes:
            validation_results.append("Check-out grace minutes cannot be greater than max grace minutes")
        
        # Validate break times
        if rule.regular_break_start and rule.regular_break_end:
            if rule.regular_break_start >= rule.regular_break_end:
                validation_results.append("Regular break start time must be before end time")
        
        if rule.friday_break_start and rule.friday_break_end:
            if rule.friday_break_start >= rule.friday_break_end:
                validation_results.append("Friday break start time must be before end time")
        
        # Validate overtime multiplier
        if rule.gazetted_overtime_multiplier < 1.0:
            validation_results.append("Gazetted overtime multiplier should be at least 1.0")
        
        return {
            'success': len(validation_results) == 0,
            'validation_results': validation_results,
            'is_valid': len(validation_results) == 0
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# ==========================================
# Attendance Sync from External Database
# ==========================================

def fetch_attendance_data_from_sqlite(date_time: str, db_path: str) -> List[Dict]:
    """
    Fetch attendance data from external SQLite database
    
    Args:
        date_time: Last sync datetime to fetch records after this time
        db_path: Path to SQLite database file
        
    Returns:
        List of attendance records from SQLite database
    """
    today_date = datetime.datetime.now().strftime('%d-%m-%Y')
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable dictionary-like access to rows
        cursor = conn.cursor()
        
        # Query to fetch attendance records after last sync time
        query = """
        SELECT * FROM Attendance 
        WHERE DATETIME(SUBSTR(date, 7) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2) || ' ' || check_in) > DATETIME(?)
        AND date NOT LIKE ?
        """
        
        cursor.execute(query, (date_time, f'%{today_date}%'))
        result = cursor.fetchall()
        
        # Convert rows to list of dictionaries
        result_list = [dict(row) for row in result]
        
        
        return result_list
        
    except sqlite3.Error as e:
        frappe.log_error(f"SQLite error: {str(e)}", "Attendance Sync SQLite Error")
        raise
    finally:
        if conn:
            conn.close()


def get_date_from_string(date_str):
    """
    Convert date string to date object
    Handles both string and date object inputs
    """
    if isinstance(date_str, datetime.date):
        return date_str
    elif not isinstance(date_str, datetime.date):
        return datetime.datetime.strptime(date_str, "%d-%m-%Y").date()


def convert_to_datetime(time_str: str, date_str) -> datetime.datetime:
    """Convert time string and date to datetime object"""
    return get_datetime(f"{str(get_date_from_string(date_str))} {time_str}")


def validate_employee_code(employee_code: str) -> Optional[str]:
    """
    Validate employee code and return employee ID
    First checks direct employee name, then checks custom_old_code field
    
    Args:
        employee_code: Employee code from external/legacy system
        
    Returns:
        Employee ID if found, None otherwise
    """
    employee_code_str = str(employee_code)
    
    # First try: Direct employee name lookup
    if frappe.db.exists("Employee", employee_code_str):
        return employee_code_str
    
    # Second try: Check custom_old_code field for legacy system codes
    employee = frappe.db.get_value(
        "Employee",
        filters={"custom_old_code": employee_code_str},
        fieldname="name"
    )
    
    if employee:
        frappe.logger().info(f"Found employee {employee} using custom_old_code: {employee_code_str}")
        return employee
    
    return None


def validate_check_in_time(attendance_dict: Dict) -> Optional[datetime.datetime]:
    """Validate and convert check-in time"""
    atten = frappe._dict(attendance_dict)
    if atten.check_in is None:
        return None
    return convert_to_datetime(atten.check_in, atten.date)


def validate_check_out_time(attendance_dict: Dict) -> Optional[datetime.datetime]:
    """
    Validate and convert check-out time
    Handles overnight shifts by adding a day if check-out is before check-in
    """
    atten = frappe._dict(attendance_dict)
    if atten.check_out is None:
        return None
    
    dt_check_out = convert_to_datetime(atten.check_out, atten.date)
    dt_check_in = validate_check_in_time(attendance_dict)
    
    if isinstance(dt_check_in, datetime.datetime) and isinstance(dt_check_out, datetime.datetime):
        # Handle overnight shift - add a day to checkout if it's before check-in
        if dt_check_out < dt_check_in:
            date_after_addition = add_days(get_date_from_string(atten.date), 1)
            dt_check_out = convert_to_datetime(atten.check_out, date_after_addition)
    
    return dt_check_out


def is_checkin_exists(employee: str, time: datetime.datetime, log_type: str) -> bool:
    """
    Check if Employee Checkin already exists for this employee, time, and log type
    
    Args:
        employee: Employee ID
        time: Check-in/out datetime
        log_type: "IN" or "OUT"
        
    Returns:
        True if exists, False otherwise
    """
    val = frappe.db.get_value(
        "Employee Checkin",
        filters={
            'employee': employee,
            'time': time,
            'log_type': log_type
        }
    )
    return val is not None


def create_employee_checkin_records(atten_dict: frappe._dict) -> Dict[str, Any]:
    """
    Create Employee Checkin records (IN and OUT) from attendance data
    
    Args:
        atten_dict: Attendance dictionary with employee, date, check_in, check_out
        
    Returns:
        Dictionary with success status and created record names
    """
    employee_id = validate_employee_code(atten_dict.employee_code)
    
    if employee_id is None:
        error_msg = f"Employee not found: {atten_dict.employee_code} (tried both employee name and custom_old_code)"
        
        # Log to Error Log (but don't spam for large syncs)
        frappe.log_error(
            error_msg,
            "Attendance Sync - Employee Not Found"
        )
        
        # Don't publish individual messages - will be shown in summary
        
        return {
            'success': False,
            'error': error_msg
        }
    
    created_records = []
    errors = []
    
    # Debug logging
    frappe.logger().debug(f"Creating checkins for employee: {employee_id}")
    frappe.logger().debug(f"Check-in time: {atten_dict.check_in}, Check-out time: {atten_dict.check_out}")
    
    # Create Check-IN record
    if atten_dict.check_in:
        frappe.logger().debug(f"Check-in exists: {is_checkin_exists(employee_id, atten_dict.check_in, 'IN')}")
        if not is_checkin_exists(employee_id, atten_dict.check_in, "IN"):
            try:
                checkin_doc = frappe.get_doc({
                    'doctype': "Employee Checkin",
                    'employee': employee_id,
                    'time': atten_dict.check_in,
                    'log_type': "IN",
                    'custom_attendance_date': atten_dict.date
                })
                checkin_doc.insert(ignore_permissions=True)
                created_records.append({'type': 'IN', 'name': checkin_doc.name})
                frappe.logger().info(f"✅ Created check-in for {employee_id}: {checkin_doc.name}")
            except Exception as e:
                error_msg = f"Error creating check-in for {employee_id} at {atten_dict.check_in}: {str(e)}"
                frappe.logger().error(error_msg)
                frappe.log_error(error_msg, "Attendance Sync - Check-in Creation Error")
                errors.append(error_msg)
        else:
            frappe.logger().debug(f"Skipped check-in (already exists) for {employee_id}")
    else:
        frappe.logger().warning(f"No check-in time for employee {employee_id}")
    
    # Create Check-OUT record
    if atten_dict.check_out:
        frappe.logger().debug(f"Check-out exists: {is_checkin_exists(employee_id, atten_dict.check_out, 'OUT')}")
        if not is_checkin_exists(employee_id, atten_dict.check_out, "OUT"):
            try:
                checkout_doc = frappe.get_doc({
                    'doctype': "Employee Checkin",
                    'employee': employee_id,
                    'time': atten_dict.check_out,
                    'log_type': "OUT",
                    'custom_attendance_date': atten_dict.date
                })
                checkout_doc.insert(ignore_permissions=True)
                created_records.append({'type': 'OUT', 'name': checkout_doc.name})
                frappe.logger().info(f"✅ Created check-out for {employee_id}: {checkout_doc.name}")
            except Exception as e:
                error_msg = f"Error creating check-out for {employee_id} at {atten_dict.check_out}: {str(e)}"
                frappe.logger().error(error_msg)
                frappe.log_error(error_msg, "Attendance Sync - Check-out Creation Error")
                errors.append(error_msg)
        else:
            frappe.logger().debug(f"Skipped check-out (already exists) for {employee_id}")
    else:
        frappe.logger().warning(f"No check-out time for employee {employee_id}")
    
    # Check if we had errors
    if errors:
        return {
            'success': False,
            'employee': employee_id,
            'records': created_records,
            'error': '; '.join(errors)
        }
    
    # Check if we actually created any records
    if len(created_records) == 0:
        warning_msg = f"No checkin records created for {employee_id} (may already exist or missing times)"
        frappe.logger().warning(warning_msg)
        
        # Only treat as error if we expected to create records but didn't
        if atten_dict.check_in or atten_dict.check_out:
            return {
                'success': False,
                'employee': employee_id,
                'records': created_records,
                'error': 'No records created - check if already synced or times are missing'
            }
    
    return {
        'success': True,
        'employee': employee_id,
        'records': created_records
    }


def update_sync_progress(session_id: str, total: int, processed: int, successful: int, failed: int, status: str):
    """Update sync progress in cache for polling"""
    cache_key = f"attendance_sync_progress_{session_id}"
    progress_data = {
        'in_progress': True,
        'total': total,
        'processed': processed,
        'successful': successful,
        'failed': failed,
        'status': status,
        'last_update': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    frappe.cache().set_value(cache_key, progress_data, expires_in_sec=3600)  # 1 hour expiry


def clear_sync_progress(session_id: str):
    """Clear sync progress from cache"""
    cache_key = f"attendance_sync_progress_{session_id}"
    frappe.cache().delete_value(cache_key)


@frappe.whitelist()
def get_sync_progress(session_id: str = None) -> Dict[str, Any]:
    """
    Get current sync progress for polling
    
    Args:
        session_id: Session ID to track progress (defaults to current session)
        
    Returns:
        Progress data or empty dict if no sync in progress
    """
    if not session_id:
        session_id = frappe.session.sid
    
    cache_key = f"attendance_sync_progress_{session_id}"
    progress_data = frappe.cache().get_value(cache_key)
    
    if progress_data:
        return progress_data
    
    return {
        'in_progress': False,
        'total': 0,
        'processed': 0,
        'successful': 0,
        'failed': 0,
        'status': 'No sync in progress'
    }


@frappe.whitelist()
def sync_attendance(attendance_db_path: str, sync_tracker_name: str = None, force_from_date: str = None, batch_size: int = 50) -> Dict[str, Any]:
    """
    Sync attendance data from external SQLite database to Employee Checkin records
    
    Args:
        attendance_db_path: Can be:
            - File URL from upload (e.g., /files/attendance.db)
            - Relative path from site (e.g., /private/files/attendance.db)
            - Absolute path
        sync_tracker_name: Name of sync tracker document (optional, defaults to company name)
        force_from_date: Force sync from specific date (format: YYYY-MM-DD HH:MM:SS), overrides last_sync_time
        batch_size: Number of records to commit at once (default: 50)
        
    Returns:
        Dictionary with sync status and statistics
    """
    try:
        frappe.logger().info(f"sync_attendance called with path: {attendance_db_path}")
        
        # Handle different path formats
        if attendance_db_path.startswith('/files/'):
            # File uploaded via attach field - get actual file path
            db_path = frappe.get_site_path('public', 'files', attendance_db_path.replace('/files/', ''))
            frappe.logger().info(f"Resolved public file path: {db_path}")
        elif attendance_db_path.startswith('/'):
            # Relative path from site root
            db_path = frappe.get_site_path() + attendance_db_path
            frappe.logger().info(f"Resolved site relative path: {db_path}")
        else:
            # Assume it's already a full path or relative to site
            db_path = attendance_db_path
            frappe.logger().info(f"Using provided path: {db_path}")
        
        # Check if file exists
        import os
        if not os.path.exists(db_path):
            error_msg = f"Database file not found at path: {db_path}"
            frappe.logger().error(error_msg)
            frappe.throw(_(error_msg))
        
        # Get last sync time from sync tracker
        if force_from_date:
            last_update = force_from_date
            frappe.publish_realtime(
                'msgprint',
                _("Force syncing from {0}").format(last_update),
                user=frappe.session.user
            )
        else:
            # Try to get last sync time from Attendance Sync Settings
            try:
                last_update = frappe.db.get_single_value('Attendance Sync Settings', 'last_sync_time')
            except Exception:
                # Settings DocType might not exist yet
                last_update = None
            
            if not last_update:
                # If no last sync time, use a default old date
                last_update = "2020-01-01 00:00:00"
                frappe.publish_realtime(
                    'msgprint',
                    _("No last sync time found. Syncing all records from {0}").format(last_update),
                    user=frappe.session.user
                )
        
        current_datetime = datetime.datetime.now()
        
        # Fetch attendance data from SQLite database
        frappe.publish_progress(
            percent=0,
            title=_("Fetching Records"),
            description=_("Reading attendance data from database...")
        )
        
        atten_data_obj = fetch_attendance_data_from_sqlite(last_update, db_path=db_path)
        
        # Statistics
        total_records = len(atten_data_obj)
        
        if total_records == 0:
            frappe.msgprint(
                _("No new records to sync"),
                alert=True,
                indicator='blue'
            )
            return {
                'success': True,
                'total_records': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0,
                'errors': [],
                'last_sync_time': current_datetime.strftime('%Y-%m-%d %H:%M:%S')
            }
        
        successful_syncs = 0
        failed_syncs = 0
        skipped_syncs = 0
        errors = []
        
        # Get session ID for progress tracking
        session_id = frappe.session.sid
        
        # Initialize progress tracking
        update_sync_progress(
            session_id=session_id,
            total=total_records,
            processed=0,
            successful=0,
            failed=0,
            status='Starting sync...'
        )
        
        # Process each attendance record with batch commits
        for index, item in enumerate(atten_data_obj):
            # Show progress with details
            percent = ((index + 1) / total_records * 100)
            
            # Update cache-based progress (for polling)
            update_sync_progress(
                session_id=session_id,
                total=total_records,
                processed=index + 1,
                successful=successful_syncs,
                failed=failed_syncs,
                status=f'Processing record {index + 1} of {total_records}'
            )
            
            # Also try realtime (may not work in background)
            frappe.publish_progress(
                percent=percent,
                title=_("Syncing Attendance Records"),
                description=_("Processing {0} of {1} | Success: {2} | Failed: {3}").format(
                    index + 1, total_records, successful_syncs, failed_syncs
                )
            )
            
            try:
                # Prepare attendance dictionary
                atten_dict = deepcopy(frappe._dict(item))
                atten_dict.check_in = validate_check_in_time(item)
                atten_dict.check_out = validate_check_out_time(item)
                atten_dict.date = get_date_from_string(item.get("date"))
                
                # Create Employee Checkin records
                result = create_employee_checkin_records(atten_dict)
                
                if result['success']:
                    successful_syncs += 1
                else:
                    failed_syncs += 1
                    error_detail = {
                        'employee_code': atten_dict.employee_code,
                        'date': str(atten_dict.date),
                        'error': result.get('error', 'Unknown error')
                    }
                    errors.append(error_detail)
                    
                    # Show error notification every 10 failures or for critical errors
                    if failed_syncs % 10 == 1 or 'not found' in result.get('error', '').lower():
                        frappe.publish_realtime(
                            'msgprint',
                            {
                                'message': f"❌ Failed ({failed_syncs} total): {atten_dict.employee_code} - {result.get('error', 'Unknown')}",
                                'indicator': 'red'
                            },
                            user=frappe.session.user
                        )
                    
            except Exception as e:
                failed_syncs += 1
                error_detail = {
                    'employee_code': item.get('employee_code', 'Unknown'),
                    'date': item.get('date', 'Unknown'),
                    'error': str(e)
                }
                errors.append(error_detail)
                
                frappe.log_error(
                    f"Error processing attendance record: {str(e)}\nRecord: {item}",
                    "Attendance Sync Error"
                )
                
                # Notify about exception
                frappe.publish_realtime(
                    'msgprint',
                    {
                        'message': f"⚠️ Exception processing {item.get('employee_code', 'Unknown')}: {str(e)[:100]}",
                        'indicator': 'orange'
                    },
                    user=frappe.session.user
                )
            
            # Commit in batches for better performance and to save progress
            if (index + 1) % batch_size == 0 or (index + 1) == total_records:
                frappe.db.commit()
                frappe.publish_realtime(
                    'msgprint',
                    _("Saved batch: {0} records processed").format(index + 1),
                    user=frappe.session.user
                )
        
        # Update last sync time
        try:
            # Try to update Attendance Sync Settings if it exists
            if frappe.db.exists('DocType', 'Attendance Sync Settings'):
                frappe.db.set_single_value('Attendance Sync Settings', 'last_sync_time', current_datetime)
                # Update statistics
                try:
                    total_records_so_far = frappe.db.get_single_value('Attendance Sync Settings', 'total_synced_records') or 0
                    frappe.db.set_single_value('Attendance Sync Settings', 'total_synced_records', total_records_so_far + successful_syncs)
                    frappe.db.set_single_value('Attendance Sync Settings', 'last_sync_status', 
                                             'Success' if failed_syncs == 0 else ('Failed' if successful_syncs == 0 else 'Partial'))
                    frappe.db.set_single_value('Attendance Sync Settings', 'last_sync_message', 
                                             f"Synced {successful_syncs} records, {failed_syncs} failed")
                except Exception:
                    pass  # Statistics update is optional
                
                frappe.db.commit()
            else:
                frappe.logger().info(f"Attendance Sync Settings not found. Last sync time: {current_datetime}")
        except Exception as e:
            frappe.log_error(
                f"Error updating last sync time: {str(e)}",
                "Attendance Sync - Update Last Sync Time Error"
            )
        
        # Prepare response
        response = {
            'success': failed_syncs == 0,
            'total_records': total_records,
            'successful': successful_syncs,
            'failed': failed_syncs,
            'skipped': skipped_syncs,
            'errors': errors,
            'last_sync_time': current_datetime.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Final progress update in cache
        update_sync_progress(
            session_id=session_id,
            total=total_records,
            processed=total_records,
            successful=successful_syncs,
            failed=failed_syncs,
            status='Sync completed'
        )
        
        # Also try realtime
        frappe.publish_progress(
            percent=100,
            title=_("Sync Complete"),
            description=_("Processed {0} records | Success: {1} | Failed: {2}").format(
                total_records, successful_syncs, failed_syncs
            )
        )
        
        # Show summary message
        if failed_syncs == 0:
            frappe.publish_realtime(
                'msgprint',
                {
                    'message': _("✅ Successfully synced {0} attendance records").format(successful_syncs),
                    'title': _('Sync Complete'),
                    'indicator': 'green'
                },
                user=frappe.session.user
            )
        else:
            frappe.publish_realtime(
                'msgprint',
                {
                    'message': _("⚠️ Synced {0} records successfully, {1} failed. Check error log for details.").format(
                        successful_syncs, failed_syncs
                    ),
                    'title': _('Sync Complete with Errors'),
                    'indicator': 'orange'
                },
                user=frappe.session.user
            )
        
        # Mark progress as complete and clear after short delay
        frappe.enqueue(
            clear_sync_progress,
            session_id=session_id,
            queue='short',
            timeout=300,
            enqueue_after_commit=True
        )
        
        return response
        
    except Exception as e:
        # Clear progress on error
        try:
            session_id = frappe.session.sid
            update_sync_progress(
                session_id=session_id,
                total=0,
                processed=0,
                successful=0,
                failed=0,
                status=f'Error: {str(e)}'
            )
        except:
            pass
            
        frappe.log_error(f"Attendance sync failed: {str(e)}", "Attendance Sync Error")
        frappe.throw(_("Attendance sync failed: {0}").format(str(e)))


@frappe.whitelist()
def get_sync_status() -> Dict[str, Any]:
    """
    Get current sync status and last sync time
    
    Returns:
        Dictionary with sync status information
    """
    try:
        # Get sync settings if exists
        last_sync_time = None
        total_synced = 0
        sync_status = None
        sync_message = None
        
        if frappe.db.exists('DocType', 'Attendance Sync Settings'):
            try:
                last_sync_time = frappe.db.get_single_value('Attendance Sync Settings', 'last_sync_time')
                total_synced = frappe.db.get_single_value('Attendance Sync Settings', 'total_synced_records') or 0
                sync_status = frappe.db.get_single_value('Attendance Sync Settings', 'last_sync_status')
                sync_message = frappe.db.get_single_value('Attendance Sync Settings', 'last_sync_message')
            except Exception:
                pass
        
        # Get count of recent checkins
        recent_checkins = frappe.db.count(
            'Employee Checkin',
            filters={
                'creation': ['>=', add_days(getdate(), -7)]
            }
        )
        
        # Get total count of checkins
        total_checkins = frappe.db.count('Employee Checkin')
        
        return {
            'success': True,
            'last_sync_time': last_sync_time,
            'total_synced_records': total_synced,
            'last_sync_status': sync_status,
            'last_sync_message': sync_message,
            'recent_checkins_7days': recent_checkins,
            'total_checkins': total_checkins,
            'settings_configured': frappe.db.exists('DocType', 'Attendance Sync Settings')
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
