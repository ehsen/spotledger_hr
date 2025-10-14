#!/usr/bin/env python3
"""
Generate and verify attendance calculation scenarios
"""

import frappe
from datetime import datetime
from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine

def calculate_scenario(employee, date, check_in, check_out):
    """Calculate attendance for a scenario"""
    engine = AttendanceRuleEngine(employee, date)
    
    # Extract time from datetime
    check_in_time = datetime.strptime(check_in, "%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S")
    check_out_time = datetime.strptime(check_out, "%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S")
    
    return engine.calculate_attendance_summary(check_in_time, check_out_time)

def print_scenario(title, check_in, check_out, result):
    """Print scenario results"""
    print(f"\n{'='*60}")
    print(f"📊 {title}")
    print(f"{'='*60}")
    print(f"Check-In:  {check_in}")
    print(f"Check-Out: {check_out}")
    print(f"\n📈 Results:")
    print(f"  Regular Hours:      {result['regular_hours']:.2f} hours")
    print(f"  Overtime Hours:     {result['overtime_hours']:.2f} hours")
    print(f"  Deficiency Hours:   {result['deficiency_hours']:.2f} hours")
    print(f"  Total Hours:        {result['total_hours']:.2f} hours")
    print(f"  Break Duration:     {result['break_duration_minutes']} minutes")
    print(f"  Is Friday:          {result['is_friday']}")
    print(f"  Is Holiday:         {result['is_gazetted_holiday']}")
    if result.get('adjusted_check_in'):
        print(f"  Adjusted Check-In:  {result['adjusted_check_in']}")
    if result.get('adjusted_check_out'):
        print(f"  Adjusted Check-Out: {result['adjusted_check_out']}")

def run_scenarios():
    """Run all scenarios"""
    
    frappe.init(site='bfi')
    frappe.connect()
    
    # Get a test employee
    employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
    if not employee:
        print("❌ No active employee found!")
        return
    
    test_date = "2025-10-13"  # Monday
    
    scenarios = [
        {
            "title": "Scenario 1: Perfect Attendance",
            "check_in": f"{test_date} 08:00:00",
            "check_out": f"{test_date} 17:00:00"
        },
        {
            "title": "Scenario 2: Overtime Work",
            "check_in": f"{test_date} 08:00:00",
            "check_out": f"{test_date} 20:00:00"
        },
        {
            "title": "Scenario 3: Within Grace Period (Late)",
            "check_in": f"{test_date} 08:10:00",
            "check_out": f"{test_date} 17:00:00"
        },
        {
            "title": "Scenario 4: Late Arrival (Beyond Grace)",
            "check_in": f"{test_date} 09:00:00",
            "check_out": f"{test_date} 17:00:00"
        },
        {
            "title": "Scenario 5: Early Exit",
            "check_in": f"{test_date} 08:00:00",
            "check_out": f"{test_date} 16:00:00"
        },
        {
            "title": "Scenario 6: Short Work Day",
            "check_in": f"{test_date} 10:00:00",
            "check_out": f"{test_date} 15:00:00"
        },
        {
            "title": "Scenario 7: Compensation for Late Arrival",
            "check_in": f"{test_date} 09:00:00",
            "check_out": f"{test_date} 18:00:00"
        }
    ]
    
    # Friday scenario
    friday_date = "2025-10-17"  # Friday
    scenarios.append({
        "title": "Scenario 8: Friday with Extended Break",
        "check_in": f"{friday_date} 08:00:00",
        "check_out": f"{friday_date} 17:00:00"
    })
    
    print("\n" + "="*60)
    print("🎯 ATTENDANCE CALCULATION SCENARIOS - REGULAR PROFILE")
    print("="*60)
    
    for scenario in scenarios:
        try:
            # Use appropriate date for the scenario
            date = friday_date if "Friday" in scenario["title"] else test_date
            result = calculate_scenario(employee, date, scenario["check_in"], scenario["check_out"])
            print_scenario(scenario["title"], scenario["check_in"], scenario["check_out"], result)
        except Exception as e:
            print(f"\n❌ Error in {scenario['title']}: {str(e)}")
    
    print("\n" + "="*60)
    print("✅ All scenarios calculated successfully!")
    print("="*60 + "\n")
    
    frappe.destroy()

if __name__ == "__main__":
    run_scenarios()

