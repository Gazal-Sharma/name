// Today: the digest. One sentence, then what matters, then what's worth a glance, then the buried pile with its reasons.
import { db, tierOf, windowRange, inRange, alerts } from "./store.js";
import { esc, cr, num, signed, pctSpan, day, dayTime, settings, save, bars } from "./ui.js";

const state = { open: new Set(), buried: false, cat: null, speaking: false };
const WINS = [["24h", "24 hours"], ["3d", "3 days"], ["7d", "7 days"], ["30d", "30 days"], ["custom", "Pick dates"]];
const label = (c) => db.meta.labels[c] || c;
const name = (sym) => (db.bySym[sym]?.name || sym).replace(/ (Ltd|Limited|Company Ltd|\(India\) Ltd)\.?$/i, "");

function reaction(f) {
  if (f.r == null) return "";
  const when = f.day === f.t.slice(0, 10) ? "that session" : `next session (${day(f.day)})`;
  const vol = f.vm >= 1.5 ? `, volume ${f.vm.toFixed(1)}× normal` : "";
  return `<p class="react">Stock ${pctSpan(f.r)} ${when}, ${pctSpan(f.ar)} against the Nifty${vol}.</p>`;
}

function resultsBody(f) {
  const R = f.results;
  if (!R.rows.length) return `<p class="why">Results filed. Standardised numbers for ${esc(R.period || "this quarter")} are not available yet; open the filing.</p>`;
  const rows = R.rows.map((r) => `<div>${r.k}</div><div class="v">${num(r.v)}</div><div class="d">${pctSpan(r.qoq)}</div><div class="d">${pctSpan(r.yoy)}</div>`).join("");
  const m = R.margin;
  const margin = m ? `<p class="note">EBITDA margin ${m.v}%${m.ya != null ? `, ${m.v === m.ya ? "unchanged from" : m.v > m.ya ? "up from" : "down from"} ${m.ya}% a year ago` : ""}.</p>` : "";
  const lender = R.lender ? `<p class="note">EBITDA is not meaningful for a lender, so it is left out.</p>` : "";
  return `<div class="nums"><div class="h">₹ crore, ${esc(R.basis || "")}</div><div class="h">${esc(R.period)}</div><div class="h">QoQ</div><div class="h">YoY</div>${rows}</div>
    ${margin}${lender}${bars(R.trend.rev)}<p class="note">Revenue, last ${R.trend.rev.length} quarters.</p>`;
}

function peopleBody(f) {
  return f.people.map((p) => `<div class="person"><b>${esc(p.name)}</b>, ${esc(p.role || "")} <span class="tag">${esc(p.change || "change")}</span>
    ${p.effective ? `<span class="x"> from ${esc(p.effective)}</span>` : ""}
    <p>${p.background ? esc(p.background) : "The filing gives no career background."}</p></div>`).join("");
}

function sheet(f) {
  const rel = f.related?.length || 0;
  const title = f.results ? `${name(f.sym)}: ${f.title}` : f.title;
  return `<article class="sheet">
    <div class="who"><span><b>${esc(f.sym)}</b> ${esc(label(f.cat))}</span><span>${dayTime(f.t)}</span></div>
    <h3><span>${esc(title)}</span></h3>
    ${f.results ? resultsBody(f) : f.why ? `<p class="why">${esc(f.why)}</p>` : ""}
    ${f.people ? peopleBody(f) : ""}
    ${reaction(f)}
    <div class="acts">
      ${f.url ? `<a href="${esc(f.url)}" target="_blank" rel="noopener">Open filing</a>` : ""}
      ${f.results?.source ? `<a href="${esc(f.results.source)}" target="_blank" rel="noopener">Results PDF</a>` : ""}
      ${f.has_transcript || f.results ? `<a href="#/research/${esc(f.sym)}">Promised vs delivered</a>` : ""}
      ${rel ? `<button data-act="related" data-id="${f.id}">${rel} related filing${rel > 1 ? "s" : ""}</button>` : ""}
      <button data-act="whyhere" data-id="${f.id}">Why this is here</button>
    </div></article>`;
}

function row(f) {
  const open = state.open.has(f.id);
  return `<button class="row" data-act="toggle" data-id="${f.id}" aria-expanded="${open}">
    <div class="l1"><span><b>${esc(f.sym)}</b> ${esc(label(f.cat))}</span><span>${day(f.t)}</span></div>
    <div class="t">${esc(f.title)}</div>
    ${open ? `<div class="more">${f.why ? esc(f.why) + " " : ""}${f.ar != null ? `Stock ${signed(f.ar)} against the Nifty. ` : ""}
      ${f.url ? `<a href="${esc(f.url)}" target="_blank" rel="noopener" data-stop>Open filing</a>` : ""}</div>` : ""}
  </button>`;
}

function evidence(cat) {
  const s = db.meta.impact.categories[cat], b = db.meta.impact.baseline.median_abs;
  if (!s || s.n < 8) return "Too few past cases in this portfolio to measure.";
  const verdict = s.lift >= 1.5 ? "well above" : s.lift >= 1.2 ? "a little above" : "about the same as";
  return `Over the past year these days moved the stock ${s.median_abs}% against the Nifty at the median, ${verdict} a normal day's ${b}% (${s.n} cases).`;
}

function buried(list) {
  if (!list.length) return "";
  const groups = {};
  for (const f of list) (groups[f.cat] ||= []).push(f);
  const cats = Object.entries(groups).sort((a, b) => b[1].length - a[1].length);
  const inner = !state.buried ? "" : cats.map(([c, fs]) => `<div class="cat">
      <button data-act="cat" data-cat="${esc(c)}" aria-expanded="${state.cat === c}"><span>${esc(label(c))}</span><span>${fs.length}</span></button>
      <p class="ev">${evidence(c)}</p>
      ${state.cat === c ? fs.map((f) => `<div class="item"><b>${esc(f.sym)}</b> ${esc(f.title)}${f.related?.length ? ` (+${f.related.length} similar)` : ""}
        ${f.url ? ` <a href="${esc(f.url)}" target="_blank" rel="noopener">Open</a>` : ""}</div>`).join("") : ""}</div>`).join("");
  return `<section class="buried"><button data-act="buried" aria-expanded="${state.buried}"><span>${list.length} buried</span><span>${state.buried ? "Hide" : "Show why"}</span></button>${inner}</section>`;
}

function moves(range) {
  const [a, b] = range.map((d) => d.toISOString().slice(0, 10));
  const list = alerts().filter((x) => x.date >= a && x.date <= b);
  if (!list.length) return "";
  return `<div class="sec"><h2>Unusual moves</h2><span>${list.length} past ±${settings.movePct}% or ${settings.volX}× volume</span></div><div class="rows">${list.slice(0, 5).map(moveRow).join("")}</div>`;
}

export function moveRow(x) {
  const cause = x.cause
    ? `Same session: ${esc(x.cause.title)} <span class="tag">${esc(label(x.cause.cat))}</span>`
    : `<span class="tag q">No material filing</span> ${x.others ? `${x.others} routine filing${x.others > 1 ? "s" : ""} that day.` : "Nothing filed that day."}`;
  return `<div class="move"><div><b>${esc(x.sym)}</b><div class="x">${day(x.date)}</div></div>
    <div><b class="${x.r > 0 ? "up" : "down"}">${signed(x.r)}</b>${x.vm ? ` on ${x.vm.toFixed(1)}× volume` : ""}<div class="x">${cause}</div></div></div>`;
}

function lede(all, t1, range, total) {
  const span = settings.win === "custom" ? `between ${day(range[0])} and ${day(range[1])}` : `in the last ${WINS.find((w) => w[0] === settings.win)[1]}`;
  if (!all.length) return `<h1 class="lede">Nothing filed ${span}.</h1>`;
  const n = total, k = t1.length;
  return `<h1 class="lede">${n} filing${n > 1 ? "s" : ""} ${span}. <span class="n">${k === 0 ? "None" : k} matter${k === 1 ? "s" : ""}.</span></h1>`;
}

function nextBusyWindow() {
  for (const [w, lab] of WINS.slice(0, 4)) {
    const hours = { "24h": 24, "3d": 72, "7d": 168, "30d": 720 }[w];
    const n = inRange([new Date(db.asOf - hours * 3600e3), db.asOf]);
    if (n.length) return { w, lab, n: n.length, k: n.filter((f) => tierOf(f) === 1).length };
  }
  return null;
}

export function render() {
  const range = windowRange();
  const all = inRange(range).sort((a, b) => (a.t < b.t ? 1 : -1));
  const total = all.reduce((s, f) => s + 1 + (f.related?.length || 0), 0);
  const t1 = all.filter((f) => tierOf(f) === 1).sort((a, b) => Math.abs(b.ar ?? 0) - Math.abs(a.ar ?? 0));
  const t2 = all.filter((f) => tierOf(f) === 2);
  const t3 = all.filter((f) => tierOf(f) === 3);
  const next = !all.length ? nextBusyWindow() : null;
  const custom = settings.win === "custom"
    ? `<div class="custom"><input type="date" data-date="from" value="${settings.from || ""}" aria-label="From"> to <input type="date" data-date="to" value="${settings.to || ""}" aria-label="To"></div>` : "";
  return `
  <header class="top"><span class="mark">FINN</span><span class="asof">Data as of ${dayTime(db.meta.generated)}</span></header>
  <div class="win" role="group" aria-label="Time window">${WINS.map(([w, l]) => `<button class="chip" data-act="win" data-win="${w}" aria-pressed="${settings.win === w}">${l}</button>`).join("")}</div>
  ${custom}
  ${lede(all, t1, range, total)}
  <p class="sub">${all.length ? `Across ${new Set(all.map((f) => f.sym)).size} of your ${db.meta.companies.length} stocks. Prices to ${day(db.meta.price_date)}.` : ""}</p>
  ${all.length && "speechSynthesis" in window ? `<button class="brief" data-act="speak">${state.speaking ? "Stop" : "Read me the brief"}</button>` : ""}
  ${next ? `<p class="empty">The last ${next.lab} had ${next.n} filings${next.k ? `, ${next.k} that matter` : ""}. <button data-act="win" data-win="${next.w}">Show the last ${next.lab}</button></p>` : ""}
  ${t1.length ? `<div class="sec"><h2>Matters</h2><span>${t1.length}</span></div>${t1.map(sheet).join("")}` : ""}
  ${moves(range)}
  ${t2.length ? `<div class="sec"><h2>Worth a glance</h2><span>${t2.length}</span></div><div class="rows">${t2.map(row).join("")}</div>` : ""}
  ${buried(t3)}`;
}

function briefText() {
  const all = inRange(windowRange()), t1 = all.filter((f) => tierOf(f) === 1), t2 = all.filter((f) => tierOf(f) === 2);
  const parts = [`${all.length} filings in this window. ${t1.length} matter.`];
  for (const f of t1.slice(0, 6)) {
    if (f.results?.rows.length) {
      const rev = f.results.rows[0], pat = f.results.rows.at(-1);
      parts.push(`${name(f.sym)}, ${f.results.period} results. Revenue ${num(rev.v)} crore, ${rev.yoy >= 0 ? "up" : "down"} ${Math.abs(rev.yoy)} percent on the year. Profit after tax ${num(pat.v)} crore, ${pat.yoy >= 0 ? "up" : "down"} ${Math.abs(pat.yoy)} percent.${f.ar != null ? ` The stock moved ${f.ar > 0 ? "up" : "down"} ${Math.abs(f.ar)} percent against the Nifty.` : ""}`);
    } else parts.push(`${name(f.sym)}. ${f.title}. ${f.why || ""}`);
  }
  if (t2.length) parts.push(`${t2.length} more are worth a glance, and ${all.length - t1.length - t2.length} are buried.`);
  return parts.join(" ");
}

export function handle(act, el, rerender) {
  if (act === "win") { settings.win = el.dataset.win; if (settings.win === "custom" && !settings.from) { settings.from = new Date(db.asOf - 14 * 864e5).toISOString().slice(0, 10); settings.to = db.asOf.toISOString().slice(0, 10); } save(); }
  else if (act === "toggle") { state.open.has(el.dataset.id) ? state.open.delete(el.dataset.id) : state.open.add(el.dataset.id); }
  else if (act === "buried") state.buried = !state.buried;
  else if (act === "cat") state.cat = state.cat === el.dataset.cat ? null : el.dataset.cat;
  else if (act === "speak") {
    if (state.speaking) { speechSynthesis.cancel(); state.speaking = false; }
    else { const u = new SpeechSynthesisUtterance(briefText()); u.lang = "en-IN"; u.rate = 1.05; u.onend = () => { state.speaking = false; rerender(); }; speechSynthesis.speak(u); state.speaking = true; }
  } else return false;
  rerender();
  return true;
}

export function sheetFor(act, id) {
  const f = db.filings.find((x) => x.id === id);
  if (!f) return null;
  if (act === "related") {
    return `<h3>${esc(f.sym)}: filed around this event</h3><div class="rows">${f.related.map((r) => `<div class="row"><div class="l1"><span>${esc(r.desc)}</span><span>${dayTime(r.t)}</span></div>
      <div class="t">${esc(r.text || r.kind)}</div>${r.url ? `<div class="more"><a href="${esc(r.url)}" target="_blank" rel="noopener">Open filing</a></div>` : ""}</div>`).join("")}</div>`;
  }
  const pref = settings.cats[f.cat];
  return `<h3>Why this is here</h3>
    <p>${f.src === "model" ? "A small model read the first pages of the filing and rated it against the company's size." : "A fixed rule placed it from the exchange's own label and text. No model was used."}</p>
    <p class="hint">Exchange label: ${esc(f.desc)}. Filed as: ${esc(label(f.cat))}${f.amount_cr ? `. Amount: ${cr(f.amount_cr)}` : ""}.</p>
    <p style="margin-top:10px">${evidence(f.cat)}</p>
    ${pref ? `<p class="hint">You have ${pref === "star" ? "starred" : "muted"} this type in Watch, which moved it ${pref === "star" ? "up" : "down"}.</p>` : ""}
    ${f.nse_summary ? `<p class="hint" style="margin-top:10px">Exchange summary: ${esc(f.nse_summary)}</p>` : ""}`;
}
