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

    rows_to_remove = []
    rows_to_add = []

    for row in doc.accounts:
        if row.account not in PER_EMPLOYEE_PARTY_ACCOUNTS:
            continue
        if row.party:
            continue  # already has a party - nothing to do

        per_employee = _get_per_employee_amounts(payroll_entry, row.account, doc.company)
        if not per_employee:
            continue

        for employee, amount in per_employee.items():
            rows_to_add.append({
                "account": row.account,
                "cost_center": row.cost_center,
                "party_type": "Employee",
                "party": employee,
                "debit_in_account_currency": amount if row.debit_in_account_currency else 0,
                "credit_in_account_currency": amount if row.credit_in_account_currency else 0,
                "exchange_rate": row.exchange_rate,
                "reference_type": "Payroll Entry",
                "reference_name": payroll_entry,
            })
        rows_to_remove.append(row)

    for row in rows_to_remove:
        doc.accounts.remove(row)
    for new_row in rows_to_add:
        doc.append("accounts", new_row)


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
