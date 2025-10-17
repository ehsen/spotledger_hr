#!/usr/bin/env python3
"""
Test script for QR Code functionality in Spotledger HR
"""

import frappe
from spotledger_hr.utilities.qr_code_generator import (
    get_qr_code, 
    get_employee_qr_code, 
    get_employee_qr_code_with_legacy_code
)

def test_qr_code_generation():
    """Test basic QR code generation"""
    print("Testing QR Code Generation...")
    
    try:
        # Test basic QR code generation
        test_code = "EMP-001"
        qr_data = get_qr_code(test_code)
        
        if qr_data and qr_data.startswith("data:image/png;base64,"):
            print("✓ Basic QR code generation successful")
        else:
            print("✗ Basic QR code generation failed")
            
    except Exception as e:
        print(f"✗ Error in basic QR code generation: {e}")

def test_employee_qr_code():
    """Test employee QR code generation"""
    print("\nTesting Employee QR Code Generation...")
    
    try:
        # Get first employee for testing
        employees = frappe.get_all("Employee", limit=1)
        
        if employees:
            employee_id = employees[0].name
            print(f"Testing with employee: {employee_id}")
            
            # Test standard QR code
            qr_data = get_employee_qr_code(employee_id)
            if qr_data and qr_data.startswith("data:image/png;base64,"):
                print("✓ Employee QR code generation successful")
            else:
                print("✗ Employee QR code generation failed")
                
            # Test with legacy code
            qr_data_legacy = get_employee_qr_code_with_legacy_code(employee_id)
            if qr_data_legacy and qr_data_legacy.startswith("data:image/png;base64,"):
                print("✓ Employee QR code with legacy code generation successful")
            else:
                print("✗ Employee QR code with legacy code generation failed")
                
        else:
            print("✗ No employees found for testing")
            
    except Exception as e:
        print(f"✗ Error in employee QR code generation: {e}")

def test_api_endpoint():
    """Test API endpoint"""
    print("\nTesting API Endpoint...")
    
    try:
        from spotledger_hr.api.employee_qr_code import get_employee_qr_code_api
        
        # Get first employee for testing
        employees = frappe.get_all("Employee", limit=1)
        
        if employees:
            employee_id = employees[0].name
            print(f"Testing API with employee: {employee_id}")
            
            # Test API endpoint
            result = get_employee_qr_code_api(employee_id, False)
            
            if result.get("status") == "success" and result.get("qr_code"):
                print("✓ API endpoint test successful")
            else:
                print(f"✗ API endpoint test failed: {result}")
                
        else:
            print("✗ No employees found for API testing")
            
    except Exception as e:
        print(f"✗ Error in API endpoint test: {e}")

if __name__ == "__main__":
    # Initialize Frappe
    frappe.init(site="localhost")
    frappe.connect()
    
    print("=== Spotledger HR QR Code Test ===")
    
    test_qr_code_generation()
    test_employee_qr_code()
    test_api_endpoint()
    
    print("\n=== Test Complete ===")
    
    frappe.destroy()


