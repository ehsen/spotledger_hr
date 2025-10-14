#!/usr/bin/env python3
"""
Test script to verify grace period logic for attendance calculations
"""
import frappe
from frappe import _
from frappe.utils import get_datetime
from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine

def test_grace_scenarios():
    """Test different grace period scenarios"""
    
    frappe.init(site='bfi')
    frappe.connect()
    
    test_employee = "128"  # Using existing employee
    test_date = "2024-01-15"  # Monday
    
    scenarios = [
        # Format: (check_in, check_out, description)
        ("08:00:00", "17:00:00", "Perfect Attendance (8:00-17:00)"),
        ("08:10:00", "17:10:00", "10 min late, 10 min overtime (within grace)"),
        ("08:15:00", "17:15:00", "15 min late, 15 min overtime (at grace limit)"),
        ("08:20:00", "17:20:00", "20 min late, 20 min overtime (beyond grace, within max)"),
        ("08:30:00", "17:30:00", "30 min late, 30 min overtime (at max grace)"),
        ("08:45:00", "17:45:00", "45 min late, 45 min overtime (beyond max grace)"),
        ("09:00:00", "18:00:00", "60 min late, 60 min overtime (way beyond max)"),
    ]
    
    print("\n" + "="*100)
    print("GRACE PERIOD TESTING")
    print("="*100)
    print("\nRule Configuration:")
    print("  - Factory Hours: 08:00 - 17:00")
    print("  - Required Working Hours: 8.5 hours (net after break)")
    print("  - Break: 30 minutes")
    print("  - Check-in Grace: 15 minutes (forgiveness)")
    print("  - Check-in Max Grace: 30 minutes (cap for late penalty)")
    print("  - Check-out Grace: 15 minutes (forgiveness)")
    print("  - Check-out Max Grace: 30 minutes (cap for overtime)")
    print("\nLogic:")
    print("  CHECK-IN:")
    print("    - Late ≤ 15 min → Adjusted to 08:00 (no penalty)")
    print("    - Late 16-30 min → Adjusted to 08:30 (capped at max grace)")
    print("    - Late > 30 min → Actual time used (full penalty)")
    print("  CHECK-OUT:")
    print("    - Stay ≤ 15 min after 17:00 → Adjusted to 17:00")
    print("    - Stay 16-30 min → Adjusted to 17:30 (capped at max grace)")
    print("    - Stay > 30 min → Actual time used")
    print("\n" + "="*100)
    
    engine = AttendanceRuleEngine(test_employee, test_date)
    
    for check_in, check_out, description in scenarios:
        print(f"\n{description}")
        print(f"  Actual: {check_in} - {check_out}")
        
        summary = engine.calculate_attendance_summary(check_in, check_out)
        
        print(f"  Adjusted: {summary['adjusted_check_in']} - {summary['adjusted_check_out']}")
        print(f"  Regular Hours: {summary['regular_hours']:.2f}")
        print(f"  Overtime: {summary['overtime_hours']:.2f}")
        print(f"  Deficiency: {summary['deficiency_hours']:.2f}")
        print(f"  Total Hours: {summary['total_hours']:.2f}")
        print(f"  Break: {summary['break_duration_minutes']} min")
    
    print("\n" + "="*100)
    print("Test completed!")
    print("="*100 + "\n")
    
    frappe.db.commit()
    frappe.destroy()

if __name__ == "__main__":
    test_grace_scenarios()

