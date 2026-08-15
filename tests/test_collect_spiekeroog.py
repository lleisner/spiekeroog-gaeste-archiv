import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collect_spiekeroog import CSV_FIELDS, archive_snapshot, parse_guest_statistics


SAMPLE_HTML = b"""
<table>
  <thead><tr>
    <th>Datum</th><th>Geplante Anreisen</th><th>Geplante Abreisen</th>
    <th>Geplante Tagesg\xc3\xa4ste</th><th>G\xc3\xa4ste auf Insel</th>
  </tr></thead>
  <tbody>
    <tr><td>14.08.2026</td><td>1.348</td><td>1305</td><td>965</td><td>4492</td></tr>
    <tr><td>15.08.2026</td><td>1104</td><td>1288</td><td>436</td><td>4298</td></tr>
  </tbody>
</table>
"""


class GuestStatisticsTests(unittest.TestCase):
    def test_parser_extracts_and_normalizes_rows(self):
        rows = parse_guest_statistics(SAMPLE_HTML.decode("utf-8"))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].date, "2026-08-14")
        self.assertEqual(rows[0].planned_arrivals, 1348)
        self.assertEqual(rows[1].guests_on_island, 4298)

    def test_archive_skips_only_consecutive_identical_payloads(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            data_dir = Path(temporary_dir)
            observed_at = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
            html = SAMPLE_HTML.decode("utf-8")
            changed_raw = SAMPLE_HTML.replace(b"4492", b"4493")
            changed_html = changed_raw.decode("utf-8")

            first = archive_snapshot(data_dir, SAMPLE_HTML, html, observed_at)
            second = archive_snapshot(data_dir, SAMPLE_HTML, html, observed_at)
            changed = archive_snapshot(
                data_dir, changed_raw, changed_html, observed_at + timedelta(minutes=1)
            )
            recurring = archive_snapshot(
                data_dir, SAMPLE_HTML, html, observed_at + timedelta(minutes=2)
            )

            self.assertTrue(first.stored)
            self.assertFalse(second.stored)
            self.assertTrue(changed.stored)
            self.assertTrue(recurring.stored)
            with (data_dir / "snapshots.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(tuple(reader.fieldnames or ()), CSV_FIELDS)
                self.assertEqual(len(list(reader)), 6)
            with (data_dir / "latest.csv").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                latest_rows = list(csv.DictReader(handle))
                self.assertEqual(len(latest_rows), 2)
                self.assertEqual(latest_rows[0]["gaeste_auf_insel"], "4492")
            self.assertEqual(len(list((data_dir / "raw").glob("*.html"))), 3)


if __name__ == "__main__":
    unittest.main()
