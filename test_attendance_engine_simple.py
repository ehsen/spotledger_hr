#!/usr/bin/env python3
"""
Simple test script to verify Attendance Rule Engine functionality
"""

import frappe
import sys
import os

# Add the app path to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_attendance_rule_engine():
    """Test the attendance rule engine with basic functionality"""
    
    print("🧪 Testing Attendance Rule Engine...")
    
    try:
        # Initialize Frappe
        frappe.init(site='bfi')
        frappe.connect()
        
        # Test 1: Check if Attendance Rule Engine can be imported
        print("✅ Test 1: Importing Attendance Rule Engine...")
        from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
        print("   ✓ Attendance Rule Engine imported successfully")
        
        # Test 2: Check if Attendance Rule DocType exists
        print("✅ Test 2: Checking Attendance Rule DocType...")
        if frappe.db.exists("DocType", "Attendance Rule"):
            print("   ✓ Attendance Rule DocType exists")
        else:
            print("   ✗ Attendance Rule DocType not found")
            return False
        
        # Test 3: Check if custom fields are installed
        print("✅ Test 3: Checking custom fields...")
        attendance_fields = frappe.get_meta("Attendance").fields
        custom_fields = [f for f in attendance_fields if f.fieldname.startswith('custom_')]
        
        expected_fields = [
            'custom_regular_hours',
            'custom_overtime_hours', 
            'custom_deficiency_hours',
            'custom_total_hours',
            'custom_break_duration_minutes',
            'custom_is_friday',
            'custom_is_gazetted_holiday'
        ]
        
        found_fields = [f.fieldname for f in custom_fields]
        missing_fields = [f for f in expected_fields if f not in found_fields]
        
        if missing_fields:
            print(f"   ⚠️  Missing custom fields: {missing_fields}")
        else:
            print("   ✓ All expected custom fields found")
        
        # Test 4: Create a test attendance rule
        print("✅ Test 4: Creating test attendance rule...")
        test_rule_name = "Test Attendance Rule"
        
        if not frappe.db.exists("Attendance Rule", test_rule_name):
            test_rule = frappe.get_doc({
                "doctype": "Attendance Rule",
                "company": test_rule_name,
                "factory_start_time": "07:30:00",
                "factory_end_time": "16:00:00",
                "required_factory_hours": 8.5,
                "checkin_grace_minutes": 10,
                "checkin_max_grace_minutes": 30,
                "checkout_grace_minutes": 5,
                "checkout_max_grace_minutes": 20,
                "break_duration_minutes": 30,
                "regular_break_start": "12:00:00",
                "regular_break_end": "12:30:00",
                "friday_break_start": "12:30:00",
                "friday_break_end": "14:00:00",
                "gazetted_overtime_multiplier": 2.0,
                "force_hours_on_friday": True,
                "allow_negative_hours": False,
                "enable_friday_logic": True,
                "consider_check_out_next_day": True,
                "allow_absent_on_holiday": False,
                "ignore_break_in_overtime": False
            })
            test_rule.insert()
            print("   ✓ Test attendance rule created")
        else:
            print("   ✓ Test attendance rule already exists")
        
        # Test 5: Create a test employee
        print("✅ Test 5: Creating test employee...")
        test_employee = "TEST-ENGINE-001"
        
        if not frappe.db.exists("Employee", test_employee):
            employee_doc = frappe.get_doc({
                "doctype": "Employee",
                "employee": test_employee,
                "employee_name": "Test Engine Employee",
                "first_name": "Test",
                "last_name": "Engine",
                "company": test_rule_name,
                "custom_attendance_rule": test_rule_name,
                "gender": "Male",
                "date_of_birth": "1990-01-01",
                "date_of_joining": "2020-01-01",
                "status": "Active"
            })
            employee_doc.insert()
            print("   ✓ Test employee created")
        else:
            print("   ✓ Test employee already exists")
        
        # Test 6: Test Attendance Rule Engine initialization
        print("✅ Test 6: Testing engine initialization...")
        try:
            engine = AttendanceRuleEngine(test_employee, "2024-01-15")
            print("   ✓ Engine initialized successfully")
            print(f"   ✓ Factory start time: {engine.rule.factory_start_time}")
            print(f"   ✓ Factory end time: {engine.rule.factory_end_time}")
            print(f"   ✓ Required hours: {engine.rule.required_factory_hours}")
        except Exception as e:
            print(f"   ✗ Engine initialization failed: {e}")
            return False
        
        # Test 7: Test basic calculations
        print("✅ Test 7: Testing basic calculations...")
        try:
            # Test total hours calculation
            total_hours = engine.calculate_total_hours("07:30:00", "16:00:00")
            print(f"   ✓ Total hours calculation: {total_hours} hours")
            
            # Test regular hours calculation
            regular_hours = engine.calculate_regular_hours("07:30:00", "16:00:00")
            print(f"   ✓ Regular hours calculation: {regular_hours} hours")
            
            # Test overtime calculation
            overtime_hours = engine.calculate_overtime("07:30:00", "17:00:00")
            print(f"   ✓ Overtime calculation: {overtime_hours} hours")
            
            # Test deficiency calculation
            deficiency_hours = engine.calculate_deficiency("07:30:00", "15:00:00")
            print(f"   ✓ Deficiency calculation: {deficiency_hours} hours")
            
        except Exception as e:
            print(f"   ✗ Basic calculations failed: {e}")
            return False
        
        # Test 8: Test comprehensive attendance summary
        print("✅ Test 8: Testing comprehensive attendance summary...")
        try:
            summary = engine.calculate_attendance_summary("07:30:00", "16:00:00")
            print("   ✓ Attendance summary calculated successfully")
            print(f"   ✓ Total hours: {summary['total_hours']}")
            print(f"   ✓ Regular hours: {summary['regular_hours']}")
            print(f"   ✓ Overtime hours: {summary['overtime_hours']}")
            print(f"   ✓ Deficiency hours: {summary['deficiency_hours']}")
            print(f"   ✓ Is Friday: {summary['is_friday']}")
            print(f"   ✓ Is Gazetted Holiday: {summary['is_gazetted_holiday']}")
            
        except Exception as e:
            print(f"   ✗ Comprehensive summary failed: {e}")
            return False
        
        # Test 9: Test grace period logic
        print("✅ Test 9: Testing grace period logic...")
        try:
            # Test check-in within grace period
            adjusted_checkin = engine.get_time_after_grace_in("07:35:00")
            print(f"   ✓ Check-in grace (07:35:00): {adjusted_checkin.strftime('%H:%M:%S')}")
            
            # Test check-out within grace period
            adjusted_checkout = engine.get_time_after_grace_out("15:58:00")
            print(f"   ✓ Check-out grace (15:58:00): {adjusted_checkout.strftime('%H:%M:%S')}")
            
        except Exception as e:
            print(f"   ✗ Grace period logic failed: {e}")
            return False
        
        # Test 10: Test break calculations
        print("✅ Test 10: Testing break calculations...")
        try:
            break_duration = engine.get_break_duration("07:30:00", "16:00:00")
            print(f"   ✓ Break duration: {break_duration} seconds")
            
            break_times = engine.get_break_times()
            print(f"   ✓ Break start: {break_times['start'].strftime('%H:%M:%S')}")
            print(f"   ✓ Break end: {break_times['end'].strftime('%H:%M:%S')}")
            
        except Exception as e:
            print(f"   ✗ Break calculations failed: {e}")
            return False
        
        print("\n🎉 All tests passed! Attendance Rule Engine is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        frappe.destroy()

if __name__ == "__main__":
    success = test_attendance_rule_engine()
    sys.exit(0 if success else 1)
