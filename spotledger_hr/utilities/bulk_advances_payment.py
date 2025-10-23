# Copyright (c) SpotLedger, All rights reserved
# License: GNU General Public License v3.0

import json
import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def create_bulk_payment_entries(employee_advance_names):
	"""
	Create Payment Entries for multiple Employee Advance documents
	
	This function processes multiple Employee Advance records and creates Payment Entries
	for those that are submitted and have Unpaid status. It provides detailed feedback
	on which records were successfully processed and which failed.
	
	Args:
		employee_advance_names: List/JSON string of Employee Advance document names
		
	Returns:
		dict: Contains success, failed, and summary information with the following structure:
			{
				"success": [
					{
						"employee_advance": "EA-001",
						"payment_entry": "PE-00001",
						"amount": 5000,
						"employee": "EMP-001"
					},
					...
				],
				"failed": [
					{
						"employee_advance": "EA-002",
						"reason": "Status is not Unpaid"
					},
					...
				],
				"summary": {
					"total_selected": 5,
					"total_created": 3,
					"total_failed": 2,
					"total_amount": 15000
				}
			}
	
	Raises:
		frappe.PermissionError: If user doesn't have permission to create Payment Entry
	"""
	
	# Parse input if it's a JSON string
	if isinstance(employee_advance_names, str):
		try:
			employee_advance_names = json.loads(employee_advance_names)
		except (json.JSONDecodeError, ValueError):
			frappe.throw(_("Invalid input format. Expected list of Employee Advance names."))
	
	# Permission check - user must have create permission on Payment Entry
	if not frappe.has_permission("Payment Entry", "create"):
		frappe.throw(_("You do not have permission to create Payment Entry"), exc=frappe.PermissionError)
	
	# Initialize result structure
	result = {
		"success": [],
		"failed": [],
		"summary": {
			"total_selected": len(employee_advance_names),
			"total_created": 0,
			"total_failed": 0,
			"total_amount": 0
		}
	}
	
	# Validate input
	if not employee_advance_names:
		frappe.throw(_("Please select at least one Employee Advance"))
	
	# Import helper function from HRMS
	try:
		from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee
	except ImportError:
		frappe.throw(_("HRMS module is required for this feature"))
	
	# Process each Employee Advance
	for ea_name in employee_advance_names:
		try:
			# Get the Employee Advance document
			ea_doc = frappe.get_doc("Employee Advance", ea_name)
			
			# Validation 1: Must be submitted (docstatus = 1)
			if ea_doc.docstatus != 1:
				raise frappe.ValidationError(
					_("Only submitted Employee Advance can be paid. Current status: Draft")
				)
			
			# Validation 2: Must have Unpaid status
			if ea_doc.status != "Unpaid":
				raise frappe.ValidationError(
					_("Only Unpaid Employee Advance can be paid. Current status: {0}").format(ea_doc.status)
				)
			
			# Validation 3: Must have outstanding amount to pay
			outstanding_amount = flt(ea_doc.advance_amount) - flt(ea_doc.paid_amount)
			if outstanding_amount <= 0:
				raise frappe.ValidationError(_("No outstanding amount to pay"))
			
			# Create Payment Entry using HRMS helper function
			pe_doc = get_payment_entry_for_employee("Employee Advance", ea_doc.name)
			pe_doc.insert()
			
			# Track success
			result["success"].append({
				"employee_advance": ea_doc.name,
				"payment_entry": pe_doc.name,
				"amount": outstanding_amount,
				"employee": ea_doc.employee
			})
			result["summary"]["total_created"] += 1
			result["summary"]["total_amount"] += outstanding_amount
			
		except frappe.ValidationError as e:
			# Track validation failure
			result["failed"].append({
				"employee_advance": ea_name,
				"reason": str(e).replace("ValidationError: ", "")
			})
			result["summary"]["total_failed"] += 1
			
		except frappe.DoesNotExistError:
			# Track missing document
			result["failed"].append({
				"employee_advance": ea_name,
				"reason": _("Document not found")
			})
			result["summary"]["total_failed"] += 1
			
		except frappe.PermissionError:
			# Track permission issue
			result["failed"].append({
				"employee_advance": ea_name,
				"reason": _("Access denied")
			})
			result["summary"]["total_failed"] += 1
			
		except Exception as e:
			# Track unexpected error
			result["failed"].append({
				"employee_advance": ea_name,
				"reason": str(e)
			})
			result["summary"]["total_failed"] += 1
	
	return result


def get_unpaid_employee_advances(filters=None):
	"""
	Get list of unpaid Employee Advances for filtering/reporting
	
	Args:
		filters: Additional filters to apply (optional)
		
	Returns:
		list: List of unpaid Employee Advance documents
	"""
	
	base_filters = {
		"docstatus": 1,
		"status": "Unpaid"
	}
	
	if filters:
		base_filters.update(filters)
	
	try:
		advances = frappe.get_list(
			"Employee Advance",
			filters=base_filters,
			fields=["name", "employee", "employee_name", "advance_amount", "paid_amount", "company", "posting_date"],
			order_by="posting_date desc"
		)
		return advances
	except Exception as e:
		frappe.log_error(str(e), "get_unpaid_employee_advances")
		return []


def validate_bulk_payment_selection(employee_advance_names):
	"""
	Validate a selection of Employee Advances for bulk payment processing
	
	Args:
		employee_advance_names: List of Employee Advance names
		
	Returns:
		dict: Validation result with can_process flag and details
	"""
	
	if not employee_advance_names:
		return {
			"can_process": False,
			"message": _("No records selected"),
			"details": []
		}
	
	validation_details = []
	valid_count = 0
	
	for ea_name in employee_advance_names:
		try:
			ea_doc = frappe.get_doc("Employee Advance", ea_name)
			
			# Check if submitted
			if ea_doc.docstatus != 1:
				validation_details.append({
					"name": ea_name,
					"valid": False,
					"reason": "Not submitted"
				})
				continue
			
			# Check if unpaid
			if ea_doc.status != "Unpaid":
				validation_details.append({
					"name": ea_name,
					"valid": False,
					"reason": f"Status is {ea_doc.status}"
				})
				continue
			
			# Check if has outstanding amount
			outstanding = flt(ea_doc.advance_amount) - flt(ea_doc.paid_amount)
			if outstanding <= 0:
				validation_details.append({
					"name": ea_name,
					"valid": False,
					"reason": "No outstanding amount"
				})
				continue
			
			# All checks passed
			validation_details.append({
				"name": ea_name,
				"valid": True,
				"amount": outstanding,
				"employee": ea_doc.employee
			})
			valid_count += 1
			
		except Exception as e:
			validation_details.append({
				"name": ea_name,
				"valid": False,
				"reason": str(e)
			})
	
	return {
		"can_process": valid_count > 0,
		"valid_count": valid_count,
		"invalid_count": len(employee_advance_names) - valid_count,
		"total_count": len(employee_advance_names),
		"details": validation_details
	}
