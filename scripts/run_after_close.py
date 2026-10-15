#!/usr/bin/env python3
"""Run the daily scanner once, 10 minutes after a regular US market close."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_DIR / "logs"
MARKER = PROJECT_DIR / "outputs" / ".last_scheduled_run.txt"
LOCK_DIR = PROJECT_DIR / ".daily_scan.lock"
NY_TZ = ZoneInfo("America/New_York")


def nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(days=7 * (occurrence - 1))


def last_weekday(year: int, month: int, weekday: int) -> date:
    current = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def easter_sunday(year: int) -> date:
    """Return Western Easter using the Meeus/Jones/Butcher algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def nyse_holidays(year: int) -> set[date]:
    return {
        observed(date(year, 1, 1)),
        observed(date(year + 1, 1, 1)),
        nth_weekday(year, 1, 0, 3),
        nth_weekday(year, 2, 0, 3),
        easter_sunday(year) - timedelta(days=2),
        last_weekday(year, 5, 0),
        observed(date(year, 6, 19)),
        observed(date(year, 7, 4)),
        nth_weekday(year, 9, 0, 1),
        nth_weekday(year, 11, 3, 4),
        observed(date(year, 12, 25)),
    }


def should_run(now: datetime) -> bool:
    return (
        now.weekday() < 5
        and now.date() not in nyse_holidays(now.year)
        and (now.hour, now.minute) >= (16, 10)
    )


def next_session_date(now: datetime) -> date:
    """Stamp post-close output for the next NYSE session (Fri → Mon)."""
    candidate = now.astimezone(NY_TZ).date() + timedelta(days=1)
    holidays = nyse_holidays(candidate.year) | nyse_holidays(candidate.year + 1)
    while candidate.weekday() >= 5 or candidate in holidays:
        candidate += timedelta(days=1)
    return candidate


def is_session(day: date) -> bool:
    return day.weekday() < 5 and day not in nyse_holidays(day.year)


def expected_snapshot_date(now: datetime) -> date:
    """The stamp a finished scan should already have written.

    Before 16:10 NY on a session day, last night's file is stamped today.
    After the close, tonight's file is stamped for the next session.
    Weekends and holidays already carry Friday's next-session stamp.
    """
    local = now.astimezone(NY_TZ)
    if is_session(local.date()) and (local.hour, local.minute) < (16, 10):
        return local.date()
    return next_session_date(local)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even outside the post-close window (also set FORCE_RUN=1).",
    )
    parser.add_argument(
        "--snapshot-date",
        type=date.fromisoformat,
        help="Override output stamp (YYYY-MM-DD). Default: next NYSE session.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    force = args.force or os.environ.get("FORCE_RUN", "").strip() in {"1", "true", "TRUE", "yes", "YES"}
    now = datetime.now(NY_TZ)
    if not force and not should_run(now):
        print(f"Skip: not after US close yet ({now.isoformat()})", flush=True)
        return 0
    LOG_DIR.mkdir(exist_ok=True)
    MARKER.parent.mkdir(exist_ok=True)
    if not force and MARKER.exists() and MARKER.read_text(encoding="utf-8").strip() == now.date().isoformat():
        print(f"Skip: already ran for {now.date().isoformat()}", flush=True)
        return 0
    try:
        LOCK_DIR.mkdir()
    except FileExistsError:
        print("Skip: lock held by another run", flush=True)
        return 0
    try:
        snapshot = args.snapshot_date or next_session_date(now)
        log_path = LOG_DIR / f"daily_scan_{now.date().isoformat()}.log"
        local_python = PROJECT_DIR / ".venv" / "bin" / "python"
        scanner_python = local_python if local_python.exists() else Path(sys.executable)
        cmd = [str(scanner_python), "focus_list.py", "--snapshot-date", snapshot.isoformat()]
        print(f"Running {' '.join(cmd)} (force={force})", flush=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n--- Scheduled run started {now.isoformat()} force={force} ---\n")
            result = subprocess.run(
                cmd,
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            log.write(result.stdout or "")
            log.write(f"--- Scheduled run finished with exit code {result.returncode} ---\n")
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
        if result.returncode == 0:
            MARKER.write_text(now.date().isoformat() + "\n", encoding="utf-8")
        else:
            print(f"Scan failed with exit code {result.returncode}", flush=True)
        return result.returncode
    finally:
        if LOCK_DIR.exists():
            LOCK_DIR.rmdir()


if __name__ == "__main__":
    sys.exit(main())
