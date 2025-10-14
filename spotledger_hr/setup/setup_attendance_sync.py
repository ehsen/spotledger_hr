# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Setup script for Attendance Sync functionality
Creates Attendance Sync Settings DocType
"""

import frappe


def setup_attendance_sync_settings():
    """
    Create Attendance Sync Settings single doctype if it doesn't exist
    """
    
    # Check if DocType exists
    if not frappe.db.exists('DocType', 'Attendance Sync Settings'):
        doc = frappe.get_doc({
            'doctype': 'DocType',
            'name': 'Attendance Sync Settings',
            'module': 'SpotLedger HR',
            'custom': 1,
            'issingle': 1,
            'fields': [
                {
                    'fieldname': 'last_sync_time',
                    'label': 'Last Sync Time',
                    'fieldtype': 'Datetime',
                    'description': 'Last successful sync datetime from external database'
                },
                {
                    'fieldname': 'attendance_db_path',
                    'label': 'Attendance Database Path',
                    'fieldtype': 'Data',
                    'description': 'Relative path to SQLite attendance database from site path'
                },
                {
                    'fieldname': 'enable_auto_sync',
                    'label': 'Enable Auto Sync',
                    'fieldtype': 'Check',
                    'default': '0',
                    'description': 'Enable automatic syncing on schedule'
                },
                {
                    'fieldname': 'sync_frequency_hours',
                    'label': 'Sync Frequency (Hours)',
                    'fieldtype': 'Int',
                    'default': '2',
                    'description': 'Frequency of automatic sync in hours'
                },
                {
                    'fieldname': 'section_break_1',
                    'fieldtype': 'Section Break',
                    'label': 'Statistics'
                },
                {
                    'fieldname': 'total_synced_records',
                    'label': 'Total Synced Records',
                    'fieldtype': 'Int',
                    'read_only': 1,
                    'default': '0'
                },
                {
                    'fieldname': 'last_sync_status',
                    'label': 'Last Sync Status',
                    'fieldtype': 'Select',
                    'options': 'Success\nFailed\nPartial',
                    'read_only': 1
                },
                {
                    'fieldname': 'last_sync_message',
                    'label': 'Last Sync Message',
                    'fieldtype': 'Small Text',
                    'read_only': 1
                }
            ],
            'permissions': [
                {
                    'role': 'System Manager',
                    'read': 1,
                    'write': 1,
                    'create': 1
                },
                {
                    'role': 'HR Manager',
                    'read': 1,
                    'write': 1
                }
            ]
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        print("Attendance Sync Settings DocType created successfully")
    else:
        print("Attendance Sync Settings DocType already exists")


def add_unique_index_for_checkins():
    """
    Add a unique composite index on Employee Checkin for employee + time + log_type
    This ensures we don't create duplicate checkins
    """
    try:
        frappe.db.sql("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_employee_checkin_unique
            ON `tabEmployee Checkin` (employee, time, log_type)
        """)
        frappe.db.commit()
        print("Unique index created for Employee Checkin to prevent duplicates")
    except Exception as e:
        print(f"Note: Could not create unique index (may already exist): {str(e)}")


def execute():
    """
    Main execution function to set up all attendance sync requirements
    """
    print("Setting up Attendance Sync functionality...")
    
    # Create settings doctype
    setup_attendance_sync_settings()
    
    # Add database index to prevent duplicate checkins
    add_unique_index_for_checkins()
    
    print("\n" + "="*60)
    print("Attendance Sync setup completed successfully!")
    print("="*60)
    print("\nNext steps:")
    print("1. Go to Attendance Sync Settings")
    print("2. Set the attendance_db_path (relative to site path)")
    print("3. Configure sync frequency if needed")
    print("4. Run manual sync to test")
    print("\nTo run manual sync from console:")
    print("bench --site [sitename] console")
    print(">>> frappe.call('spotledger_hr.controllers.attendance_controller.sync_attendance', attendance_db_path='/path/to/attendance.db')")
    print("\nOr from UI using frappe.call in browser console")
    print("\nNote: Employee codes in SQLite database should match ERPNext Employee names")


if __name__ == '__main__':
    execute()

