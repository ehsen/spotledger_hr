# CustomPayrollEntry - Implementation Code Skeleton

## Complete Code Structure with Proper Cancellation Handling

This document provides the complete code skeleton for `payroll_entry_controller.py` with emphasis on proper cancellation logic.

## File: `spotledger_hr/controllers/payroll_entry_controller.py`

```python
# Copyright (c) 2025, SpotLedger and contributors
# For license information, please see license.txt

"""
Custom Payroll Entry Controller
Implements intelligent party detail handling for Receivable/Payable salary components
while maintaining full standard ERPNext HRMS cancellation behavior
"""

import frappe
from frappe import _
from frappe.utils import flt
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry


class CustomPayrollEntry(PayrollEntry):
    """
    Extended Payroll Entry with intelligent handling of Receivable/Payable accounts
    
    Key Features:
    - Automatically detects account types (Receivable, Payable, Expense, etc.)
    - Adds party details (party_type, party) for accounts that require them
    - Maintains complete backward compatibility with standard components
    - Preserves standard ERPNext cancellation logic for salary slips and JVs
    
    Cancellation Behavior:
    - This class does NOT override cancel(), on_cancel(), or related methods
    - Standard parent cancellation logic finds and cancels all JVs via reference fields
    - Salary slips are cancelled through standard parent logic
    - Cancellation works identically for custom and standard salary components
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize with account type cache for performance"""
        super().__init__(*args, **kwargs)
        # Cache for account types to avoid repeated DB queries
        self._account_type_cache = {}
    
    # =========================================================================
    # OVERRIDE: Main JV Creation Method (ONLY method we override)
    # =========================================================================
    
    def make_accrual_jv_entry(self, submitted_salary_slips):
        """
        Override: Create accrual JV with proper party details for Receivable/Payable accounts
        
        IMPORTANT: This method creates JVs that get linked via reference_type and 
        reference_name fields. This linkage enables the standard parent's 
        cancel_linked_journal_entries() method to find and cancel these JVs
        during payroll cancellation.
        
        Args:
            submitted_salary_slips (list[Document]): List of submitted Salary Slip documents
        
        Returns:
            None (creates and submits JV as side effect)
        
        Cancellation Impact:
            When payroll entry is cancelled:
            1. on_cancel() calls cancel_linked_journal_entries()
            2. cancel_linked_journal_entries() queries for JV Account entries with:
               - reference_type = "Payroll Entry"
               - reference_name = self.name
            3. Our custom JVs ARE FOUND because we call self.make_journal_entry()
               which sets these reference fields
            4. All JVs (with or without party details) are cancelled automatically
        """
        try:
            # Step 1: Classify salary components by account type
            components_by_type = self.get_salary_components_by_account_type()
            
            if not components_by_type:
                frappe.log_error(
                    "No salary components found for payroll entry",
                    "CustomPayrollEntry.make_accrual_jv_entry"
                )
                return
            
            # Step 2: Initialize variables for JV creation
            accounts = []
            currencies = []
            
            # Step 3: Process components by account type
            for account_type, components_list in components_by_type.items():
                if self.is_party_required_account(account_type):
                    # Accounts that need party details (Receivable, Payable, Bank)
                    for component in components_list:
                        entry = self.process_party_component(component)
                        accounts.extend(entry)
                else:
                    # Standard accounts (Expense, Income, etc.)
                    for component in components_list:
                        entry = self.process_standard_component(component)
                        accounts.extend(entry)
            
            # Step 4: Add payable amount entry (standard Frappe logic)
            # This matches parent class behavior
            payable_entry = self.create_payable_entry()
            if payable_entry:
                accounts.append(payable_entry)
            
            # Step 5: Create and submit JV
            # CRITICAL: This calls parent's make_journal_entry() which sets:
            #   - reference_type = "Payroll Entry"
            #   - reference_name = self.name
            # These fields are ESSENTIAL for cancellation to work properly
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
            
            frappe.logger().info(
                f"CustomPayrollEntry.make_accrual_jv_entry: "
                f"JV created for {self.name} with party details for {len(accounts)} accounts"
            )
            
        except Exception as e:
            frappe.log_error(
                f"Error in CustomPayrollEntry.make_accrual_jv_entry: {str(e)}",
                "CustomPayrollEntry"
            )
            raise
    
    # =========================================================================
    # DO NOT OVERRIDE THESE METHODS (Standard Cancellation Logic)
    # =========================================================================
    # 
    # ❌ DO NOT override:
    #    - cancel()
    #    - on_cancel()
    #    - delete_linked_salary_slips()
    #    - cancel_linked_journal_entries()
    #    - get_linked_salary_slips()
    #
    # These parent methods handle all cancellation logic:
    # 1. cancel() - Queues or directly cancels based on slip count
    # 2. on_cancel() - Orchestrates the cancellation process
    # 3. delete_linked_salary_slips() - Cancels and deletes all linked salary slips
    # 4. cancel_linked_journal_entries() - Finds and cancels all JVs linked by reference fields
    # 5. get_linked_salary_slips() - Queries for linked salary slips
    #
    # The parent implementation ensures:
    # ✓ All salary slips are cancelled
    # ✓ All JVs are found and cancelled (via reference_type and reference_name)
    # ✓ Status flags are properly reset
    # ✓ No orphaned records remain
    #
    # Our custom JVs with party details are automatically included in cancellation
    # because we use self.make_journal_entry() which sets the required reference fields.
    #
    # =========================================================================
    
    # =========================================================================
    # HELPER METHODS: Detection and Classification
    # =========================================================================
    
    def get_account_type(self, account_name: str) -> str:
        """
        Get account type with caching for performance
        
        Args:
            account_name (str): Name of the account
        
        Returns:
            str: Account type (e.g., "Receivable", "Payable", "Expense", etc.)
        
        Caching:
            Account types are cached in _account_type_cache to avoid repeated
            database queries for the same accounts within a single payroll entry.
        """
        if not account_name:
            return ""
        
        # Check cache first
        if account_name in self._account_type_cache:
            return self._account_type_cache[account_name]
        
        try:
            # Query Account master
            account_type = frappe.db.get_value(
                "Account",
                account_name,
                "account_type",
                cache=True
            ) or ""
            
            # Store in cache
            self._account_type_cache[account_name] = account_type
            
            return account_type
            
        except Exception as e:
            frappe.log_error(
                f"Error getting account type for {account_name}: {str(e)}",
                "CustomPayrollEntry.get_account_type"
            )
            return ""
    
    def get_salary_components_by_account_type(self) -> dict:
        """
        Classify all salary components from submitted salary slips by account type
        
        Returns:
            dict: Dictionary with account types as keys and component lists as values
            Example:
            {
                "Receivable": [
                    {
                        "component": "Advances",
                        "account": "Employee Advances Account",
                        "employee": "HREMP00001",
                        "amount": 5000.00,
                        "parentfield": "deductions",
                        "salary_slip": "SS-2024-001"
                    },
                    ...
                ],
                "Payable": [...],
                "Expense": [...],
                "Other": [...]
            }
        
        Logic:
            1. Get submitted salary slips from current payroll entry
            2. Extract all earnings and deductions components
            3. Get account for each component
            4. Get account type (cached)
            5. Group by account type
            6. Deduplicate to avoid processing same combination multiple times
        """
        components_dict = {}
        processed_combinations = set()
        
        try:
            # Get submitted salary slips
            salary_slips = self.get_sal_slip_list(ss_status=1, as_dict=True)
            
            if not salary_slips:
                frappe.log_error(
                    f"No submitted salary slips found for payroll entry {self.name}",
                    "CustomPayrollEntry.get_salary_components_by_account_type"
                )
                return components_dict
            
            # Iterate through each salary slip and component
            for salary_slip in salary_slips:
                # Process earnings
                for component_detail in salary_slip.earnings or []:
                    self._add_component_to_dict(
                        components_dict,
                        processed_combinations,
                        component_detail,
                        salary_slip,
                        "earnings"
                    )
                
                # Process deductions
                for component_detail in salary_slip.deductions or []:
                    self._add_component_to_dict(
                        components_dict,
                        processed_combinations,
                        component_detail,
                        salary_slip,
                        "deductions"
                    )
            
            return components_dict
            
        except Exception as e:
            frappe.log_error(
                f"Error classifying salary components: {str(e)}",
                "CustomPayrollEntry.get_salary_components_by_account_type"
            )
            return {}
    
    def _add_component_to_dict(self, components_dict, processed_combinations, 
                               component_detail, salary_slip, field_type):
        """
        Helper to add component to classification dict with deduplication
        
        Args:
            components_dict (dict): Main components dictionary
            processed_combinations (set): Set of already processed combinations
            component_detail (obj): Component detail object
            salary_slip (obj): Salary slip document
            field_type (str): "earnings" or "deductions"
        """
        try:
            # Get component account
            account = self.get_salary_component_account(component_detail.salary_component)
            
            # Get account type
            account_type = self.get_account_type(account)
            if not account_type:
                account_type = "Expense"  # Default
            
            # Create unique key to avoid duplicates
            # (We only need to process same component once per account type per slip)
            key = (account_type, component_detail.salary_component, salary_slip.employee)
            
            if key in processed_combinations:
                return  # Skip duplicate
            
            processed_combinations.add(key)
            
            # Add to return dictionary
            if account_type not in components_dict:
                components_dict[account_type] = []
            
            components_dict[account_type].append({
                "component": component_detail.salary_component,
                "account": account,
                "employee": salary_slip.employee,
                "amount": flt(component_detail.amount),
                "parentfield": field_type,
                "salary_slip": salary_slip.name
            })
            
        except Exception as e:
            frappe.log_error(
                f"Error adding component to dict: {str(e)}",
                "CustomPayrollEntry._add_component_to_dict"
            )
    
    def is_party_required_account(self, account_type: str) -> bool:
        """
        Check if an account type requires party details
        
        Args:
            account_type (str): Account type string
        
        Returns:
            bool: True if party details are required, False otherwise
        
        Account Types That Require Party:
            - Receivable: Amounts due FROM someone (e.g., employee advances)
            - Payable: Amounts due TO someone (e.g., creditors)
            - Bank: May represent specific party accounts (handled cautiously)
        
        Account Types That Don't Require Party:
            - Expense: Expense categories (no specific creditor)
            - Income: Revenue categories (no specific debtor)
            - Asset: General assets (no party relationship)
            - Liability: General liabilities (no specific creditor)
            - Equity: Equity accounts (no party)
            - Depreciation: Fixed assets (no party)
        """
        party_required_types = ["Receivable", "Payable", "Bank"]
        return account_type in party_required_types
    
    # =========================================================================
    # PROCESSING METHODS: Create JV Entries
    # =========================================================================
    
    def process_party_component(self, component_data: dict) -> list:
        """
        Create JV entry rows for components with Receivable/Payable accounts
        
        Args:
            component_data (dict): Component information including:
                - component: Salary component name
                - account: GL account
                - employee: Employee ID
                - amount: Amount
                - parentfield: "earnings" or "deductions"
        
        Returns:
            list: List containing JV entry dict with party details
        
        Party Assignment Logic:
            - party_type: Always "Employee" for payroll context
            - party: Employee ID from salary slip
            - Receivable accounts: Credit for deductions (reducing asset)
            - Payable accounts: Debit or Credit based on component type
        
        Important: Entries must not override reference_type/reference_name
        because the parent make_journal_entry() sets these fields for cancellation.
        """
        try:
            entry = {
                "account": component_data["account"],
                "exchange_rate": 1.0,
                "cost_center": self.cost_center or "",
                "project": self.project or "",
                "party_type": "Employee",
                "party": component_data["employee"],
            }
            
            # Determine debit or credit based on component type
            # and whether it's earnings or deduction
            amount = component_data["amount"]
            
            if component_data["parentfield"] == "earnings":
                # Earnings: Typically debit to expense, credit to payable
                # For Receivable: Credit (reduces asset)
                entry["credit_in_account_currency"] = flt(amount)
            else:
                # Deductions: Typically credit to payable
                # For Receivable accounts being deducted: Credit (reduces asset)
                entry["credit_in_account_currency"] = flt(amount)
            
            return [entry]
            
        except Exception as e:
            frappe.log_error(
                f"Error processing party component: {str(e)}",
                "CustomPayrollEntry.process_party_component"
            )
            return []
    
    def process_standard_component(self, component_data: dict) -> list:
        """
        Create JV entry rows for standard components (Expense, Income, etc.)
        
        Args:
            component_data (dict): Component information
        
        Returns:
            list: List containing standard JV entry dict (no party details)
        """
        try:
            amount = component_data["amount"]
            parentfield = component_data["parentfield"]
            
            entry = {
                "account": component_data["account"],
                "exchange_rate": 1.0,
                "cost_center": self.cost_center or "",
                "project": self.project or "",
            }
            
            # Determine debit or credit
            if parentfield == "earnings":
                entry["debit_in_account_currency"] = flt(amount)
            else:
                entry["credit_in_account_currency"] = flt(amount)
            
            return [entry]
            
        except Exception as e:
            frappe.log_error(
                f"Error processing standard component: {str(e)}",
                "CustomPayrollEntry.process_standard_component"
            )
            return []
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def create_payable_entry(self) -> dict:
        """
        Create the payable entry for total salary amount
        
        This entry balances the JV by creating a liability entry for
        the total salary amount to be paid.
        
        Returns:
            dict: Entry dict for payable account or None if no payable needed
        """
        # This is simplified - actual implementation would match parent's logic
        # for calculating total earnings and deductions
        try:
            # Placeholder - actual calculation would go here
            return None
        except Exception as e:
            frappe.log_error(
                f"Error creating payable entry: {str(e)}",
                "CustomPayrollEntry.create_payable_entry"
            )
            return None
    
    def validate_party_details(self, party_type: str, party: str) -> bool:
        """
        Validate party details before creating JV entry
        
        Args:
            party_type (str): Type of party (e.g., "Employee")
            party (str): Party identifier (e.g., employee ID)
        
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            if party_type == "Employee":
                # Verify employee exists
                exists = frappe.db.exists("Employee", party)
                return bool(exists)
            
            return True
            
        except Exception as e:
            frappe.log_error(
                f"Error validating party details: {str(e)}",
                "CustomPayrollEntry.validate_party_details"
            )
            return False


# ============================================================================
# Note on Cancellation Behavior
# ============================================================================
#
# When a CustomPayrollEntry is cancelled:
#
# 1. User clicks "Cancel" button on Payroll Entry
#
# 2. PayrollEntry.cancel() is called (NOT OVERRIDDEN)
#    ├─ Checks if salary slips > 50
#    ├─ If yes: Queues cancellation for background job
#    └─ If no: Calls on_cancel()
#
# 3. PayrollEntry.on_cancel() is called (NOT OVERRIDDEN)
#    ├─ Sets ignore_linked_doctypes
#    ├─ Calls delete_linked_salary_slips()
#    │   ├─ Queries for salary slips with payroll_entry = self.name
#    │   ├─ For each slip:
#    │   │   ├─ If submitted: Cancel it
#    │   │   └─ Delete it
#    │   └─ Result: All salary slips cancelled
#    │
#    ├─ Calls cancel_linked_journal_entries()
#    │   ├─ Queries Journal Entry Account for entries with:
#    │   │   reference_type = "Payroll Entry"
#    │   │   reference_name = self.name
#    │   │   docstatus = 1
#    │   ├─ For each JE found (including our custom JVs with party details):
#    │   │   └─ Cancel it
#    │   └─ Result: ALL journal entries cancelled (standard AND custom)
#    │
#    ├─ Resets flags:
#    │   ├─ salary_slips_created = 0
#    │   ├─ salary_slips_submitted = 0
#    │   ├─ status = "Cancelled"
#    │   └─ error_message = ""
#    │
#    └─ Result: Payroll entry is cancelled
#
# 4. Outcome:
#    ✓ All salary slips cancelled
#    ✓ All journal entries cancelled (including our party-detailed JVs)
#    ✓ All status and error flags reset
#    ✓ No orphaned records
#    ✓ Complete data integrity maintained
#    ✓ User sees standard "Cancelled" message
#
# CRITICAL POINT:
# Our custom JVs with party details ARE FOUND AND CANCELLED
# because we use self.make_journal_entry() which sets reference_type and reference_name.
# These fields are the KEY to making cancellation work for our custom JVs!
#
# ============================================================================
```

## File: Update `spotledger_hr/hooks.py`

Add this to the existing `override_doctype_class` dictionary:

```python
override_doctype_class = {
    "Attendance": "spotledger_hr.controllers.attendance_controller.AttendanceController",
    "Salary Slip": "spotledger_hr.controllers.salary_slip_controller.CustomSalarySlip",
    "Payroll Entry": "spotledger_hr.controllers.payroll_entry_controller.CustomPayrollEntry"  # ← ADD THIS
}
```

## Key Implementation Points

### 1. Override ONLY `make_accrual_jv_entry()`
- This is the ONLY method that needs custom logic
- All cancellation logic is handled by parent class

### 2. Call `self.make_journal_entry()` 
- Parent's method sets reference_type and reference_name
- These fields are ESSENTIAL for cancellation
- Don't create JV entries manually

### 3. Do NOT Override Cancellation Methods
- `cancel()`
- `on_cancel()`
- `delete_linked_salary_slips()`
- `cancel_linked_journal_entries()`
- `get_linked_salary_slips()`

### 4. Use Caching for Performance
- Account types cached in `_account_type_cache`
- Eliminates repeated DB queries

### 5. Error Handling
- Log errors but don't break JV creation
- Default to "Expense" for unknown account types

## Testing Commands

```python
# Test account type detection
entry = frappe.get_doc("Payroll Entry", "PE-2024-001")
print(entry.get_account_type("Employee Advances Account"))

# Test component classification
components = entry.get_salary_components_by_account_type()
print(components.keys())

# Test cancellation
entry.cancel()
print(entry.docstatus)  # Should be 2

# Verify JV was cancelled
jv_list = frappe.get_all("Journal Entry", {"reference_name": entry.name})
for jv_name in jv_list:
    jv = frappe.get_doc("Journal Entry", jv_name)
    print(f"{jv_name}: {jv.docstatus}")  # Should be 2
```

---

**Status**: Ready for Implementation  
**Implementation Time**: 5-6 hours  
**Critical Requirement**: Do NOT override cancellation methods  
**Success Indicator**: JVs with party details are created AND cancelled properly

