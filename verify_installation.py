#!/usr/bin/env python3
"""
Verification script for Attendance Rule Engine installation
"""

import frappe

def verify_installation():
    """Verify that the Attendance Rule Engine is properly installed"""
    
    print("🔍 Verifying Attendance Rule Engine Installation...")
    
    try:
        # Check if custom fields were created
        custom_fields = frappe.get_all('Custom Field', 
            filters={'dt': 'Attendance', 'fieldname': ['like', 'custom_%']}, 
            fields=['fieldname', 'label', 'fieldtype']
        )
        
        print(f"✅ Found {len(custom_fields)} custom fields for Attendance:")
        for field in custom_fields:
            print(f"   - {field.fieldname}: {field.label} ({field.fieldtype})")
        
        # Check if Attendance Rule DocType exists
        if frappe.db.exists("DocType", "Attendance Rule"):
            print("✅ Attendance Rule DocType exists")
        else:
            print("❌ Attendance Rule DocType not found")
            return False
        
        # Check if we can import the engine
        try:
            from spotledger_hr.attendance_rule_engine import AttendanceRuleEngine
            print("✅ Attendance Rule Engine can be imported")
        except Exception as e:
            print(f"❌ Cannot import Attendance Rule Engine: {e}")
            return False
        
        # Check if custom controller can be imported
        try:
            from spotledger_hr.controllers.attendance_controller import AttendanceController
            print("✅ Attendance Controller can be imported")
        except Exception as e:
            print(f"❌ Cannot import Attendance Controller: {e}")
            return False
        
        print("\n🎉 Installation verification completed successfully!")
        print("✅ All components are properly installed and ready to use.")
        
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    verify_installation()
