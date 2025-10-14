#!/usr/bin/env python3
"""Test employee creation to debug the issue"""

import frappe
from spotledger_hr.tests.fixtures.attendance_test_data import TEST_EMPLOYEES, STANDARD_ATTENDANCE_RULE, TEST_HOLIDAY_LIST

frappe.init(site='sites/bfi')
frappe.connect()

try:
    # Create test company
    if not frappe.db.exists("Company", "Test Company"):
        company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Test Company",
            "abbr": "TC",
            "default_currency": "USD"
        })
        company.insert(ignore_permissions=True)
        print("✓ Created Test Company")
    else:
        print("✓ Test Company exists")
    
    # Create holiday list
    if not frappe.db.exists("Holiday List", "Test Holiday List"):
        holiday_list = frappe.get_doc(TEST_HOLIDAY_LIST)
        holiday_list.insert(ignore_permissions=True)
        print("✓ Created Test Holiday List")
    else:
        print("✓ Test Holiday List exists")
    
    # Create attendance rule
    if not frappe.db.exists("Attendance Rule", "Test Company"):
        rule = frappe.get_doc(STANDARD_ATTENDANCE_RULE)
        rule.insert(ignore_permissions=True)
        print("✓ Created Attendance Rule")
    else:
        print("✓ Attendance Rule exists")
    
    # Try to create employee
    emp_data = TEST_EMPLOYEES[0]
    print(f"\nTrying to create employee with data: {emp_data}")
    
    # Check if exists
    existing = frappe.db.get_value("Employee", {"employee_number": emp_data["employee_number"]}, "name")
    if existing:
        print(f"✓ Employee already exists: {existing}")
        emp = frappe.get_doc("Employee", existing)
    else:
        emp = frappe.get_doc({
            "doctype": "Employee",
            "employee_name": emp_data["employee_name"],
            "first_name": emp_data["first_name"],
            "last_name": emp_data["last_name"],
            "company": emp_data["company"],
            "custom_attendance_rule": emp_data["custom_attendance_rule"],
            "gender": emp_data["gender"],
            "date_of_birth": emp_data["date_of_birth"],
            "date_of_joining": emp_data["date_of_joining"],
            "status": emp_data["status"],
            "holiday_list": "Test Holiday List",
            "naming_series": emp_data["naming_series"],
            "employee_number": emp_data["employee_number"]
        })
        emp.insert(ignore_permissions=True)
        print(f"✓ Created employee: {emp.name}, Number: {emp.employee_number}")
    
    # Try to lookup by employee_number
    found_name = frappe.db.get_value("Employee", {"employee_number": emp_data["employee_number"]}, "name")
    print(f"\nLookup by employee_number '{emp_data['employee_number']}': {found_name}")
    
    # Verify holiday list
    if found_name:
        holiday_list, company = frappe.db.get_value("Employee", found_name, ["holiday_list", "company"])
        print(f"Employee holiday_list: {holiday_list}, company: {company}")
    
    frappe.db.rollback()
    print("\n✓ Rolled back changes")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    frappe.db.rollback()

