# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Custom Payroll Entry Controller
Adds party details to Receivable/Payable accounts in payroll JV entries
"""

import frappe
from frappe import _
from frappe.utils import flt
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions
import erpnext


class CustomPayrollEntry(PayrollEntry):
	"""
	Extends PayrollEntry to add party details for Receivable/Payable accounts
	
	Only overrides make_accrual_jv_entry to add party information where needed.
	All other methods use standard parent behavior.
	"""
	
	def make_accrual_jv_entry(self, submitted_salary_slips):
		"""
		Create accrual JV with party details for Receivable/Payable accounts
		
		This method replicates parent logic but adds party details to
		Receivable and Payable account entries.
		"""
		self.check_permission("write")
		employee_wise_accounting_enabled = frappe.db.get_single_value(
			"Payroll Settings", "process_payroll_accounting_entry_based_on_employee"
		)
		self.employee_based_payroll_payable_entries = {}
		self._advance_deduction_entries = []

		# Get earnings and deductions with party info
		earnings = self._get_salary_component_total_with_party("earnings", employee_wise_accounting_enabled) or {}
		deductions = self._get_salary_component_total_with_party("deductions", employee_wise_accounting_enabled) or {}

		precision = frappe.get_precision("Journal Entry Account", "debit_in_account_currency")

		if earnings or deductions:
			accounts = []
			currencies = []
			payable_amount = 0
			accounting_dimensions = get_accounting_dimensions() or []
			company_currency = erpnext.get_company_currency(self.company)

			# Process earnings
			for acc_cc, amount in earnings.items():
				# acc_cc might be (account, cost_center) or (account, cost_center, party_type, party)
				payable_amount = self._get_accounting_entry_with_party(
					acc_cc,
					amount,
					currencies,
					company_currency,
					payable_amount,
					accounting_dimensions,
					precision,
					entry_type="debit",
					accounts=accounts,
				)

			# Process deductions
			for acc_cc, amount in deductions.items():
				payable_amount = self._get_accounting_entry_with_party(
					acc_cc,
					amount,
					currencies,
					company_currency,
					payable_amount,
					accounting_dimensions,
					precision,
					entry_type="credit",
					accounts=accounts,
				)

			# Handle advance deductions
			payable_amount = self.set_accounting_entries_for_advance_deductions(
				accounts,
				currencies,
				company_currency,
				accounting_dimensions,
				precision,
				payable_amount,
			)

			# Add payroll payable entry
			self.set_payable_amount_against_payroll_payable_account(
				accounts,
				currencies,
				company_currency,
				accounting_dimensions,
				precision,
				payable_amount,
				self.payroll_payable_account,
				employee_wise_accounting_enabled,
			)

			# Create JV
			self.make_journal_entry(
				accounts,
				currencies,
				self.payroll_payable_account,
				voucher_type="Journal Entry",
				user_remark=_("Accrual Journal Entry for salaries from {0} to {1}").format(
					self.start_date, self.end_date
				),
				submit_journal_entry=True,
				submitted_salary_slips=submitted_salary_slips,
			)
	
	def _get_salary_component_total_with_party(self, component_type, employee_wise_accounting_enabled=False):
		"""
		Get salary component totals with party information for Receivable/Payable accounts
		"""
		salary_components = self.get_salary_components(component_type)
		if not salary_components:
			return None
		
		component_dict = {}
		
		for item in salary_components:
			if not self.should_add_component_to_accrual_jv(component_type, item):
				continue
			
			# Get component account
			account = self.get_salary_component_account(item.salary_component)
			
			# Check if account is Receivable or Payable
			account_type = frappe.db.get_value("Account", account, "account_type", cache=True)
			
			employee_cost_centers = self.get_payroll_cost_centers_for_employee(
				item.employee, item.salary_structure
			)
			employee_advance = self.get_advance_deduction(component_type, item)

			for cost_center, percentage in employee_cost_centers.items():
				amount_against_cost_center = flt(item.amount) * percentage / 100

				if employee_advance:
					self.add_advance_deduction_entry(
						item, amount_against_cost_center, cost_center, employee_advance
					)
				else:
					# Create key - add party info if Receivable/Payable
					if account_type in ["Receivable", "Payable"]:
						key = (item.salary_component, cost_center, account, account_type, item.employee)
					else:
						key = (item.salary_component, cost_center)
					
					component_dict[key] = component_dict.get(key, 0) + amount_against_cost_center

				if employee_wise_accounting_enabled:
					self.set_employee_based_payroll_payable_entries(
						component_type, item.employee, amount_against_cost_center
					)

		# Convert to account dict
		account_details = {}
		for key, amount in component_dict.items():
			if len(key) == 5:
				# Has party info
				component, cost_center, account, account_type, employee = key
				accounting_key = (account, cost_center, account_type, employee)
			else:
				# Standard
				component, cost_center = key
				account = self.get_salary_component_account(component)
				accounting_key = (account, cost_center)
			
			account_details[accounting_key] = account_details.get(accounting_key, 0) + amount

		return account_details
	
	def _get_accounting_entry_with_party(
		self,
		acc_cc,
		amount,
		currencies,
		company_currency,
		payable_amount,
		accounting_dimensions,
		precision,
		entry_type="credit",
		accounts=None,
	):
		"""
		Create accounting entry with party details if needed
		"""
		# Extract account, cost_center, and party info if present
		if len(acc_cc) == 4:
			# Has party info: (account, cost_center, account_type, employee)
			account, cost_center, account_type, employee = acc_cc
			party = employee
			party_type = "Employee"
			
			# Get employee name for narration
			employee_name = frappe.db.get_value("Employee", employee, "employee_name", cache=True)
		else:
			# Standard: (account, cost_center)
			account, cost_center = acc_cc
			party = None
			party_type = None
			employee_name = None
		
		# Call parent method to get the payable amount
		payable_amount = self.get_accounting_entries_and_payable_amount(
			account,
			cost_center or self.cost_center,
			amount,
			currencies,
			company_currency,
			payable_amount,
			accounting_dimensions,
			precision,
			entry_type=entry_type,
			party=party,
			accounts=accounts,
		)
		
		# Add narration to the last added account entry (the one we just added)
		if accounts and len(accounts) > 0:
			last_entry = accounts[-1]
			
			# Build narration based on entry type and party
			if party and employee_name:
				# For party-based accounts, mention employee
				if entry_type == "debit":
					last_entry["user_remark"] = _("{0} - Salary for {1} to {2}").format(
						employee_name, self.start_date, self.end_date
					)
				else:  # credit
					last_entry["user_remark"] = _("{0} - Deduction for {1} to {2}").format(
						employee_name, self.start_date, self.end_date
					)
			else:
				# For standard accounts
				if entry_type == "debit":
					last_entry["user_remark"] = _("Salary expense for {0} to {1}").format(
						self.start_date, self.end_date
					)
				else:  # credit
					last_entry["user_remark"] = _("Salary deduction for {0} to {1}").format(
						self.start_date, self.end_date
					)
		
		return payable_amount
