# Test type: Unit Test
# Validation to be executed: Validates transaction parsing (expense → transaction)
#   and transaction validation logic (data integrity, duplicates, wage constraints).
# Command: pytest test/test_unit_transactions.py -v

"""Unit tests for app.services.transaction_service module."""

import pytest

from app.models.schemas import Expense, TransactionFlexible
from app.services.transaction_service import parse_expenses, validate_transactions


class TestParseExpenses:
    """Convert raw expenses → enriched transactions."""

    def test_challenge_example_all_four(self):
        expenses = [
            Expense(timestamp="2023-10-12 20:15:00", amount=250),
            Expense(timestamp="2023-02-28 15:49:00", amount=375),
            Expense(timestamp="2023-07-01 21:59:00", amount=620),
            Expense(timestamp="2023-12-17 08:09:00", amount=480),
        ]
        txns = parse_expenses(expenses)

        assert len(txns) == 4
        assert txns[0].ceiling == 300 and txns[0].remanent == 50
        assert txns[1].ceiling == 400 and txns[1].remanent == 25
        assert txns[2].ceiling == 700 and txns[2].remanent == 80
        assert txns[3].ceiling == 500 and txns[3].remanent == 20

    def test_total_remanent(self):
        expenses = [
            Expense(timestamp="2023-10-12 20:15:00", amount=250),
            Expense(timestamp="2023-02-28 15:49:00", amount=375),
            Expense(timestamp="2023-07-01 21:59:00", amount=620),
            Expense(timestamp="2023-12-17 08:09:00", amount=480),
        ]
        txns = parse_expenses(expenses)
        total = sum(t.remanent for t in txns)
        assert total == 175.0

    def test_exact_multiple(self):
        expenses = [Expense(timestamp="2023-01-01 00:00:00", amount=500)]
        txns = parse_expenses(expenses)
        assert txns[0].ceiling == 500
        assert txns[0].remanent == 0

    def test_date_normalisation(self):
        """Short format 'HH:mm' normalised to 'HH:mm:ss'."""
        expenses = [Expense(timestamp="2023-10-12 20:15", amount=250)]
        txns = parse_expenses(expenses)
        assert txns[0].date == "2023-10-12 20:15:00"

    def test_empty_list(self):
        assert parse_expenses([]) == []

    def test_single_expense(self):
        expenses = [Expense(timestamp="2023-06-15 12:30:00", amount=1519)]
        txns = parse_expenses(expenses)
        assert txns[0].ceiling == 1600
        assert txns[0].remanent == 81


class TestValidateTransactions:
    """Validate transactions for data integrity, constraints, duplicates."""

    def _make_txn(self, date, amount, ceiling, remanent):
        return TransactionFlexible(
            date=date, amount=amount, ceiling=ceiling, remanent=remanent
        )

    def test_all_valid(self):
        txns = [
            self._make_txn("2023-10-12 20:15:00", 250, 300, 50),
            self._make_txn("2023-02-28 15:49:00", 375, 400, 25),
        ]
        valid, invalid = validate_transactions(50000, txns)
        assert len(valid) == 2
        assert len(invalid) == 0

    def test_duplicate_detection(self):
        txns = [
            self._make_txn("2023-10-12 20:15:00", 250, 300, 50),
            self._make_txn("2023-10-12 20:15:00", 250, 300, 50),
        ]
        valid, invalid = validate_transactions(50000, txns)
        assert len(valid) == 1
        assert len(invalid) == 1
        assert "Duplicate" in invalid[0].message

    def test_ceiling_mismatch_detected(self):
        txns = [self._make_txn("2023-10-12 20:15:00", 250, 400, 50)]
        valid, invalid = validate_transactions(50000, txns)
        assert len(invalid) == 1
        assert "Ceiling mismatch" in invalid[0].message

    def test_remanent_mismatch_detected(self):
        txns = [self._make_txn("2023-10-12 20:15:00", 250, 300, 99)]
        valid, invalid = validate_transactions(50000, txns)
        assert len(invalid) == 1
        assert "Remanent mismatch" in invalid[0].message

    def test_amount_exceeds_wage(self):
        txns = [self._make_txn("2023-10-12 20:15:00", 60000, 60000, 0)]
        valid, invalid = validate_transactions(50000, txns)
        assert len(invalid) == 1
        assert "exceeds monthly wage" in invalid[0].message

    def test_negative_amount(self):
        txns = [self._make_txn("2023-10-12 20:15:00", -100, 0, 100)]
        valid, invalid = validate_transactions(50000, txns)
        assert len(invalid) == 1
        assert "positive" in invalid[0].message.lower()

    def test_empty_list(self):
        valid, invalid = validate_transactions(50000, [])
        assert valid == []
        assert invalid == []
