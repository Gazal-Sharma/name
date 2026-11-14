// Small shared helpers: escaping, formatting, tiny SVG charts, local settings.
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export const cr = (v) => {
  if (v == null) return "n/a";
  const a = Math.abs(v);
  if (a >= 100000) return `₹${(v / 100000).toFixed(2)} lakh cr`;
  return `₹${Math.round(v).toLocaleString("en-IN")} cr`;
};
export const num = (v, d = 0) => (v == null ? "n/a" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d }));
export const signed = (v, d = 1) => (v == null ? "n/a" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(d)}%`);
export const tone = (v) => (v == null || v === 0 ? "" : v > 0 ? "up" : "down");
export const pctSpan = (v, d = 1) => `<span class="${tone(v)}">${signed(v, d)}</span>`;

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const day = (iso) => { const d = new Date(iso); return `${d.getDate()} ${MON[d.getMonth()]}`; };
export const dayTime = (iso) => { const d = new Date(iso); return `${d.getDate()} ${MON[d.getMonth()]}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };

// Settings live on the phone. Nothing here needs a server.
const KEY = "finn.settings.v1";
const DEFAULTS = { volX: 2, movePct: 4, win: "24h", from: null, to: null, cats: {} };
export const settings = (() => {
  let s = { ...DEFAULTS };
  try { s = { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || "{}") }; } catch { /* private mode */ }
  return s;
})();
export const save = () => { try { localStorage.setItem(KEY, JSON.stringify(settings)); } catch { /* ignore */ } };

export function bars(values, cls = "bars") {
  const xs = values.map((v) => v ?? 0), max = Math.max(...xs, 1);
  return `<div class="${cls}" aria-hidden="true">${xs.map((v, i) => `<i class="${i === xs.length - 1 ? "now" : ""}" style="height:${Math.max(4, (v / max) * 100)}%"></i>`).join("")}</div>`;
}

export function spark(series, { w = 320, h = 56 } = {}) {
  // series: [{values, dash}]. Shared scale so two lines are comparable.
  const all = series.flatMap((s) => s.values.filter((v) => v != null));
  if (!all.length) return "";
  const lo = Math.min(...all, 0), hi = Math.max(...all), n = Math.max(...series.map((s) => s.values.length));
  const x = (i) => (n === 1 ? w / 2 : (i / (n - 1)) * (w - 4) + 2), y = (v) => h - 3 - ((v - lo) / (hi - lo || 1)) * (h - 6);
  const paths = series.map((s) => {
    const pts = s.values.map((v, i) => (v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean).join(" ");
    return `<polyline points="${pts}" fill="none" stroke="var(--ink)" stroke-width="${s.dash ? 1.4 : 2}" ${s.dash ? 'stroke-dasharray="3 3"' : ""} />`;
  }).join("");
  const zero = lo < 0 ? `<line x1="0" x2="${w}" y1="${y(0)}" y2="${y(0)}" stroke="var(--rule)" />` : "";
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">${zero}${paths}</svg>`;
}

export function openSheet(html) {
  const el = document.getElementById("sheet");
  el.innerHTML = `<div class="panel" role="dialog" aria-modal="true"><button class="close" data-close>Close</button>${html}</div>`;
  el.hidden = false;
}
export function closeSheet() { document.getElementById("sheet").hidden = true; }
