# Payroll Entry Cancellation Logic - Implementation Addendum

## Overview
This document clarifies the cancellation behavior for CustomPayrollEntry to ensure standard ERPNext HRMS cancellation logic is preserved while implementing custom JV creation with party details.

## Critical Requirement
**When CustomPayrollEntry is cancelled, the standard cancellation flow MUST be maintained:**
- All associated Salary Slips are cancelled
- All associated Journal Entries are cancelled
- Status flags are reset properly
- Error messages are cleared

## Current ERPNext PayrollEntry Cancellation Flow

### Standard Methods in PayrollEntry:

```python
def cancel(self):
    """Queue or directly cancel based on salary slip count"""
    if len(self.get_linked_salary_slips()) > 50:
        # Queue for background processing
        self.queue_action("cancel", timeout=3000)
    else:
        # Direct cancellation
        self._cancel()

def on_cancel(self):
    """Executed during cancellation"""
    self.ignore_linked_doctypes = ("GL Entry", "Salary Slip", "Journal Entry")
    self.delete_linked_salary_slips()
    self.cancel_linked_journal_entries()
    
    # Reset flags
    self.db_set("salary_slips_created", 0)
    self.db_set("salary_slips_submitted", 0)
    self.set_status(update=True, status="Cancelled")
    self.db_set("error_message", "")

def delete_linked_salary_slips(self):
    """Cancel and delete salary slips"""
    salary_slips = self.get_linked_salary_slips()
    for salary_slip in salary_slips:
        if salary_slip.docstatus == 1:
            frappe.get_doc("Salary Slip", salary_slip.name).cancel()
        frappe.delete_doc("Salary Slip", salary_slip.name)

def cancel_linked_journal_entries(self):
    """Cancel journal entries linked to payroll entry"""
    journal_entries = frappe.get_all(
        "Journal Entry Account",
        {"reference_type": self.doctype, "reference_name": self.name, "docstatus": 1},
        pluck="parent",
        distinct=True,
    )
    for je in journal_entries:
        frappe.get_doc("Journal Entry", je).cancel()
```

## CustomPayrollEntry Cancellation Strategy

### DO NOT Override These Methods:
```python
# ❌ DON'T override these:
def cancel(self):
def on_cancel(self):
def delete_linked_salary_slips(self):
def cancel_linked_journal_entries(self):
def get_linked_salary_slips(self):
```

**Reason**: Parent methods handle all cancellation logic properly. Our custom logic should NOT interfere with this.

### ONLY Override:
```python
# ✅ Only override this:
def make_accrual_jv_entry(self, submitted_salary_slips):
```

**Reason**: This is where JV creation happens. Only customize here for party details.

## Implementation Pattern: Safe Override

### ✅ CORRECT Approach:

```python
class CustomPayrollEntry(PayrollEntry):
    """
    Custom PayrollEntry with intelligent party details handling
    for Receivable/Payable accounts
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._account_type_cache = {}
    
    # ✅ OVERRIDE ONLY THIS
    def make_accrual_jv_entry(self, submitted_salary_slips):
        """
        Override: Create accrual JV with party details for Receivable/Payable accounts
        
        This method is called after salary slips are submitted and creates
        the corresponding journal entry. We override it to add party details
        for accounts that require them (Receivable, Payable).
        
        The standard cancellation flow still works because:
        - cancel() method calls on_cancel()
        - on_cancel() calls cancel_linked_journal_entries()
        - cancel_linked_journal_entries() cancels all JVs linked via reference_type/reference_name
        - Our custom JV has the same reference fields, so gets cancelled automatically
        """
        # Get components by account type
        components_by_type = self.get_salary_components_by_account_type()
        
        # Process components and build accounts list
        accounts = []
        currencies = []
        
        for account_type, components_list in components_by_type.items():
            if self.is_party_required_account(account_type):
                # Receivable/Payable accounts - ADD PARTY DETAILS
                for component in components_list:
                    entries = self.process_party_component(component)
                    accounts.extend(entries)
            else:
                # Standard accounts - USE NORMAL LOGIC
                for component in components_list:
                    entries = self.process_standard_component(component)
                    accounts.extend(entries)
        
        # Create JV with all entries
        # The make_journal_entry() method sets:
        #   - reference_type = "Payroll Entry"
        #   - reference_name = self.name
        # These fields allow cancel_linked_journal_entries() to find and cancel this JV
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
    
    # ✅ ADD HELPER METHODS (don't override parent)
    def get_account_type(self, account_name: str) -> str:
        """Get and cache account type"""
        # Implementation...
        pass
    
    def get_salary_components_by_account_type(self) -> dict:
        """Classify components by account type"""
        # Implementation...
        pass
    
    # ... other helper methods
    
    # ❌ DO NOT ADD/OVERRIDE THESE:
    # - cancel()
    # - on_cancel()
    # - delete_linked_salary_slips()
    # - cancel_linked_journal_entries()
    # Let parent class handle all cancellation logic!
```

### ❌ INCORRECT Approaches (DO NOT DO THESE):

**Mistake 1: Overriding cancel() or on_cancel()**
```python
# ❌ WRONG - Don't do this!
def on_cancel(self):
    # Your code here
    super().on_cancel()  # ← May cause issues with cancellation order
```

**Mistake 2: Modifying cancellation without calling parent**
```python
# ❌ WRONG - Don't do this!
def cancel_linked_journal_entries(self):
    # Custom logic that skips parent
    # ← JVs won't be cancelled!
```

**Mistake 3: Breaking reference fields in JV**
```python
# ❌ WRONG - Don't do this!
def make_journal_entry(self, accounts, ...):
    # Remove or change reference_type/reference_name
    # ← Cancellation won't find JV to cancel it!
```

## Cancellation Flow with CustomPayrollEntry

```
Payroll Entry Cancel Button Clicked
    ↓
PayrollEntry.cancel() [NOT OVERRIDDEN - uses parent]
    ↓
    ├─ Check if salary slips > 50
    │   ├─ Yes → Queue for background job
    │   └─ No → Continue to on_cancel()
    │
    └─ Call on_cancel() [NOT OVERRIDDEN - uses parent]
        ↓
        on_cancel():
        ├─ Set ignore_linked_doctypes
        ├─ Call delete_linked_salary_slips() [NOT OVERRIDDEN]
        │   └─ For each salary slip:
        │       ├─ If submitted: cancel it
        │       └─ Delete it
        │
        ├─ Call cancel_linked_journal_entries() [NOT OVERRIDDEN]
        │   ├─ Query: Find all JE Account rows with
        │   │   reference_type = "Payroll Entry"
        │   │   reference_name = self.name
        │   │
        │   └─ For each JE found:
        │       └─ Cancel it ✓ (Our custom JV IS FOUND AND CANCELLED)
        │
        ├─ db_set("salary_slips_created", 0)
        ├─ db_set("salary_slips_submitted", 0)
        ├─ set_status("Cancelled")
        └─ db_set("error_message", "")

Result:
    ✓ All salary slips cancelled
    ✓ All journal entries cancelled (including our custom JV with party details)
    ✓ Status reset
    ✓ No orphaned records
    ✓ Complete data integrity
```

## Key Points for CustomPayrollEntry

### 1. Override make_accrual_jv_entry() ONLY

```python
def make_accrual_jv_entry(self, submitted_salary_slips):
    """
    ONLY override this method.
    Call self.make_journal_entry() at the end (which sets reference fields).
    """
    # Our custom logic here
    self.make_journal_entry(...)  # Sets reference_type and reference_name
```

### 2. Reference Fields are CRITICAL for Cancellation

The `make_journal_entry()` method we call sets:
```python
# In make_journal_entry():
# When entry_type == "payable" or voucher_type == "Journal Entry":
row.update({
    "reference_type": self.doctype,      # = "Payroll Entry"
    "reference_name": self.name,         # = Payroll Entry name
})
```

These fields enable `cancel_linked_journal_entries()` to find our JV:
```python
# In cancel_linked_journal_entries():
journal_entries = frappe.get_all(
    "Journal Entry Account",
    {
        "reference_type": self.doctype,        # Matches our "Payroll Entry"
        "reference_name": self.name,           # Matches our PE name
        "docstatus": 1                         # Only submitted
    },
    pluck="parent",
    distinct=True,
)
```

### 3. DO NOT Modify Reference Fields

When creating JV entries in our override, ALWAYS include the reference fields that parent's `make_journal_entry()` will add:

```python
# ✓ CORRECT - Let parent set reference fields
self.make_journal_entry(
    accounts,
    currencies,
    self.payroll_payable_account,
    submit_journal_entry=True,
    submitted_salary_slips=submitted_salary_slips,
)

# ❌ WRONG - Don't manually add/override reference fields
entry = {
    "reference_type": "Custom Type",  # ← WRONG! Breaks cancellation
    "reference_name": "Something Else"
}
```

### 4. Parent Method Invocation Chain

Our override should follow this pattern:

```python
def make_accrual_jv_entry(self, submitted_salary_slips):
    # Step 1: Our custom logic
    # - Classify components
    # - Process each type
    # - Build accounts list
    
    # Step 2: Call parent's make_journal_entry()
    # (which sets reference fields and submits JV)
    self.make_journal_entry(
        accounts,
        currencies,
        self.payroll_payable_account,
        voucher_type="Journal Entry",
        user_remark="...",
        submit_journal_entry=True,
        submitted_salary_slips=submitted_salary_slips,
    )
    
    # Step 3: Done
    # Parent's method handles:
    # - Setting reference_type and reference_name
    # - Submitting JV
    # - Linking to salary slips
    # - Setting journal_entry field in salary slips
```

## Testing Cancellation Logic

### Test Case 1: Cancel Payroll Entry Without Advances

```python
def test_cancel_payroll_entry_without_advances():
    # Setup
    payroll_entry = create_payroll_entry(employees=2, include_advances=False)
    payroll_entry.submit()
    
    # Create and verify
    salary_slips = payroll_entry.create_salary_slips()
    payroll_entry.submit_salary_slips()
    payroll_entry.make_accrual_jv_entry(salary_slips)
    
    # Get JV name
    jv_name = frappe.db.get_value(
        "Journal Entry Account",
        {"reference_name": payroll_entry.name},
        "parent"
    )
    assert jv_name, "JV should be created"
    jv = frappe.get_doc("Journal Entry", jv_name)
    assert jv.docstatus == 1, "JV should be submitted"
    
    # Cancel
    payroll_entry.cancel()
    
    # Verify
    payroll_entry.reload()
    assert payroll_entry.docstatus == 2, "PE should be cancelled"
    
    jv.reload()
    assert jv.docstatus == 2, "JV should be cancelled"
    
    # All salary slips should be cancelled
    salary_slip_docs = frappe.get_all(
        "Salary Slip",
        {"payroll_entry": payroll_entry.name},
        pluck="name"
    )
    for ss_name in salary_slip_docs:
        ss = frappe.get_doc("Salary Slip", ss_name)
        # Should either be deleted or docstatus 2
        # Based on parent implementation
```

### Test Case 2: Cancel Payroll Entry WITH Advances (Our Custom Logic)

```python
def test_cancel_payroll_entry_with_advances():
    # Setup - WITH ADVANCES (our custom party logic applies)
    payroll_entry = create_payroll_entry(employees=2, include_advances=True)
    payroll_entry.submit()
    
    # Create salary slips with advances
    salary_slips = payroll_entry.create_salary_slips()
    payroll_entry.submit_salary_slips()
    
    # Create accrual JV (uses our custom make_accrual_jv_entry)
    payroll_entry.make_accrual_jv_entry(salary_slips)
    
    # Get JV name
    jv_name = frappe.db.get_value(
        "Journal Entry Account",
        {"reference_name": payroll_entry.name},
        "parent"
    )
    jv = frappe.get_doc("Journal Entry", jv_name)
    
    # Verify party details are in JV
    advances_entries = [e for e in jv.accounts 
                        if "Employee Advances" in e.account]
    assert len(advances_entries) > 0, "Advances entries should exist"
    for entry in advances_entries:
        assert entry.party_type == "Employee", "Party type should be Employee"
        assert entry.party, "Party should be set"
    
    # NOW CANCEL - Should still cancel everything properly
    payroll_entry.cancel()
    
    # Verify
    payroll_entry.reload()
    assert payroll_entry.docstatus == 2, "PE should be cancelled"
    
    jv.reload()
    assert jv.docstatus == 2, "JV with party details should be cancelled ✓"
    
    # Verify flags are reset
    assert payroll_entry.salary_slips_created == 0
    assert payroll_entry.salary_slips_submitted == 0
    assert payroll_entry.status == "Cancelled"
    assert payroll_entry.error_message == ""
```

### Test Case 3: Verify Reference Fields Are Set Correctly

```python
def test_jv_reference_fields_for_cancellation():
    # Setup
    payroll_entry = create_payroll_entry()
    payroll_entry.submit()
    
    salary_slips = payroll_entry.create_salary_slips()
    payroll_entry.submit_salary_slips()
    payroll_entry.make_accrual_jv_entry(salary_slips)
    
    # Get JV
    jv_accounts = frappe.get_all(
        "Journal Entry Account",
        {"reference_name": payroll_entry.name},
        ["parent", "reference_type", "reference_name"]
    )
    
    # Verify reference fields
    assert len(jv_accounts) > 0, "JV should have entries with references"
    for jea in jv_accounts:
        assert jea.reference_type == "Payroll Entry", "Reference type should be Payroll Entry"
        assert jea.reference_name == payroll_entry.name, "Reference name should match PE name"
```

## Critical Summary

### What Our CustomPayrollEntry MUST Do:

✅ **DO**:
1. Override ONLY `make_accrual_jv_entry()`
2. Call `self.make_journal_entry()` to create JV
3. Let parent method set reference fields
4. NOT override cancellation methods

✅ **DO NOT**:
1. Override `cancel()`, `on_cancel()`, `delete_linked_salary_slips()`, etc.
2. Modify or remove reference_type/reference_name fields
3. Break the inheritance chain
4. Add custom cancellation logic

### Result:

When a CustomPayrollEntry is cancelled:
```
✓ All salary slips are cancelled (parent logic)
✓ All JVs are found and cancelled via reference fields (parent logic)
✓ Cancellation works for both standard AND our custom party-detailed JVs
✓ Zero orphaned records
✓ Complete data integrity maintained
✓ User sees standard "Payroll Entry Cancelled" flow
```

## Implementation Checklist for Cancellation Safety

- [ ] Override ONLY `make_accrual_jv_entry()` method
- [ ] Call `self.make_journal_entry()` to ensure reference fields are set
- [ ] Do NOT override `cancel()` method
- [ ] Do NOT override `on_cancel()` method
- [ ] Do NOT override `delete_linked_salary_slips()` method
- [ ] Do NOT override `cancel_linked_journal_entries()` method
- [ ] Verify reference_type and reference_name are set in JV entries
- [ ] Test cancellation with sample payroll entries
- [ ] Verify all salary slips are cancelled when PE is cancelled
- [ ] Verify all JVs are cancelled when PE is cancelled
- [ ] Confirm status flags are reset after cancellation
- [ ] Verify no orphaned records remain

---

**Document Version**: 1.0  
**Date**: 2025-01-01  
**Purpose**: Ensure CustomPayrollEntry cancellation behavior is correct  
**Status**: Critical - Review before implementation

