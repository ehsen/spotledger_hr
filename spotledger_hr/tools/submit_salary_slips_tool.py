# Copyright (c) 2026, SpotLedger and contributors
# For license information, please see license.txt

"""
Submit Salary Slips Tool.
Exposes Payroll Entry submit_salary_slips method as a frappe_assistant_core MCP tool.
"""

from typing import Any, Dict
import frappe
from frappe import _
from frappe_assistant_core.core.base_tool import BaseTool


class SubmitSalarySlipsTool(BaseTool):
    """
    Tool for submitting drafted Salary Slips and creating the accrual
    Journal Entry (JV) for a given Payroll Entry.
    """

    def __init__(self):
        super().__init__()
        self.name = "submit_salary_slips_tool"
        self.description = (
            "Submit all drafted Salary Slips and automatically create the accrual "
            "Journal Entry (JV) for a specific Payroll Entry. "
            "If the Payroll Entry has more than 30 salary slips, the submission "
            "process is enqueued to run in the background."
        )
        self.requires_permission = "Payroll Entry"
        self.source_app = "spotledger_hr"
        self.category = "HR"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "payroll_entry": {
                    "type": "string",
                    "description": "Name/ID of the Payroll Entry (e.g. 'HR-PR-2026-00001').",
                },
            },
            "required": ["payroll_entry"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Submit salary slips and create accrual Journal Entry"""
        payroll_entry = arguments.get("payroll_entry")

        if not payroll_entry:
            return {
                "success": False,
                "error": "The payroll_entry argument is required."
            }

        # Check if the Payroll Entry exists
        if not frappe.db.exists("Payroll Entry", payroll_entry):
            return {
                "success": False,
                "error": f"Payroll Entry '{payroll_entry}' not found."
            }

        # Check user's write permission for this specific Payroll Entry
        if not frappe.has_permission("Payroll Entry", "write", doc=payroll_entry):
            return {
                "success": False,
                "error": f"Insufficient permissions to submit Salary Slips for Payroll Entry '{payroll_entry}'."
            }

        try:
            doc = frappe.get_doc("Payroll Entry", payroll_entry)

            # Check if salary slips have already been submitted
            if doc.salary_slips_submitted:
                return {
                    "success": True,
                    "message": f"Salary slips for Payroll Entry '{payroll_entry}' have already been submitted."
                }

            # Check if salary slips have been created yet
            if not doc.salary_slips_created:
                return {
                    "success": False,
                    "error": f"Salary Slips have not been created for Payroll Entry '{payroll_entry}'. Please create them first."
                }

            # Call the backend method
            doc.submit_salary_slips()
            
            # Reload to get the latest status
            doc.reload()

            if doc.status == "Queued":
                return {
                    "success": True,
                    "queued": True,
                    "message": f"Salary Slip submission for '{payroll_entry}' is queued. It may take a few minutes."
                }

            if doc.salary_slips_submitted:
                return {
                    "success": True,
                    "message": f"Salary Slips submitted and accrual Journal Entry created successfully for '{payroll_entry}'."
                }

            # If it wasn't queued and not submitted, there might be no drafted salary slips to submit
            # or they all failed validation. Let's see if we have drafted slips left
            draft_slips = doc.get_sal_slip_list(ss_status=0)
            if not draft_slips:
                return {
                    "success": False,
                    "error": f"No drafted Salary Slips were found for Payroll Entry '{payroll_entry}' to submit."
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to submit Salary Slips for '{payroll_entry}'. Please check error log or net pay of salary slips."
                }

        except Exception as e:
            frappe.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }


submit_salary_slips_tool = SubmitSalarySlipsTool
