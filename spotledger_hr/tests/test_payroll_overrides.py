import unittest
from unittest.mock import MagicMock, patch
import frappe
from spotledger_hr.payroll_overrides import split_party_required_lines, PER_EMPLOYEE_PARTY_ACCOUNTS, _get_per_employee_amounts


class TestPayrollOverrides(unittest.TestCase):
    def test_early_return_no_user_remark(self):
        doc = MagicMock()
        doc.user_remark = "Manual Journal Entry"
        split_party_required_lines(doc)
        # Accounts should not be modified
        doc.accounts.remove.assert_not_called()
        doc.append.assert_not_called()

    def test_early_return_no_payroll_entry_reference(self):
        doc = MagicMock()
        doc.user_remark = "Accrual Journal Entry for salaries from 2025-07-01 to 2025-07-31"
        account_row = MagicMock()
        account_row.reference_type = "Sales Invoice"
        account_row.reference_name = "ACC-SINV-2025-00001"
        doc.accounts = [account_row]

        split_party_required_lines(doc)
        doc.append.assert_not_called()

    def test_account_not_in_per_employee_party_accounts(self):
        doc = MagicMock()
        doc.user_remark = "Accrual Journal Entry for salaries from 2025-07-01 to 2025-07-31"
        doc.company = "BFI"
        
        row1 = MagicMock()
        row1.reference_type = "Payroll Entry"
        row1.reference_name = "HR-PRUN-2026-00018"
        row1.account = "511100 - Expense Account - BFI"
        row1.party = None
        
        doc.accounts = [row1]

        split_party_required_lines(doc)
        doc.append.assert_not_called()

    def test_account_already_has_party(self):
        doc = MagicMock()
        doc.user_remark = "Accrual Journal Entry for salaries from 2025-07-01 to 2025-07-31"
        doc.company = "BFI"
        
        row1 = MagicMock()
        row1.reference_type = "Payroll Entry"
        row1.reference_name = "HR-PRUN-2026-00018"
        row1.account = list(PER_EMPLOYEE_PARTY_ACCOUNTS)[0]
        row1.party = "EMP-001"
        
        doc.accounts = [row1]

        split_party_required_lines(doc)
        doc.append.assert_not_called()

    @patch("spotledger_hr.payroll_overrides._get_per_employee_amounts")
    def test_split_lines_success(self, mock_get_per_employee):
        mock_get_per_employee.return_value = {
            "EMP-001": 500.0,
            "EMP-002": 300.0,
        }

        doc = MagicMock()
        doc.user_remark = "Accrual Journal Entry for salaries from 2025-07-01 to 2025-07-31"
        doc.company = "BFI"

        row_payroll = MagicMock()
        row_payroll.reference_type = "Payroll Entry"
        row_payroll.reference_name = "HR-PRUN-2026-00018"

        row_advances = MagicMock()
        row_advances.reference_type = "Payroll Entry"
        row_advances.reference_name = "HR-PRUN-2026-00018"
        row_advances.account = "110452 - Employee Advances - BFI"
        row_advances.party = None
        row_advances.cost_center = "Main - BFI"
        row_advances.debit_in_account_currency = 0
        row_advances.credit_in_account_currency = 800.0
        row_advances.exchange_rate = 1.0

        accounts_list = [row_payroll, row_advances]
        doc.accounts = accounts_list
        
        added_rows = []
        doc.append.side_effect = lambda key, val: added_rows.append(val)

        split_party_required_lines(doc)

        mock_get_per_employee.assert_called_once_with(
            "HR-PRUN-2026-00018", "110452 - Employee Advances - BFI", "BFI"
        )
        
        self.assertNotIn(row_advances, doc.accounts)
        self.assertEqual(len(added_rows), 2)
        
        self.assertEqual(added_rows[0]["party"], "EMP-001")
        self.assertEqual(added_rows[0]["party_type"], "Employee")
        self.assertEqual(added_rows[0]["credit_in_account_currency"], 500.0)
        self.assertEqual(added_rows[0]["debit_in_account_currency"], 0)

        self.assertEqual(added_rows[1]["party"], "EMP-002")
        self.assertEqual(added_rows[1]["party_type"], "Employee")
        self.assertEqual(added_rows[1]["credit_in_account_currency"], 300.0)
        self.assertEqual(added_rows[1]["debit_in_account_currency"], 0)

    @patch("frappe.get_all")
    @patch("frappe.get_doc")
    def test_get_per_employee_amounts(self, mock_get_doc, mock_get_all):
        # First call: components query
        # Second call: salary slips query
        mock_get_all.side_effect = [
            ["Advances"],  # components linked to account
            ["SAL-SLIP-001", "SAL-SLIP-002"],  # submitted slips
        ]

        slip1 = MagicMock()
        slip1.employee = "EMP-001"
        row1 = MagicMock()
        row1.salary_component = "Advances"
        row1.amount = 150.0
        slip1.earnings = []
        slip1.deductions = [row1]

        slip2 = MagicMock()
        slip2.employee = "EMP-002"
        row2 = MagicMock()
        row2.salary_component = "Advances"
        row2.amount = 250.0
        slip2.earnings = []
        slip2.deductions = [row2]

        mock_get_doc.side_effect = [slip1, slip2]

        result = _get_per_employee_amounts(
            payroll_entry="HR-PRUN-2026-00018",
            account="110452 - Employee Advances - BFI",
            company="BFI"
        )

        self.assertEqual(result, {"EMP-001": 150.0, "EMP-002": 250.0})

    def test_merge_same_account_no_party_lines(self):
        from spotledger_hr.payroll_overrides import _merge_same_account_no_party_lines

        doc = MagicMock()
        
        row1 = MagicMock()
        row1.account = "510114 - Direct Salaries - BFI"
        row1.cost_center = "Main - BFI"
        row1.party = None
        row1.debit_in_account_currency = 35673.0
        row1.credit_in_account_currency = 0
        row1.exchange_rate = 1.0

        row2 = MagicMock()
        row2.account = "510114 - Direct Salaries - BFI"
        row2.cost_center = "Main - BFI"
        row2.party = None
        row2.debit_in_account_currency = 0
        row2.credit_in_account_currency = 844.0
        row2.exchange_rate = 1.0

        row_with_party = MagicMock()
        row_with_party.account = "211000 - Payroll Payable - BFI"
        row_with_party.cost_center = "Main - BFI"
        row_with_party.party = "EMP-001"
        row_with_party.party_type = "Employee"

        accounts_list = [row1, row2, row_with_party]
        doc.accounts = accounts_list

        added_rows = []
        doc.append.side_effect = lambda key, val: added_rows.append(val)

        _merge_same_account_no_party_lines(doc)


        self.assertNotIn(row1, doc.accounts)
        self.assertNotIn(row2, doc.accounts)
        self.assertIn(row_with_party, doc.accounts)

        self.assertEqual(len(added_rows), 1)
        self.assertEqual(added_rows[0]["account"], "510114 - Direct Salaries - BFI")
        self.assertEqual(added_rows[0]["cost_center"], "Main - BFI")
        self.assertEqual(added_rows[0]["debit_in_account_currency"], 34829.0)
        self.assertEqual(added_rows[0]["credit_in_account_currency"], 0)


if __name__ == "__main__":
    unittest.main()


