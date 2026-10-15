/* Expected scan stamp. Matches scripts/run_after_close.py. */
(function (root) {
  function isoDay(date) {
    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, "0");
    const day = String(date.getUTCDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
  }

  function nthWeekday(year, month, weekday, occurrence) {
    const first = new Date(Date.UTC(year, month - 1, 1));
    const delta = (weekday - first.getUTCDay() + 7) % 7;
    return new Date(Date.UTC(year, month - 1, 1 + delta + 7 * (occurrence - 1)));
  }

  function lastWeekday(year, month, weekday) {
    const last = new Date(Date.UTC(year, month, 0));
    const delta = (last.getUTCDay() - weekday + 7) % 7;
    return new Date(Date.UTC(year, month - 1, last.getUTCDate() - delta));
  }

  function observed(date) {
    const day = date.getUTCDay();
    if (day === 6) return new Date(date.getTime() - 86400000);
    if (day === 0) return new Date(date.getTime() + 86400000);
    return date;
  }

  function easterSunday(year) {
    const a = year % 19;
    const b = Math.floor(year / 100);
    const c = year % 100;
    const d = Math.floor(b / 4);
    const e = b % 4;
    const f = Math.floor((b + 8) / 25);
    const g = Math.floor((b - f + 1) / 3);
    const h = (19 * a + b - d - g + 15) % 30;
    const i = Math.floor(c / 4);
    const k = c % 4;
    const l = (32 + 2 * e + 2 * i - h - k) % 7;
    const m = Math.floor((a + 11 * h + 22 * l) / 451);
    const month = Math.floor((h + l - 7 * m + 114) / 31);
    const day = ((h + l - 7 * m + 114) % 31) + 1;
    return new Date(Date.UTC(year, month - 1, day));
  }

  function nyseHolidays(year) {
    return [
      observed(new Date(Date.UTC(year, 0, 1))),
      observed(new Date(Date.UTC(year + 1, 0, 1))),
      nthWeekday(year, 1, 1, 3),
      nthWeekday(year, 2, 1, 3),
      new Date(easterSunday(year).getTime() - 2 * 86400000),
      lastWeekday(year, 5, 1),
      observed(new Date(Date.UTC(year, 5, 19))),
      observed(new Date(Date.UTC(year, 6, 4))),
      nthWeekday(year, 9, 1, 1),
      nthWeekday(year, 11, 4, 4),
      observed(new Date(Date.UTC(year, 11, 25)))
    ].map(isoDay);
  }

  function nyParts(now) {
    const fmt = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      weekday: "short"
    });
    const parts = {};
    fmt.formatToParts(now).forEach(function (part) { parts[part.type] = part.value; });
    const weekdays = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
    return {
      year: Number(parts.year),
      month: Number(parts.month),
      day: Number(parts.day),
      hour: Number(parts.hour) % 24,
      minute: Number(parts.minute),
      weekday: weekdays[parts.weekday]
    };
  }

  function nextSessionISO(iso) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
    let cursor = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + 1));
    const holidays = new Set(nyseHolidays(cursor.getUTCFullYear()).concat(nyseHolidays(cursor.getUTCFullYear() + 1)));
    for (let guard = 0; guard < 14; guard += 1) {
      const key = isoDay(cursor);
      const weekday = cursor.getUTCDay();
      if (weekday !== 0 && weekday !== 6 && !holidays.has(key)) return key;
      cursor = new Date(cursor.getTime() + 86400000);
    }
    return isoDay(cursor);
  }

  function expectedSnapshotDate(now) {
    const parts = nyParts(now || new Date());
    const today = parts.year + "-" + String(parts.month).padStart(2, "0") + "-" + String(parts.day).padStart(2, "0");
    const holidays = new Set(nyseHolidays(parts.year));
    const session = parts.weekday > 0 && parts.weekday < 6 && !holidays.has(today);
    if (session && (parts.hour < 16 || (parts.hour === 16 && parts.minute < 10))) return today;
    return nextSessionISO(today);
  }

  root.expectedSnapshotDate = expectedSnapshotDate;
  root.nyseHolidayList = nyseHolidays;
})(typeof window !== "undefined" ? window : globalThis);
