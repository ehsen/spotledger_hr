# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.model.document import Document


def validate_friday_absence_policy(doc, method=None):
    hours = flt(doc.get('friday_absence_deficiency_hours'))
    if hours < 0:
        frappe.throw('Friday absence deficiency hours cannot be negative.')
    if hours > 0 and not doc.get('friday_absence_policy_from_date'):
        frappe.throw('Friday absence policy effective date is required when deficiency hours are positive.')


def validate_final_duration_rounding(doc, method=None):
    if doc.get('final_duration_rounding') and not doc.get('final_duration_rounding_from_date'):
        frappe.throw('Final rounding effective date is required when final rounding is enabled.')


def validate_overnight_tail_credit(doc, method=None):
    if doc.get('overnight_tail_credit') and not doc.get('overnight_tail_credit_from_date'):
        frappe.throw('Tail credit effective date is required when cross-midnight tail credit is enabled.')


class AttendanceRule(Document):
    pass
