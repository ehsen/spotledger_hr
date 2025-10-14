"""
Test Attendance Controller Integration
"""

import frappe
from frappe.utils import nowdate, add_days, now_datetime
from datetime import datetime, timedelta

def test_attendance_calculation():
    """Test attendance calculation with custom rules"""
    
    frappe.set_user("Administrator")
    
    # Get or create a test employee
    employee = get_test_employee()
    
    # Get or create attendance rule
    attendance_rule = get_test_attendance_rule(employee.company)
    
    # Test attendance calculation
    test_date = nowdate()
    
    # Create test attendance with in_time and out_time
    print("\n" + "="*60)
    print("TESTING ATTENDANCE CALCULATION")
    print("="*60)
    
    # Clean up existing test attendance
    existing = frappe.db.exists("Attendance", {
        "employee": employee.name,
        "attendance_date": test_date
    })
    if existing:
        frappe.delete_doc("Attendance", existing, force=1)
        frappe.db.commit()
    
    # Create new attendance record
    attendance = frappe.new_doc("Attendance")
    attendance.employee = employee.name
    attendance.attendance_date = test_date
    attendance.status = "Present"
    
    # Set manual attendance with custom check-in/check-out times (8:00 AM to 5:00 PM)
    attendance.custom_manual_attendance = 1
    base_datetime = datetime.strptime(test_date, "%Y-%m-%d")
    attendance.custom_check_in_time = base_datetime.replace(hour=8, minute=0, second=0)
    attendance.custom_check_out_time = base_datetime.replace(hour=17, minute=0, second=0)
    
    print(f"\n📝 Creating Attendance for: {employee.employee_name}")
    print(f"   Date: {test_date}")
    print(f"   Manual Attendance: Yes")
    print(f"   Check-In Time: {attendance.custom_check_in_time}")
    print(f"   Check-Out Time: {attendance.custom_check_out_time}")
    
    # Save and validate
    try:
        attendance.save()
        frappe.db.commit()
        
        print(f"\n✅ Attendance saved successfully!")
        print(f"\n📊 Calculated Values:")
        print(f"   Regular Hours: {attendance.custom_regular_hours}")
        print(f"   Overtime Hours: {attendance.custom_overtime_hours}")
        print(f"   Deficiency Hours: {attendance.custom_deficiency_hours}")
        print(f"   Total Hours: {attendance.custom_total_hours}")
        print(f"   Break Duration (mins): {attendance.custom_break_duration_minutes}")
        print(f"   Working Hours: {attendance.working_hours}")
        print(f"   Status: {attendance.status}")
        
        if attendance.custom_adjusted_check_in:
            print(f"   Adjusted Check-In: {attendance.custom_adjusted_check_in}")
        if attendance.custom_adjusted_check_out:
            print(f"   Adjusted Check-Out: {attendance.custom_adjusted_check_out}")
        
        # Verify calculations were performed
        if (attendance.custom_regular_hours > 0 or 
            attendance.custom_overtime_hours > 0 or 
            attendance.custom_deficiency_hours > 0):
            print(f"\n✅ SUCCESS: Attendance rules are being applied!")
            return True
        else:
            print(f"\n⚠️  WARNING: Attendance fields not calculated")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        if attendance.name:
            frappe.delete_doc("Attendance", attendance.name, force=1)
            frappe.db.commit()

def get_test_employee():
    """Get or create a test employee"""
    # Try to find an existing active employee
    employee = frappe.db.get_value("Employee", 
        {"status": "Active"}, 
        ["name", "employee_name", "company"], 
        as_dict=True
    )
    
    if not employee:
        # Create a test employee
        emp = frappe.new_doc("Employee")
        emp.first_name = "Test"
        emp.last_name = "Employee"
        emp.company = frappe.db.get_value("Company", {"is_group": 0})
        emp.status = "Active"
        emp.date_of_joining = add_days(nowdate(), -30)
        emp.save()
        frappe.db.commit()
        employee = frappe._dict({
            "name": emp.name,
            "employee_name": emp.employee_name,
            "company": emp.company
        })
    
    return employee

def get_test_attendance_rule(company):
    """Get or create attendance rule for the company"""
    if frappe.db.exists("Attendance Rule", company):
        return frappe.get_doc("Attendance Rule", company)
    
    # Create default attendance rule
    rule = frappe.new_doc("Attendance Rule")
    rule.company = company
    rule.factory_start_time = "07:30:00"
    rule.factory_end_time = "16:00:00"
    rule.required_factory_hours = 8.5
    rule.checkin_grace_minutes = 10
    rule.checkin_max_grace_minutes = 30
    rule.checkout_grace_minutes = 5
    rule.checkout_max_grace_minutes = 20
    rule.break_duration_minutes = 30
    rule.regular_break_start = "12:00:00"
    rule.regular_break_end = "12:30:00"
    rule.save()
    frappe.db.commit()
    
    return rule

def run():
    """Main test runner"""
    test_attendance_calculation()

