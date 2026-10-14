import datetime as dt
import decimal
import unittest

import evidence_runner as runner


class EvidenceRunnerTests(unittest.TestCase):
    def test_split_sql_ignores_comments_and_semicolons_in_strings(self):
        text = """
        -- comment;
        SET @city := 'Concepci;ón';
        # another comment
        SET @value := 2; /* block; comment */
        """
        self.assertEqual(
            runner.split_sql(text),
            ["SET @city := 'Concepci;ón'", "SET @value := 2"],
        )

    def test_checksum_is_order_independent_but_type_sensitive(self):
        columns = ["id", "amount", "at"]
        rows = [
            (1, decimal.Decimal("1.20"), dt.datetime(2026, 1, 2, 3, 4, 5)),
            (2, None, dt.datetime(2026, 1, 3, 3, 4, 5)),
        ]
        self.assertEqual(
            runner.result_checksum(columns, rows),
            runner.result_checksum(columns, list(reversed(rows))),
        )
        self.assertNotEqual(
            runner.result_checksum(columns, rows),
            runner.result_checksum(columns, [("1", decimal.Decimal("1.20"), rows[0][2]), rows[1]]),
        )

    def test_canonical_date(self):
        self.assertEqual(
            runner.canonical_value(dt.date(2026, 10, 13)),
            {"type": "date", "value": "2026-10-13"},
        )

    def test_nearest_rank_p95(self):
        self.assertEqual(runner.percentile_nearest_rank(list(range(1, 11)), 0.95), 10)


if __name__ == "__main__":
    unittest.main()
