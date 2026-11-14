// Loads the snapshot once and derives everything else on the phone (windows, alerts, user tiers).
import { settings } from "./ui.js";

export const db = { meta: null, filings: [], prices: {}, asOf: null, bySym: {} };

export async function load() {
  const get = (p) => fetch(`data/${p}`, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); });
  const [meta, filings, prices] = await Promise.all([get("meta.json"), get("filings.json"), get("prices.json")]);
  Object.assign(db, { meta, filings, prices, asOf: new Date(meta.generated) });
  db.bySym = Object.fromEntries(meta.companies.map((c) => [c.sym, c]));
}

// The user's say over the ranking: a starred type moves up a tier, a muted type is always buried.
export function tierOf(f) {
  const pref = settings.cats[f.cat];
  if (pref === "mute") return 3;
  if (pref === "star") return Math.max(1, f.tier - 1);
  return f.tier;
}

export function windowRange() {
  const end = db.asOf;
  if (settings.win === "custom" && settings.from) {
    return [new Date(settings.from + "T00:00"), settings.to ? new Date(settings.to + "T23:59") : end];
  }
  const hours = { "24h": 24, "3d": 72, "7d": 168, "30d": 720 }[settings.win] || 24;
  return [new Date(end - hours * 3600e3), end];
}

export const inRange = ([a, b]) => db.filings.filter((f) => { const t = new Date(f.t); return t >= a && t <= b; });

// Price and volume alerts, recomputed instantly whenever a threshold moves.
// A day fires when |close-to-close move| >= movePct or volume >= volX times its prior 20-day average.
export function alerts(volX = settings.volX, movePct = settings.movePct, lookback = 90) {
  const out = [];
  for (const [sym, s] of Object.entries(db.prices)) {
    if (sym === "NIFTY") continue;
    const n = s.d.length;
    for (let i = Math.max(21, n - lookback); i < n; i++) {
      const r = (s.c[i] / s.c[i - 1] - 1) * 100;
      let sum = 0, k = 0;
      for (let j = i - 20; j < i; j++) if (s.v[j]) { sum += s.v[j]; k++; }
      const vm = k && s.v[i] ? s.v[i] / (sum / k) : null;
      const byMove = Math.abs(r) >= movePct, byVol = vm != null && vm >= volX;
      if (byMove || byVol) out.push({ sym, date: s.d[i], r, vm, byMove, byVol });
    }
  }
  // Join each alert to what was filed for that session, so a move arrives with its likely reason, or flagged as unexplained.
  const byDay = {};
  for (const f of db.filings) if (f.day) (byDay[`${f.sym}|${f.day}`] ||= []).push(f);
  for (const a of out) {
    const fs = (byDay[`${a.sym}|${a.date}`] || []).slice().sort((x, y) => tierOf(x) - tierOf(y));
    a.cause = fs.find((f) => tierOf(f) <= 2) || null;
    a.others = fs.length;
  }
  return out.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : Math.abs(b.r) - Math.abs(a.r)));
}

export const tradingDays = (lookback = 90) => db.prices.NIFTY.d.slice(-lookback);
