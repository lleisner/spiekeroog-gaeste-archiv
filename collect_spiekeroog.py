#!/usr/bin/env python3
"""Archive the public Spiekeroog guest statistics endpoint."""

import argparse
import csv
import hashlib
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


SOURCE_URL = (
    "https://www.spiekeroog.de/buchung/file/codebehind/"
    "loadGaesteStatistik.php"
)
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data" / "gaestestatistik"
MAX_RESPONSE_BYTES = 1_000_000
ARCHIVE_TIMEZONE = ZoneInfo("Europe/Berlin")
EXPECTED_HEADERS = (
    "Datum",
    "Geplante Anreisen",
    "Geplante Abreisen",
    "Geplante Tagesgäste",
    "Gäste auf Insel",
)
CSV_FIELDS = (
    "abgerufen_am",
    "datum",
    "geplante_anreisen",
    "geplante_abreisen",
    "geplante_tagesgaeste",
    "gaeste_auf_insel",
    "inhalt_sha256",
    "quell_url",
    "rohdatei",
)


@dataclass(frozen=True)
class GuestRow:
    date: str
    planned_arrivals: int
    planned_departures: int
    planned_day_guests: int
    guests_on_island: int


@dataclass(frozen=True)
class ArchiveResult:
    stored: bool
    row_count: int
    digest: str
    raw_path: Optional[Path]


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: List[List[Tuple[str, str]]] = []
        self._row: Optional[List[Tuple[str, str]]] = None
        self._cell_tag: Optional[str] = None
        self._cell_parts: List[str] = []

    def handle_starttag(
        self, tag: str, attrs: Sequence[Tuple[str, Optional[str]]]
    ) -> None:
        del attrs
        if tag == "tr":
            self._row = []
        elif tag in ("th", "td") and self._row is not None:
            self._cell_tag = tag
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_tag is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == self._cell_tag and self._row is not None:
            value = " ".join("".join(self._cell_parts).split())
            self._row.append((tag, value))
            self._cell_tag = None
            self._cell_parts = []
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _parse_count(value: str, label: str) -> int:
    normalized = value.replace(".", "").replace(" ", "")
    try:
        count = int(normalized)
    except ValueError as exc:
        raise ValueError(f"Ungültiger Wert für {label}: {value!r}") from exc
    if count < 0:
        raise ValueError(f"Negativer Wert für {label}: {value!r}")
    return count


def parse_guest_statistics(html: str) -> List[GuestRow]:
    parser = _TableParser()
    parser.feed(html)

    header_index: Optional[int] = None
    for index, row in enumerate(parser.rows):
        if tuple(value for tag, value in row if tag == "th") == EXPECTED_HEADERS:
            header_index = index
            break
    if header_index is None:
        raise ValueError("Die erwartete Gästestatistik-Tabelle wurde nicht gefunden")

    result: List[GuestRow] = []
    for row in parser.rows[header_index + 1 :]:
        cells = [value for tag, value in row if tag == "td"]
        if not cells:
            continue
        if len(cells) != 5:
            raise ValueError(f"Unerwartete Tabellenzeile mit {len(cells)} Spalten")
        try:
            source_date = datetime.strptime(cells[0], "%d.%m.%Y").date().isoformat()
        except ValueError as exc:
            raise ValueError(f"Ungültiges Datum in der Tabelle: {cells[0]!r}") from exc
        result.append(
            GuestRow(
                date=source_date,
                planned_arrivals=_parse_count(cells[1], EXPECTED_HEADERS[1]),
                planned_departures=_parse_count(cells[2], EXPECTED_HEADERS[2]),
                planned_day_guests=_parse_count(cells[3], EXPECTED_HEADERS[3]),
                guests_on_island=_parse_count(cells[4], EXPECTED_HEADERS[4]),
            )
        )

    if not result:
        raise ValueError("Die Gästestatistik-Tabelle enthält keine Datenzeilen")
    return result


def fetch_source(timeout: float) -> Tuple[bytes, str]:
    request = Request(
        SOURCE_URL,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "spiekeroog-gaeste-archiv/1.0",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("Die Serverantwort ist unerwartet groß")
        charset = response.headers.get_content_charset() or "utf-8"
    return raw, raw.decode(charset)


def _read_existing_rows(csv_path: Path) -> List[Dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise ValueError(f"Unerwartete Kopfzeile in {csv_path}")
        return list(reader)


def _already_collected_today(data_dir: Path, observed_at: datetime) -> bool:
    rows = _read_existing_rows(data_dir / "snapshots.csv")
    target_date = observed_at.astimezone(ARCHIVE_TIMEZONE).date()
    return any(
        datetime.fromisoformat(row["abgerufen_am"])
        .astimezone(ARCHIVE_TIMEZONE)
        .date()
        == target_date
        for row in rows
    )


def _atomic_write_csv(csv_path: Path, rows: List[Dict[str, str]]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(csv_path.parent), prefix=f".{csv_path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, csv_path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _write_latest_csv(data_dir: Path, rows: List[Dict[str, str]]) -> None:
    latest_by_date: Dict[str, Dict[str, str]] = {}
    for row in rows:
        previous = latest_by_date.get(row["datum"])
        if previous is None:
            latest_by_date[row["datum"]] = row
            continue
        if datetime.fromisoformat(row["abgerufen_am"]) > datetime.fromisoformat(
            previous["abgerufen_am"]
        ):
            latest_by_date[row["datum"]] = row
    latest_rows = [latest_by_date[key] for key in sorted(latest_by_date)]
    _atomic_write_csv(data_dir / "latest.csv", latest_rows)


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def archive_snapshot(
    data_dir: Path, raw: bytes, html: str, observed_at: datetime
) -> ArchiveResult:
    rows = parse_guest_statistics(html)
    digest = hashlib.sha256(raw).hexdigest()
    data_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    csv_path = data_dir / "snapshots.csv"
    existing_rows = _read_existing_rows(csv_path)

    if existing_rows and existing_rows[-1]["inhalt_sha256"] == digest:
        _write_latest_csv(data_dir, existing_rows)
        return ArchiveResult(False, 0, digest, None)

    observed_at = observed_at.astimezone(ARCHIVE_TIMEZONE).replace(microsecond=0)
    timestamp = observed_at.strftime("%Y%m%dT%H%M%S%z")
    raw_path = raw_dir / f"{timestamp}_{digest[:12]}.html"
    _atomic_write_bytes(raw_path, raw)

    relative_raw_path = raw_path.relative_to(data_dir).as_posix()
    new_rows = [
        {
            "abgerufen_am": observed_at.isoformat(),
            "datum": row.date,
            "geplante_anreisen": str(row.planned_arrivals),
            "geplante_abreisen": str(row.planned_departures),
            "geplante_tagesgaeste": str(row.planned_day_guests),
            "gaeste_auf_insel": str(row.guests_on_island),
            "inhalt_sha256": digest,
            "quell_url": SOURCE_URL,
            "rohdatei": relative_raw_path,
        }
        for row in rows
    ]
    all_rows = existing_rows + new_rows
    _atomic_write_csv(csv_path, all_rows)
    _write_latest_csv(data_dir, all_rows)
    return ArchiveResult(True, len(new_rows), digest, raw_path)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Öffentliche Spiekerooger Gästestatistik archivieren"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Zielverzeichnis (Standard: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="HTTP-Zeitlimit in Sekunden"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Abrufen und prüfen, aber nicht speichern"
    )
    parser.add_argument(
        "--once-per-day",
        action="store_true",
        help="Ohne Abruf beenden, wenn heute bereits ein Snapshot gespeichert wurde",
    )
    args = parser.parse_args(argv)

    try:
        observed_at = datetime.now(ARCHIVE_TIMEZONE)
        if args.once_per_day and _already_collected_today(args.data_dir, observed_at):
            print(f"Heute bereits archiviert: {observed_at.date().isoformat()}")
            return 0
        raw, html = fetch_source(args.timeout)
        rows = parse_guest_statistics(html)
        if args.dry_run:
            print(f"OK: {len(rows)} Zeilen geprüft; keine Dateien geschrieben")
            return 0
        result = archive_snapshot(
            args.data_dir, raw, html, datetime.now(ARCHIVE_TIMEZONE)
        )
    except (OSError, UnicodeError, URLError, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    if result.stored:
        print(
            f"Gespeichert: {result.row_count} Zeilen, SHA-256 {result.digest[:12]}, "
            f"Rohdaten {result.raw_path}"
        )
    else:
        print(f"Unverändert: SHA-256 {result.digest[:12]} ist bereits archiviert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
