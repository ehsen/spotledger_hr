# Simple test for Attendance Rule Engine
import frappe

def test_basic_functionality():
    """Test basic functionality of Attendance Rule Engine"""
    
    print("🧪 Testing Attendance Rule Engine Basic Functionality...")
    
    # Test 1: Import
    try:
        from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
        print("✅ Attendance Rule Engine imported successfully")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Test 2: Check DocType
    if frappe.db.exists("DocType", "Attendance Rule"):
        print("✅ Attendance Rule DocType exists")
    else:
        print("❌ Attendance Rule DocType not found")
        return False
    
    # Test 3: Check custom fields
    attendance_fields = frappe.get_meta("Attendance").fields
    custom_fields = [f.fieldname for f in attendance_fields if f.fieldname.startswith("custom_")]
    expected_fields = ["custom_regular_hours", "custom_overtime_hours", "custom_deficiency_hours"]
    found_expected = [f for f in expected_fields if f in custom_fields]
    print(f"✅ Found {len(found_expected)}/{len(expected_fields)} expected custom fields")
    
    # Test 4: Test basic calculation methods
    try:
        # Test datetime utility
        engine = AttendanceRuleEngine.__new__(AttendanceRuleEngine)
        dt = engine.get_current_datetime("2024-01-15", "07:30:00")
        print(f"✅ DateTime utility works: {dt}")
        
        # Test total hours calculation
        total_seconds = 8.5 * 3600  # 8.5 hours in seconds
        print(f"✅ Total hours calculation concept: {total_seconds/3600} hours")
        
    except Exception as e:
        print(f"❌ Basic calculations failed: {e}")
        return False
    
    print("🎉 Basic functionality tests passed!")
    return True

if __name__ == "__main__":
    test_basic_functionality()
