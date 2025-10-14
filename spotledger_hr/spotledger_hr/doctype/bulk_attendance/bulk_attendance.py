# -*- coding: utf-8 -*-
# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, get_datetime, cstr, get_time
from datetime import datetime, timedelta
import json


class BulkAttendance(Document):
    def validate(self):
        if self.from_date and self.to_date and self.from_date > self.to_date:
            frappe.throw("From Date cannot be greater than To Date")
            
    @frappe.whitelist()
    def load_data(self, docname=None):
        """Load employee checkin data based on filters"""
        # Get the document if docname is provided, otherwise use self
        if docname:
            doc = frappe.get_doc("Bulk Attendance", docname)
        else:
            doc = self

        # Load the document to ensure we have the latest data
        doc.reload()

        doc.clear_attendance_data()

        # Get list of employees to process (only those with custom_attendance_required = 1)
        employee_filters = {
            "custom_attendance_required": 1
        }
        if doc.employee:
            employee_filters["name"] = doc.employee
        
        employees = frappe.get_all("Employee", filters=employee_filters, fields=["name", "employee_name", "employee_number"])
        
        if not employees:
            frappe.msgprint("No employees found matching the filter criteria.")
            return {"message": "No employees found", "count": 0}

        # Build filters for Employee Checkin
        checkin_filters = {
            "time": ["between", [doc.get_datetime_from_date(doc.from_date), doc.get_datetime_to_date(doc.to_date)]]
        }

        if doc.employee:
            checkin_filters["employee"] = doc.employee

        # Get all checkin records
        checkin_records = frappe.get_all(
            "Employee Checkin",
            filters=checkin_filters,
            fields=["name", "employee", "employee_name", "time", "log_type", "shift"],
            order_by="employee, time"
        )

        # Group records by employee and date
        employee_date_map = {}
        for record in checkin_records:
            date_key = getdate(record.time).strftime("%Y-%m-%d")
            employee_key = record.employee

            if employee_key not in employee_date_map:
                employee_date_map[employee_key] = {}

            if date_key not in employee_date_map[employee_key]:
                employee_date_map[employee_key][date_key] = {
                    "checkin": None,
                    "checkout": None,
                    "checkin_doc": None,
                    "checkout_doc": None,
                    "employee_name": record.employee_name
                }

            # Take the first IN and last OUT of the day
            if record.log_type == "IN":
                if not employee_date_map[employee_key][date_key]["checkin"]:
                    employee_date_map[employee_key][date_key]["checkin"] = record.time
                    employee_date_map[employee_key][date_key]["checkin_doc"] = record.name
            elif record.log_type == "OUT":
                # Always take the last OUT time
                employee_date_map[employee_key][date_key]["checkout"] = record.time
                employee_date_map[employee_key][date_key]["checkout_doc"] = record.name

        # Generate all dates in the range
        from_date = getdate(doc.from_date)
        to_date = getdate(doc.to_date)
        current_date = from_date
        all_dates = []
        
        while current_date <= to_date:
            all_dates.append(current_date)
            current_date = current_date + timedelta(days=1)

        # Create attendance items for each employee for each day
        for employee in employees:
            employee_id = employee.name
            employee_name = employee.employee_name
            employee_code = employee.employee_number or ""
            
            for date in all_dates:
                date_str = date.strftime("%Y-%m-%d")
                
                # Check if there's attendance data for this employee on this date
                checkin = None
                checkout = None
                checkin_doc = None
                checkout_doc = None
                
                if employee_id in employee_date_map and date_str in employee_date_map[employee_id]:
                    record = employee_date_map[employee_id][date_str]
                    checkin = record["checkin"]
                    checkout = record["checkout"]
                    checkin_doc = record["checkin_doc"]
                    checkout_doc = record["checkout_doc"]

                # Extract date and time components
                check_in_date = None
                check_in_time = None
                check_out_date = None
                check_out_time = None
                
                if checkin:
                    # Ensure we have a datetime object
                    if isinstance(checkin, str):
                        checkin_dt = get_datetime(checkin)
                    else:
                        checkin_dt = checkin
                    
                    # Extract date and time as date/time objects
                    check_in_date = checkin_dt.date() if hasattr(checkin_dt, 'date') else getdate(checkin_dt)
                    check_in_time = checkin_dt.time() if hasattr(checkin_dt, 'time') else get_time(checkin_dt)
                
                if checkout:
                    # Ensure we have a datetime object
                    if isinstance(checkout, str):
                        checkout_dt = get_datetime(checkout)
                    else:
                        checkout_dt = checkout
                    
                    # Extract date and time as date/time objects
                    check_out_date = checkout_dt.date() if hasattr(checkout_dt, 'date') else getdate(checkout_dt)
                    check_out_time = checkout_dt.time() if hasattr(checkout_dt, 'time') else get_time(checkout_dt)
                
                doc.append("attendance_data", {
                    "employee": employee_id,
                    "employee_name": employee_name,
                    "employee_code": employee_code,
                    "day": date,
                    "check_in_date": check_in_date,
                    "check_in_time": check_in_time,
                    "check_out_date": check_out_date,
                    "check_out_time": check_out_time,
                    "checkin_docname": checkin_doc,
                    "checkout_docname": checkout_doc,
                    "original_checkin_time": checkin,
                    "original_checkout_time": checkout,
                    "status": doc.get_status(checkin, checkout)
                })

        # Sort by employee and date
        doc.attendance_data.sort(key=lambda x: (x.employee, x.day))

        # Add serial numbers
        for i, item in enumerate(doc.attendance_data, 1):
            item.idx = i

        # Save the document to persist the data
        doc.save()

        return {"message": f"Successfully loaded {len(doc.attendance_data)} attendance records", "count": len(doc.attendance_data)}

    def get_status(self, checkin, checkout):
        """Determine attendance status"""
        if checkin and checkout:
            return "Present"
        elif checkin or checkout:
            return "Error"
        else:
            return "Absent"

    def get_datetime_from_date(self, date):
        """Get datetime from date (start of day)"""
        return get_datetime(f"{date} 00:00:00")

    def get_datetime_to_date(self, date):
        """Get datetime from date (end of day)"""
        return get_datetime(f"{date} 23:59:59")

    def clear_attendance_data(self):
        """Clear existing attendance data"""
        self.attendance_data = []

    @frappe.whitelist()
    def bulk_update(self, docname=None):
        """Bulk update employee checkin records"""
        # Get the document if docname is provided, otherwise use self
        if docname:
            doc = frappe.get_doc("Bulk Attendance", docname)
        else:
            doc = self

        updated_count = 0

        for item in doc.attendance_data:
            if doc.has_changes(item):
                doc.update_checkin_records(item)
                updated_count += 1

        # Save the document to persist any status changes
        doc.save()

        if updated_count > 0:
            frappe.msgprint(f"Updated {updated_count} records successfully")
            return {"message": f"Successfully updated {updated_count} records"}
        else:
            frappe.msgprint("No changes detected to update")
            return {"message": "No changes to update"}

    def has_changes(self, item):
        """Check if item has changes"""
        # Check checkin changes
        original_checkin = get_datetime(item.original_checkin_time) if item.original_checkin_time else None
        new_checkin = None
        if item.check_in_date and item.check_in_time:
            new_checkin = get_datetime(f"{item.check_in_date} {item.check_in_time}")

        # Check if checkin changed
        if original_checkin != new_checkin:
            return True

        # Check checkout changes
        original_checkout = get_datetime(item.original_checkout_time) if item.original_checkout_time else None
        new_checkout = None
        if item.check_out_date and item.check_out_time:
            new_checkout = get_datetime(f"{item.check_out_date} {item.check_out_time}")

        # Check if checkout changed
        if original_checkout != new_checkout:
            return True

        return False

    def update_checkin_records(self, item):
        """Update checkin records for an employee day"""
        try:
            # Handle checkin record
            if item.check_in_date and item.check_in_time:
                new_checkin_time = get_datetime(f"{item.check_in_date} {item.check_in_time}")

                if item.checkin_docname:
                    # Update existing checkin record
                    frappe.db.set_value("Employee Checkin", item.checkin_docname, "time", new_checkin_time)
                else:
                    # Create new checkin record
                    checkin_doc = frappe.get_doc({
                        "doctype": "Employee Checkin",
                        "employee": item.employee,
                        "log_type": "IN",
                        "time": new_checkin_time
                    })
                    checkin_doc.insert()
                    item.checkin_docname = checkin_doc.name
                    item.original_checkin_time = new_checkin_time
            elif item.checkin_docname and not (item.check_in_date and item.check_in_time):
                # User removed checkin data - delete the record
                frappe.delete_doc("Employee Checkin", item.checkin_docname)
                item.checkin_docname = None
                item.original_checkin_time = None

            # Handle checkout record
            if item.check_out_date and item.check_out_time:
                new_checkout_time = get_datetime(f"{item.check_out_date} {item.check_out_time}")

                if item.checkout_docname:
                    # Update existing checkout record
                    frappe.db.set_value("Employee Checkin", item.checkout_docname, "time", new_checkout_time)
                else:
                    # Create new checkout record
                    checkout_doc = frappe.get_doc({
                        "doctype": "Employee Checkin",
                        "employee": item.employee,
                        "log_type": "OUT",
                        "time": new_checkout_time
                    })
                    checkout_doc.insert()
                    item.checkout_docname = checkout_doc.name
                    item.original_checkout_time = new_checkout_time
            elif item.checkout_docname and not (item.check_out_date and item.check_out_time):
                # User removed checkout data - delete the record
                frappe.delete_doc("Employee Checkin", item.checkout_docname)
                item.checkout_docname = None
                item.original_checkout_time = None

            # Update item status
            item.status = self.get_status(
                get_datetime(f"{item.check_in_date} {item.check_in_time}") if (item.check_in_date and item.check_in_time) else None,
                get_datetime(f"{item.check_out_date} {item.check_out_time}") if (item.check_out_date and item.check_out_time) else None
            )

            # Update original times for reference
            if item.check_in_date and item.check_in_time:
                item.original_checkin_time = get_datetime(f"{item.check_in_date} {item.check_in_time}")
            if item.check_out_date and item.check_out_time:
                item.original_checkout_time = get_datetime(f"{item.check_out_date} {item.check_out_time}")

        except Exception as e:
            frappe.log_error(message=str(e), title=f"Error updating checkin for {item.employee} on {item.day}")
            frappe.throw(f"Error updating attendance for {item.employee_name} on {item.day}: {str(e)}")

    def get_employees_with_missing_data(self):
        """Get employees with missing checkin/checkout data"""
        missing_data = []

        for item in self.attendance_data:
            if item.status in ["Error", "Absent"]:
                missing_data.append({
                    "employee": item.employee,
                    "employee_name": item.employee_name,
                    "day": item.day,
                    "status": item.status,
                    "missing_checkin": not (item.check_in_date and item.check_in_time),
                    "missing_checkout": not (item.check_out_date and item.check_out_time)
                })

        return missing_data
