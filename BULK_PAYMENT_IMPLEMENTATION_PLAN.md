# Bulk Payment Entry Against Employee Advance - Implementation Plan
## SpotLedger HR Custom Implementation

> **Note**: This implementation will extend the ERPNext/HRMS Employee Advance doctype using custom scripts and hooks in the spotledger_hr app.

---

## 1. Overview

**Objective**: Implement bulk payment entry feature for Employee Advance doctype that allows users to create multiple Payment Entries simultaneously when one or more Employee Advance documents are selected from the list view.

**Scope**: 
- Add "Create Bulk Payment" action to Employee Advance list view
- Create backend method to process multiple Employee Advances
- Display progress feedback with Frappe's built-in progress bar
- Show comprehensive results dialog with success/failure information

**Status**: ✅ Only submit and Unpaid status records will be processed

---

## 2. Architecture

### 2.1 Implementation Strategy (Hooks-Based)

This implementation will use **custom scripts** loaded via hooks in `hooks.py`:

```
spotledger_hr/
├── spotledger_hr/
│   ├── employee_advance_bulk_payment/
│   │   ├── __init__.py
│   │   ├── backend.py          # Backend logic
│   │   └── frontend.js         # Frontend logic (loaded via hooks)
│   └── hooks.py                # Register scripts
└── BULK_PAYMENT_IMPLEMENTATION_PLAN.md
```

### 2.2 Hook Configuration

In `hooks.py`, register the custom script:

```python
# hooks.py
app_include_js = [
    "employee_advance_bulk_payment/frontend.js"
]

# Register backend method
app_name = "spotledger_hr"
```

### 2.3 Implementation Architecture

```
┌────────────────────────────────────────┐
│   spotledger_hr/hooks.py               │
│   (Registers custom scripts)           │
└────────────┬─────────────────────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
┌──────────────┐  ┌──────────────────┐
│frontend.js   │  │backend.py        │
│(Custom List  │  │(Backend method)  │
│View Action)  │  │                  │
└──────────────┘  └──────────────────┘
     │                    │
     └────────┬───────────┘
              ▼
    ┌────────────────────┐
    │ Employee Advance   │
    │ (HRMS Doctype)     │
    └────────────────────┘
```

---

## 3. File Structure

### 3.1 Create Backend Module

**File**: `/home/frappe/frappe-bench/apps/spotledger_hr/spotledger_hr/employee_advance_bulk_payment/backend.py`

```python
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
    
    Args:
        employee_advance_names: List/JSON string of Employee Advance names
        
    Returns:
        dict with success, failed, and summary information
    """
    
    # Parse input
    if isinstance(employee_advance_names, str):
        employee_advance_names = json.loads(employee_advance_names)
    
    # Permission check
    if not frappe.has_permission("Payment Entry", "create"):
        frappe.throw(_("You do not have permission to create Payment Entry"))
    
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
    
    # Import helper function from HRMS
    from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee
    
    # Process each Employee Advance
    for ea_name in employee_advance_names:
        try:
            # Get and validate Employee Advance document
            ea_doc = frappe.get_doc("Employee Advance", ea_name)
            
            # Validation 1: Must be submitted
            if ea_doc.docstatus != 1:
                raise frappe.ValidationError(
                    _("Only submitted Employee Advance can be paid. Current status: Draft")
                )
            
            # Validation 2: Must have Unpaid status
            if ea_doc.status != "Unpaid":
                raise frappe.ValidationError(
                    _("Only Unpaid Employee Advance can be paid. Current status: {0}").format(ea_doc.status)
                )
            
            # Validation 3: Must have outstanding amount
            outstanding_amount = flt(ea_doc.advance_amount) - flt(ea_doc.paid_amount)
            if outstanding_amount <= 0:
                raise frappe.ValidationError(_("No outstanding amount to pay"))
            
            # Create Payment Entry using HRMS function
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
            
        except Exception as e:
            # Track failure
            result["failed"].append({
                "employee_advance": ea_name,
                "reason": str(e)
            })
            result["summary"]["total_failed"] += 1
    
    return result
```

### 3.2 Create Frontend Module

**File**: `/home/frappe/frappe-bench/apps/spotledger_hr/spotledger_hr/employee_advance_bulk_payment/frontend.js`

```javascript
// Copyright (c) SpotLedger, All rights reserved
// License: GNU General Public License v3.0

// List View Settings for bulk operations
frappe.listview_settings["Employee Advance"] = {
    add_fields: ["status", "company", "advance_amount", "paid_amount", "docstatus", "employee_name"],
    
    onload(listview) {
        listview.page.add_actions_menu_item(
            __("Create Bulk Payment"),
            function() {
                const checked_items = listview.get_checked_items();
                
                // Validation: At least one record selected
                if (!checked_items.length) {
                    frappe.msgprint(__("Please select at least one Employee Advance"));
                    return;
                }
                
                // Show preview dialog
                frappe.db.get_list("Employee Advance", {
                    filters: { name: ["in", checked_items.map(i => i.name)] },
                    fields: ["name", "employee", "employee_name", "advance_amount", "paid_amount", "status", "company", "docstatus"]
                }).then(records => {
                    show_bulk_payment_preview_dialog(records);
                });
            },
            "icon-bolt"
        );
    }
};

function show_bulk_payment_preview_dialog(selected_items) {
    const dialog = new frappe.ui.Dialog({
        title: __("Create Bulk Payment Entries"),
        fields: [
            {
                fieldtype: "HTML",
                fieldname: "preview_section",
                label: ""
            }
        ],
        primary_action_label: __("Create Payment"),
        primary_action(d) {
            execute_bulk_payment_creation(selected_items);
            dialog.hide();
        },
        secondary_action_label: __("Cancel")
    });

    const preview_html = create_preview_html(selected_items);
    dialog.set_df_property("preview_section", "options", preview_html);
    dialog.show();
}

function create_preview_html(items) {
    let html = `
        <div class="bulk-payment-preview" style="padding: 15px;">
            <h6>${__("Selected Employee Advances:")}</h6>
            <table class="table table-bordered table-sm">
                <thead class="table-light">
                    <tr>
                        <th>${__("Employee Advance")}</th>
                        <th>${__("Employee")}</th>
                        <th>${__("Amount")}</th>
                        <th>${__("Status")}</th>
                        <th>${__("Company")}</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    let total_amount = 0;
    items.forEach(item => {
        const status_badge = get_status_badge(item.status);
        const amount = flt(item.advance_amount || 0) - flt(item.paid_amount || 0);
        total_amount += amount;
        
        html += `
            <tr>
                <td><strong>${item.name}</strong></td>
                <td>${item.employee_name || item.employee}</td>
                <td class="text-right">${frappe.format(amount, { fieldtype: "Currency" })}</td>
                <td>${status_badge}</td>
                <td>${item.company}</td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
            <div class="alert alert-info" role="alert">
                <i class="fa fa-info-circle"></i>
                <small>${__("Only Unpaid and submitted advances will be processed. Others will be skipped.")}</small>
            </div>
            <div class="row mt-3">
                <div class="col-6">
                    <strong>${__("Total Records:")} ${items.length}</strong>
                </div>
                <div class="col-6 text-right">
                    <strong>${__("Total Amount:")} ${frappe.format(total_amount, { fieldtype: "Currency" })}</strong>
                </div>
            </div>
        </div>
    `;
    
    return html;
}

function get_status_badge(status) {
    const status_color_map = {
        "Unpaid": "danger",
        "Paid": "success",
        "Claimed": "info",
        "Returned": "secondary",
        "Partly Claimed and Returned": "warning",
        "Draft": "warning",
        "Cancelled": "dark"
    };
    
    const color = status_color_map[status] || "secondary";
    return `<span class="badge badge-${color}">${status}</span>`;
}

function execute_bulk_payment_creation(selected_items) {
    const item_names = selected_items.map(item => item.name);
    const total = item_names.length;
    
    // Show progress bar
    frappe.show_progress(__("Creating Payment Entries"), 0, total);
    
    // Call backend endpoint
    frappe.call({
        method: "spotledger_hr.employee_advance_bulk_payment.backend.create_bulk_payment_entries",
        args: {
            employee_advance_names: item_names
        },
        callback: function(r) {
            frappe.hide_progress();
            
            if (r.message) {
                show_bulk_payment_results_dialog(r.message);
                // Refresh list view
                cur_list && cur_list.refresh();
            }
        },
        error: function(r) {
            frappe.hide_progress();
            frappe.msgprint({
                title: __("Error"),
                message: __("Error creating bulk payment entries. Please try again."),
                indicator: "red"
            });
        }
    });
}

function show_bulk_payment_results_dialog(result) {
    const dialog = new frappe.ui.Dialog({
        title: __("Bulk Payment Creation - Results"),
        width: 800,
        fields: [
            {
                fieldtype: "HTML",
                fieldname: "results_section",
                label: ""
            }
        ],
        primary_action_label: __("Close"),
        primary_action() {
            dialog.hide();
        }
    });
    
    const results_html = create_results_html(result);
    dialog.set_df_property("results_section", "options", results_html);
    dialog.show();
}

function create_results_html(result) {
    const summary = result.summary;
    const success_count = result.success.length;
    const failed_count = result.failed.length;
    
    let html = `
        <div class="bulk-payment-results" style="padding: 15px;">
            <div class="alert alert-info mb-4">
                <h6 class="mb-3"><strong>${__("Summary")}</strong></h6>
                <div class="row">
                    <div class="col-md-3">
                        <small>${__("Total Selected:")}</small><br>
                        <strong>${summary.total_selected}</strong>
                    </div>
                    <div class="col-md-3">
                        <small>${__("Successfully Created:")}</small><br>
                        <strong class="text-success">${summary.total_created}</strong>
                    </div>
                    <div class="col-md-3">
                        <small>${__("Failed/Skipped:")}</small><br>
                        <strong class="text-danger">${summary.total_failed}</strong>
                    </div>
                    <div class="col-md-3">
                        <small>${__("Total Amount:")}</small><br>
                        <strong>${frappe.format(summary.total_amount, { fieldtype: "Currency" })}</strong>
                    </div>
                </div>
            </div>
    `;
    
    // Success section
    if (success_count > 0) {
        html += `<h6 class="text-success mb-2"><i class="fa fa-check"></i> ${__("Successfully Created:")} (${success_count})</h6>`;
        html += `<table class="table table-bordered table-sm mb-4">
                    <thead class="table-light">
                        <tr>
                            <th>${__("Employee Advance")}</th>
                            <th>${__("Payment Entry")}</th>
                            <th>${__("Employee")}</th>
                            <th class="text-right">${__("Amount")}</th>
                        </tr>
                    </thead>
                    <tbody>`;
        
        result.success.forEach(item => {
            html += `
                <tr>
                    <td>${item.employee_advance}</td>
                    <td><a href="/app/payment-entry/${item.payment_entry}" target="_blank">${item.payment_entry}</a></td>
                    <td>${item.employee}</td>
                    <td class="text-right">${frappe.format(item.amount, { fieldtype: "Currency" })}</td>
                </tr>
            `;
        });
        
        html += `</tbody></table>`;
    }
    
    // Failed section
    if (failed_count > 0) {
        html += `<h6 class="text-danger mb-2"><i class="fa fa-times"></i> ${__("Failed/Skipped:")} (${failed_count})</h6>`;
        html += `<table class="table table-bordered table-sm">
                    <thead class="table-light">
                        <tr>
                            <th>${__("Employee Advance")}</th>
                            <th>${__("Reason")}</th>
                        </tr>
                    </thead>
                    <tbody>`;
        
        result.failed.forEach(item => {
            html += `
                <tr>
                    <td>${item.employee_advance}</td>
                    <td><small class="text-danger">${item.reason}</small></td>
                </tr>
            `;
        });
        
        html += `</tbody></table>`;
    }
    
    html += `</div>`;
    
    return html;
}
```

### 3.3 Create __init__.py

**File**: `/home/frappe/frappe-bench/apps/spotledger_hr/spotledger_hr/employee_advance_bulk_payment/__init__.py`

```python
# Copyright (c) SpotLedger, All rights reserved
# License: GNU General Public License v3.0

__version__ = '0.0.1'
```

### 3.4 Update hooks.py

**File**: `/home/frappe/frappe-bench/apps/spotledger_hr/spotledger_hr/hooks.py`

Add to the existing hooks.py:

```python
# Include custom scripts for Employee Advance bulk operations
app_include_js = [
    "/assets/spotledger_hr/js/employee_advance_bulk_payment.js"
]

# Or if using separate files:
# app_include_js = [
#     "employee_advance_bulk_payment/frontend.js"
# ]
```

---

## 4. Implementation Steps

### Phase 1: Setup (30 minutes)
- [ ] Create directory structure
- [ ] Create `__init__.py` file
- [ ] Create `backend.py` with main logic
- [ ] Create `frontend.js` with UI logic
- [ ] Update `hooks.py` to register scripts

### Phase 2: Testing (1-2 hours)
- [ ] Test backend endpoint with single record
- [ ] Test backend endpoint with multiple records
- [ ] Test validation (submitted vs draft)
- [ ] Test validation (Unpaid vs other status)
- [ ] Test permission checks
- [ ] Test frontend preview dialog
- [ ] Test progress bar display
- [ ] Test results dialog display

### Phase 3: Integration (1 hour)
- [ ] Test end-to-end flow
- [ ] Test with different companies
- [ ] Test with mixed status records
- [ ] Verify Payment Entries are correctly created
- [ ] Check GL entries are properly recorded

### Phase 4: Deployment (30 minutes)
- [ ] Code review
- [ ] Update documentation
- [ ] Bench update/migrate
- [ ] Clear browser cache
- [ ] UAT in production environment

---

## 5. Validation Rules

| Validation | Status | Requirement |
|-----------|--------|------------|
| Submitted | ✅ | docstatus = 1 (must be submitted) |
| Status | ✅ | status = "Unpaid" only |
| Outstanding | ✅ | advance_amount - paid_amount > 0 |
| Permission | ✅ | User must have "create" on Payment Entry |
| Selection | ✅ | At least 1 record must be selected |

---

## 6. Error Handling

| Error | Message | Handling |
|-------|---------|----------|
| No selection | "Please select at least one Employee Advance" | Show alert |
| Draft | "Only submitted Employee Advance can be paid. Current status: Draft" | Add to failed list |
| Wrong Status | "Only Unpaid Employee Advance can be paid. Current status: Paid" | Add to failed list |
| No Amount | "No outstanding amount to pay" | Add to failed list |
| No Permission | "You do not have permission to create Payment Entry" | Throw error, abort |

---

## 7. User Experience

```
1. Open Employee Advance List
2. Select multiple records (checkboxes)
3. Click Actions → Create Bulk Payment
4. Preview dialog shows selected records
5. Click "Create Payment"
6. Progress bar shows creation in progress
7. Results dialog shows summary + links
8. Click Close to return to list
```

---

## 8. Testing Checklist

- [ ] Single record creation
- [ ] Multiple records (5+)
- [ ] Mixed status records
- [ ] Multiple companies
- [ ] Permission denied test
- [ ] Draft record test
- [ ] Already paid record test
- [ ] Progress bar display
- [ ] Results dialog display
- [ ] Payment Entry links work
- [ ] List view refreshes automatically

---

## 9. Deployment Verification

After deployment:

```bash
# Clear cache
bench clear-cache

# Build assets
bench build

# Test in browser
# 1. Navigate to Employee Advance list
# 2. Select records
# 3. Verify "Create Bulk Payment" action appears
# 4. Test complete flow
```

---

## 10. Future Enhancements

- [ ] Background job for 100+ records
- [ ] Email notification with results
- [ ] Batch operation history
- [ ] Scheduled bulk creation
- [ ] Custom payment template
- [ ] Approval workflow
- [ ] Export results to Excel
