// Research: any NSE ticker. Numbers come from the standardised tables with no model involved;
// the Promise Ledger comes from the company's own earnings-call transcripts, with every quote checked against the page it cites.
import { db } from "./store.js";
import { esc, cr, num, signed, pctSpan, spark, day } from "./ui.js";

const state = { sym: null, co: null, ledger: null, steps: [], error: null, busy: false };
const cache = {};
const row = (t, k) => t?.rows?.[k] || null;
const last = (a, back = 0) => (a ? a[a.length - 1 - back] : null);

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) { let m = `${r.status}`; try { m = (await r.json()).error || m; } catch { /* not json */ } throw new Error(m); }
  return r.json();
}

export async function open(sym, rerender) {
  sym = sym.trim().toUpperCase().replace(/\.NS$/, "");
  if (!/^[A-Z0-9&-]{1,20}$/.test(sym)) return;
  Object.assign(state, { sym, co: null, ledger: null, steps: [], error: null, busy: true });
  rerender();
  try {
    state.co = cache[sym]?.co || await getJSON(`data/company/${sym}.json`).catch(() => getJSON(`api/company?symbol=${encodeURIComponent(sym)}`));
    rerender();
    state.ledger = cache[sym]?.ledger || await getJSON(`data/research/${sym}.json`).catch(() => live(sym, state.co, rerender));
    cache[sym] = { co: state.co, ledger: state.ledger };
  } catch (e) {
    state.error = state.co ? `The Promise Ledger could not be built: ${e.message}. The figures below still come straight from the financial tables.`
      : `Could not load ${sym}: ${e.message}. Check the NSE symbol.`;
  }
  state.busy = false;
  rerender();
}

// Live path for a ticker that was not precomputed: one small request per transcript, so progress is visible and no request runs long.
async function live(sym, co, rerender) {
  const calls = (co.documents?.concalls || []).filter((c) => c.transcript).slice(0, 5);
  if (!calls.length) throw new Error("no earnings-call transcripts are listed for this company");
  state.steps = calls.map((c) => ({ label: `Reading the ${c.month} call`, done: false })).concat([{ label: "Checking promises against reported numbers", done: false }]);
  rerender();
  const claims = [];
  for (let i = 0; i < calls.length; i++) {
    const q = new URLSearchParams({ symbol: sym, name: co.name, month: calls[i].month, url: calls[i].transcript });
    try { claims.push(await getJSON(`api/claims?${q}`)); } catch (e) { state.steps[i].label += ` (skipped: ${e.message})`; }
    state.steps[i].done = true; rerender();
  }
  if (!claims.length) throw new Error("no transcript could be read");
  const out = await getJSON("api/ledger", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ symbol: sym, company: co, calls: claims }) });
  state.steps.at(-1).done = true;
  return out;
}

function cagr(a, years) {
  if (!a || a.length <= years) return null;
  const end = last(a), start = last(a, years);
  return end > 0 && start > 0 ? (Math.pow(end / start, 1 / years) - 1) * 100 : null;
}

function figures(co) {
  const A = co.annual, hasTTM = last(A.periods) === "TTM";
  const cut = (a) => (a && hasTTM ? a.slice(0, -1) : a);
  const rev = cut(row(A, "Sales") || row(A, "Revenue")), pat = cut(row(A, "Net Profit")), opm = cut(row(A, "OPM %"));
  const yrs = cut(A.periods).map((p) => p.replace("Mar ", "FY").replace("20", ""));
  const r3 = cagr(rev, 3), r5 = cagr(rev, 5), p3 = cagr(pat, 3), p5 = cagr(pat, 5);
  const B = co.balance, debt = row(B, "Borrowings") || row(B, "Borrowing"), eq = row(B, "Equity Capital"), res = row(B, "Reserves");
  const de = debt && eq && res ? last(debt) / (last(eq) + last(res)) : null;
  const de3 = debt && eq && res && debt.length > 3 ? last(debt, 3) / (last(eq, 3) + last(res, 3)) : null;
  const C = co.cashflow, cfo = row(C, "Cash from Operating Activity"), fcf = row(C, "Free Cash Flow");
  const n = Math.min(5, cfo?.length || 0, pat?.length || 0);
  const sum = (a) => a.slice(-n).reduce((s, v) => s + (v || 0), 0);
  const conv = n && sum(pat) > 0 ? (sum(cfo) / sum(pat)) * 100 : null;
  const R = co.ratios, ccc = row(R, "Cash Conversion Cycle"), dd = row(R, "Debtor Days"), inv = row(R, "Inventory Days");
  return { rev, pat, opm, yrs, r3, r5, p3, p5, de, de3, debt, conv, n, cfo, fcf, ccc, dd, inv, lender: co.is_lender };
}

function trajectory(f) {
  if (!f.rev) return "";
  const faster = f.p3 != null && f.r3 != null ? (f.p3 > f.r3 + 2 ? "Profit has grown faster than revenue, so margins widened." : f.p3 < f.r3 - 2 ? "Profit has grown slower than revenue, so margins were squeezed." : "Profit and revenue have grown in step.") : "";
  const accel = f.r3 != null && f.r5 != null ? (f.r3 > f.r5 + 2 ? " Growth has picked up in the last three years." : f.r3 < f.r5 - 2 ? " Growth has slowed in the last three years." : "") : "";
  const k = Math.min(5, f.rev.length);
  return `<section class="blk"><h2>Trajectory</h2><p class="verdict">${faster}${accel}</p>
    ${spark([{ values: f.rev.slice(-10) }, { values: f.pat.slice(-10), dash: true }])}
    <p class="hint">Revenue (solid) and profit after tax (dashed), last ${Math.min(10, f.rev.length)} years, same scale.</p>
    <table class="tbl"><tr><th></th>${f.yrs.slice(-k).map((y) => `<th>${esc(y)}</th>`).join("")}</tr>
    <tr><td>Revenue</td>${f.rev.slice(-k).map((v) => `<td>${num(v)}</td>`).join("")}</tr>
    <tr><td>PAT</td>${f.pat.slice(-k).map((v) => `<td>${num(v)}</td>`).join("")}</tr>
    ${f.opm && !f.lender ? `<tr><td>Margin</td>${f.opm.slice(-k).map((v) => `<td>${v ?? ""}%</td>`).join("")}</tr>` : ""}</table>
    <p class="hint">Revenue growth a year: ${signed(f.r3)} over 3 years, ${signed(f.r5)} over 5. PAT: ${signed(f.p3)} and ${signed(f.p5)}. ₹ crore.</p></section>`;
}

function balance(f) {
  if (f.lender) return `<section class="blk"><h2>Balance sheet</h2><p class="verdict">This is a lender, so borrowing is its raw material and debt-to-equity is not a risk signal here. Asset quality and capital ratios in the filings matter more.</p></section>`;
  if (f.de == null) return "";
  const lvl = f.de < 0.1 ? "Almost no debt" : f.de < 0.5 ? "Lightly geared" : f.de < 1.5 ? "Moderately geared" : "Heavily geared";
  const dir = f.de3 == null ? "" : f.de > f.de3 + 0.1 ? ", and leverage has risen over three years" : f.de < f.de3 - 0.1 ? ", and leverage has come down over three years" : ", and leverage is steady";
  const wc = f.ccc && last(f.ccc) != null && last(f.ccc, 3) != null
    ? ` Cash tied up in operations runs ${num(last(f.ccc))} days, ${last(f.ccc) > last(f.ccc, 3) + 5 ? "longer than" : last(f.ccc) < last(f.ccc, 3) - 5 ? "shorter than" : "close to"} three years ago (${num(last(f.ccc, 3))}).` : "";
  return `<section class="blk"><h2>Balance sheet</h2><p class="verdict">${lvl}: borrowings of ${cr(last(f.debt))} are ${f.de.toFixed(2)}× equity${dir}.${wc}</p></section>`;
}

function cash(f) {
  if (f.conv == null || f.lender) return "";
  const v = f.conv >= 90 ? "Profits turn into cash." : f.conv >= 60 ? "Most of the profit turns into cash, not all." : "Profit is running well ahead of cash, which deserves a closer look.";
  return `<section class="blk"><h2>Cash quality</h2><p class="verdict">${v} Over ${f.n} years, cash from operations was ${num(f.conv)}% of reported profit.</p>
    ${spark([{ values: f.cfo.slice(-8) }, { values: f.pat.slice(-8), dash: true }])}
    <p class="hint">Cash from operations (solid) against profit after tax (dashed). Latest free cash flow ${cr(last(f.fcf))}.</p></section>`;
}

const STAMP = { kept: "Delivered", missed: "Missed", partly: "Partly", open: "Too early" };
function ledger(L) {
  if (!L) return "";
  const s = L.score || {};
  const entries = (L.entries || []).map((e) => `<div class="entry">
    <div class="meta"><span>${esc(e.topic || "")}</span><span class="stamp ${esc(e.verdict)}">${STAMP[e.verdict] || esc(e.verdict)}</span></div>
    <div class="cols"><div><small>Promised, ${esc(e.said_when || "")}</small><div class="said">${esc(e.said)}</div></div>
    <div><small>Delivered</small><div class="did">${esc(e.delivered || "Not yet reported")}</div></div></div>
    ${e.quote ? `<blockquote>"${esc(e.quote)}" ${e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.said_when)}, page ${esc(e.page)}</a>` : ""}${e.quote_verified ? "" : " <span class=\"tag q\">quote not found on that page</span>"}</blockquote>` : ""}
    ${e.evidence ? `<p class="hint">${esc(e.evidence)}</p>` : ""}</div>`).join("");
  return `<section class="blk"><h2>Promise ledger</h2>
    <p class="verdict">${esc(L.summary || "")}</p>
    <div class="score"><div><b class="up">${s.kept || 0}</b>delivered</div><div><b class="down">${s.missed || 0}</b>missed</div><div><b>${s.partly || 0}</b>partly</div><div><b>${s.open || 0}</b>too early</div></div>
    <div class="ledger">${entries || `<p class="empty">Management gave no explicit numeric guidance in the calls read.</p>`}</div>
    <p class="hint">Built only from ${(L.calls || []).length} earnings-call transcripts (${esc((L.calls || []).map((c) => c.month).join(", "))}) and the reported quarterly numbers. Quotes are checked word for word against the cited page; any that fail are flagged.</p></section>
    ${L.business ? `<section class="blk"><h2>The business, in management's words</h2><p class="verdict">${esc(L.business)}</p></section>` : ""}
    ${L.bull?.length ? `<section class="blk"><h2>The case each way</h2><div class="two"><div><b class="up">Bull</b><ul>${L.bull.map((b) => `<li>${esc(b)}</li>`).join("")}</ul></div><div><b class="down">Bear</b><ul>${L.bear.map((b) => `<li>${esc(b)}</li>`).join("")}</ul></div></div></section>` : ""}`;
}

export function render() {
  const demo = db.meta.demo || [];
  const head = `<header class="top"><span class="mark">FINN</span><span class="asof">Primary sources only</span></header>
    <form class="search" data-form="research"><input name="sym" placeholder="Any NSE symbol, e.g. KPITTECH" value="${esc(state.sym || "")}" autocomplete="off" autocapitalize="characters" aria-label="NSE symbol"><button class="btn">Research</button></form>
    <div class="cats">${demo.map((s) => `<a class="chip" href="#/research/${s}">${s}</a>`).join("")}</div>`;
  if (!state.sym) return `${head}<h1 class="lede">What did management promise, and did they deliver?</h1>
    <p class="sub">FINN reads a company's last earnings calls, pulls out every number management committed to, and sets each one against what was later reported.</p>`;
  if (!state.co) return `${head}<p class="empty">${state.error ? esc(state.error) : `Loading ${esc(state.sym)}`}</p>`;
  const co = state.co, f = figures(co), t = co.top || {};
  return `${head}<article class="co"><h1>${esc(co.name)}</h1>
    <div class="kv"><div><small>Market cap</small><b>${cr(t["Market Cap"])}</b></div><div><small>P/E</small><b>${t["Stock P/E"] ?? "n/a"}</b></div>
    <div><small>ROCE</small><b>${t.ROCE ?? "n/a"}%</b></div><div><small>ROE</small><b>${t.ROE ?? "n/a"}%</b></div></div>
    ${state.error ? `<p class="empty">${esc(state.error)}</p>` : ""}
    ${state.busy && state.steps.length ? `<ul class="steps">${state.steps.map((s) => `<li class="${s.done ? "done" : ""}">${s.done ? "Done: " : ""}${esc(s.label)}</li>`).join("")}</ul>` : state.busy ? `<p class="empty">Loading the Promise Ledger</p>` : ""}
    ${ledger(state.ledger)}${trajectory(f)}${balance(f)}${cash(f)}
    <p class="hint" style="margin-top:22px">Figures: ${esc(co.basis)} financials, ₹ crore, from the company's filings as standardised on screener.in. ${co.documents?.annual_reports?.[0] ? `<a href="${esc(co.documents.annual_reports[0].url)}" target="_blank" rel="noopener">Latest annual report</a>` : ""}</p></article>`;
}

export function current() { return state.sym; }
