# Copyright (c) 2026, SpotLedger and contributors
# For license information, please see license.txt

"""
Create Salary Slips Tool.
Exposes Payroll Entry create_salary_slips method as a frappe_assistant_core MCP tool.
"""

from typing import Any, Dict
import frappe
from frappe import _
from frappe_assistant_core.core.base_tool import BaseTool


class CreateSalarySlipsTool(BaseTool):
    """
    Tool for creating draft Salary Slips for selected employees on a
    given Payroll Entry.
    """

    def __init__(self):
        super().__init__()
        self.name = "create_salary_slips_tool"
        self.description = (
            "Create draft Salary Slips for the employees registered under a specific "
            "Payroll Entry. If the Payroll Entry has more than 30 employees, the process "
            "is enqueued to run in the background."
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
        """Create draft salary slips for employees"""
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
                "error": f"Insufficient permissions to write/modify Payroll Entry '{payroll_entry}'."
            }

        try:
            doc = frappe.get_doc("Payroll Entry", payroll_entry)

            # Check if salary slips have already been created
            if doc.salary_slips_created:
                return {
                    "success": True,
                    "message": f"Salary slips for Payroll Entry '{payroll_entry}' have already been created."
                }

            # Call the backend method
            doc.create_salary_slips()

            # Reload to get the latest status
            doc.reload()

            if doc.status == "Queued":
                return {
                    "success": True,
                    "queued": True,
                    "message": f"Salary Slip creation for '{payroll_entry}' is queued. It may take a few minutes."
                }

            if doc.salary_slips_created:
                return {
                    "success": True,
                    "message": f"Draft Salary Slips created successfully for '{payroll_entry}'."
                }

            return {
                "success": False,
                "error": f"Failed to create Salary Slips for '{payroll_entry}'. Please check if there are employees assigned to this Payroll Entry."
            }

        except Exception as e:
            frappe.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }


create_salary_slips_tool = CreateSalarySlipsTool
