# Copyright (c) 2026, SpotLedger and contributors
# For license information, please see license.txt

"""
Attendance Checker Tool.
Exposes attendance_rule_tester.calculate_one as a frappe_assistant_core MCP tool.
"""

from typing import Any, Dict

from frappe_assistant_core.core.base_tool import BaseTool

from spotledger_hr.tools.attendance_rule_tester import calculate_one


class AttendanceCheckerTool(BaseTool):
    """
    Tool for calculating regular/overtime/deficiency hours for a single
    check-in/check-out pair via the Attendance Rule Engine, without creating
    any Attendance or Employee Checkin record.
    """

    def __init__(self):
        super().__init__()
        self.name = "attendance_checker_tool"
        self.description = (
            "Calculate regular, overtime, and deficiency hours for one employee "
            "check-in/check-out pair by running it through the Attendance Rule "
            "Engine, without creating any Attendance or Employee Checkin record. "
            "Use to validate the engine's numbers against a manually kept "
            "attendance card, or to answer 'how many hours would this shift count "
            "as' questions."
        )
        self.requires_permission = "Attendance"
        self.source_app = "spotledger_hr"
        self.category = "HR"

        self.inputSchema = {
            "type": "object",
            "properties": {
                "employee": {
                    "type": "string",
                    "description": "Employee ID (e.g. HR-EMP-00128) or the value in the "
                    "employee's custom_old_code field (legacy/biometric device code).",
                },
                "date": {
                    "type": "string",
                    "description": "Attendance date in YYYY-MM-DD format. Used to pick "
                    "Friday/holiday rules from the employee's Attendance Rule.",
                },
                "check_in": {
                    "type": "string",
                    "description": "Check-in time in HH:MM:SS (24-hour).",
                },
                "check_out": {
                    "type": "string",
                    "description": "Check-out time in HH:MM:SS (24-hour). If earlier than "
                    "check_in it is treated as an overnight shift automatically.",
                },
            },
            "required": ["employee", "date", "check_in", "check_out"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate attendance hours for a single check-in/check-out pair"""
        result = calculate_one(
            employee_code=arguments.get("employee"),
            date=arguments.get("date"),
            check_in=arguments.get("check_in"),
            check_out=arguments.get("check_out"),
        )

        if result.get("error"):
            return {"success": False, "error": result["error"], **result}

        return {"success": True, **result}


attendance_checker_tool = AttendanceCheckerTool
