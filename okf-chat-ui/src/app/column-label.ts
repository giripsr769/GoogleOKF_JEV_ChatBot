/** Turns a database column name or SQL alias into a header a person would write: `full_name` -> `Full Name`, `customer_id` -> `Customer ID`. */

const ACRONYMS = new Set(['id', 'usd', 'sku', 'url', 'sla', 'uk', 'us', 'sql', 'api', 'ip', 'vat', 'gst', 'ui']);
const EXPAND: Record<string, string> = { avg: 'Average', qty: 'Quantity', amt: 'Amount', pct: 'Percent' };

export function columnLabel(name: string): string {
  // anything that is not a plain identifier (e.g. `COUNT(*)`, `Total Sales`) was named on purpose: leave it alone
  if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(name)) return name;
  const words = name
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2') // camelCase -> camel Case
    .split(/[_\s]+/)
    .filter(Boolean);
  return words
    .map((w) => {
      const lower = w.toLowerCase();
      if (ACRONYMS.has(lower)) return lower.toUpperCase();
      if (EXPAND[lower]) return EXPAND[lower];
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(' ');
}
