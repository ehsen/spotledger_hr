import frappe

# Every account that (a) requires a Party per ERPNext's own validation,
# and (b) needs its aggregated payroll-accrual line broken out per
# employee instead of posted as one lump sum.
PER_EMPLOYEE_PARTY_ACCOUNTS = {
    "110452 - Employee Advances - BFI",
}


def split_party_required_lines(doc, method=None):
    if not (doc.user_remark or "").startswith("Accrual Journal Entry for salaries"):
        return

    payroll_entry = next(
        (d.reference_name for d in doc.accounts
         if d.reference_type == "Payroll Entry" and d.reference_name),
        None,
    )
    if not payroll_entry:
        return

    # Group original party-less rows by account (there may be >1, one per cost center)
    rows_by_account = {}
    for row in doc.accounts:
        if row.account in PER_EMPLOYEE_PARTY_ACCOUNTS and not row.party:
            rows_by_account.setdefault(row.account, []).append(row)

    rows_to_remove = []
    rows_to_add = []

    for account, rows in rows_by_account.items():
        # compute per-employee amounts ONCE per account, not once per row
        per_employee = _get_per_employee_amounts(payroll_entry, account, doc.company)
        if not per_employee:
            continue

        is_debit = bool(rows[0].debit_in_account_currency)
        for employee, amount in per_employee.items():
            cost_center = _employee_cost_center(payroll_entry, employee) or rows[0].cost_center
            rows_to_add.append({
                "account": account,
                "cost_center": cost_center,
                "party_type": "Employee",
                "party": employee,
                "debit_in_account_currency": amount if is_debit else 0,
                "credit_in_account_currency": amount if not is_debit else 0,
                "exchange_rate": rows[0].exchange_rate,
                "reference_type": "Payroll Entry",
                "reference_name": payroll_entry,
            })
        rows_to_remove.extend(rows)

    for row in rows_to_remove:
        doc.accounts.remove(row)
    for new_row in rows_to_add:
        doc.append("accounts", new_row)

    _merge_same_account_no_party_lines(doc)


def _merge_same_account_no_party_lines(doc):
    """
    Some Salary Components (e.g. Deficiency / "-Ve Overtime") are meant to
    stay fully visible as their own row on the Salary Slip, but should NOT
    show up as a separate line in the accrual JV - they're just a
    reduction of the same expense the earnings already debit. HRMS builds
    one JV row per (account) from its earnings dict and a separate one
    from its deductions dict, so the same account can end up with two
    rows (e.g. 510114 debit 35,673 from earnings + 510114 credit 844 from
    Deficiency) instead of one net figure.

    This collapses any set of rows that share the same account, cost
    center, and have NO party, into a single net row - keeping every
    party-attributed row (Payroll Payable per employee, Advances per
    employee, etc.) completely untouched.
    """
    groups = {}
    for row in doc.accounts:
        if row.party:
            continue
        key = (row.account, row.cost_center)
        groups.setdefault(key, []).append(row)

    for (account, cost_center), rows in groups.items():
        if len(rows) < 2:
            continue

        net = sum(r.debit_in_account_currency or 0 for r in rows) - sum(
            r.credit_in_account_currency or 0 for r in rows
        )
        ref_row = rows[0]
        for row in rows:
            doc.accounts.remove(row)

        doc.append("accounts", {
            "account": account,
            "cost_center": cost_center,
            "debit_in_account_currency": net if net >= 0 else 0,
            "credit_in_account_currency": -net if net < 0 else 0,
            "exchange_rate": ref_row.exchange_rate,
        })


def _get_per_employee_amounts(payroll_entry, account, company):
    """{employee: total_amount} across all submitted slips in this Payroll Entry
    for whichever Salary Component(s) route to `account`."""
    components = frappe.get_all(
        "Salary Component Account",
        filters={"account": account, "company": company},
        pluck="parent",
    )
    if not components:
        return {}

    slip_names = frappe.get_all(
        "Salary Slip",
        filters={"payroll_entry": payroll_entry, "docstatus": 1},
        pluck="name",
    )

    totals = {}
    for slip_name in slip_names:
        slip = frappe.get_doc("Salary Slip", slip_name)
        rows = list(slip.earnings) + list(slip.deductions)
        amount = sum(r.amount for r in rows if r.salary_component in components)
        if amount:
            totals[slip.employee] = totals.get(slip.employee, 0) + amount

    return totals


def _employee_cost_center(payroll_entry, employee):
    """Retrieve the payroll cost center from the Employee master."""
    return frappe.db.get_value("Employee", employee, "payroll_cost_center")
