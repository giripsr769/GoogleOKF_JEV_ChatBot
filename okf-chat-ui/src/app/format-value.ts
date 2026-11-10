/** Friendly dates for table cells: `2026-11-03T18:26:39.036736` -> `3 Nov 2026, 18:26`, `2026-11-03` or midnight -> `3 Nov 2026`. */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DATE_TIME = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}(?::?\d{2})?)?)?$/;

const pad = (n: number) => String(n).padStart(2, '0');

/** Returns the friendly text, or null when the value is not a date or timestamp (so the caller shows it unchanged). */
export function formatTimestamp(value: string): string | null {
  const m = DATE_TIME.exec(value);
  if (!m) return null;
  let [year, month, day, hour, minute] = [+m[1], +m[2], +m[3], m[4] === undefined ? null : +m[4], m[5] === undefined ? null : +m[5]];
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  const zone = m[6];
  if (zone && hour !== null && minute !== null) {
    // a value with an explicit time zone is shown in the viewer's own time zone
    const d = new Date(value.replace(' ', 'T'));
    if (isNaN(d.getTime())) return null;
    [year, month, day, hour, minute] = [d.getFullYear(), d.getMonth() + 1, d.getDate(), d.getHours(), d.getMinutes()];
  }
  const date = `${day} ${MONTHS[month - 1]} ${year}`;
  if (hour === null || minute === null || (hour === 0 && minute === 0)) return date; // dates, and midnight (e.g. a truncated month)
  return `${date}, ${pad(hour)}:${pad(minute)}`;
}
