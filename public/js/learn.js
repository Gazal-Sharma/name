// Learn: everything a newcomer needs on one page, a box to ask anything, and places to read more.
import { TERMS, CATS } from "./glossary.js";
import { db } from "./store.js";
import { esc } from "./ui.js";

const state = { q: "", a: "", busy: false };
const GROUPS = [
  ["Reading a results card", ["revenue", "ebitda", "pbt", "pat", "margin", "qoq", "yoy", "crore", "consolidated"]],
  ["Prices and trading", ["nifty", "volume", "mcap", "pe"]],
  ["Judging a company", ["guidance", "concall", "roce", "roe", "cashconv", "leverage"]],
];
const LINKS = [
  ["Zerodha Varsity", "https://zerodha.com/varsity/", "Free, well-written lessons on markets, from the very beginning."],
  ["SEBI investor education", "https://investor.sebi.gov.in/", "The market regulator's own guides for new investors."],
  ["NSE India", "https://www.nseindia.com/", "The exchange itself, where every filing in this app comes from."],
  ["Screener", "https://www.screener.in/", "Company financials in one place; FINN's numbers are taken from here."],
];
const SUGGEST = ["Why does profit fall when sales rise?", "What is a good EBITDA margin?", "Why do share prices jump after results?"];

export async function ask(question, context) {
  const r = await fetch("api/ask", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ mode: "explain", question, context }) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "the help desk is unavailable right now");
  return j.answer;
}

export function render() {
  return `<header class="top"><span class="mark">FINN</span><span class="asof">No finance background needed</span></header>
  <h1 class="lede">The basics, in plain English.</h1>
  <section class="blk"><h2>The idea</h2>
    <p class="verdict">A company listed on a stock exchange must tell the exchange, in a formal notice called a filing, about anything that happens to it. Most filings are paperwork. A few change what the company is worth. FINN reads all of them for the companies you hold and puts the few that count in front of you.</p></section>
  <section class="blk"><h2>Ask anything</h2>
    <form class="search" data-form="ask"><input name="q" style="text-transform:none" placeholder="e.g. What is EBITDA?" value="${esc(state.q)}" aria-label="Your question" autocomplete="off"><button class="btn">${state.busy ? "Thinking" : "Ask"}</button></form>
    ${state.a ? `<p class="verdict" style="margin-top:12px">${esc(state.a)}</p>` : `<div class="cats">${SUGGEST.map((s) => `<button class="chip" data-act="suggest" data-q="${esc(s)}">${esc(s)}</button>`).join("")}</div>`}
    <p class="hint">Answered by a small AI model. It explains; it does not give investment advice.</p></section>
  <section class="blk"><h2>The three screens</h2>
    <dl class="defs"><dt>Today</dt><dd>Pick a time window. The big sentence says how many filings arrived and how many matter. "Matters" are shown in full, "Worth a glance" get one line, and "Buried" is the routine pile, with the reason for each.</dd>
    <dt>Watch</dt><dd>You decide how big a price move or a jump in trading counts as unusual. FINN lists each time it happened and whether a filing explains it.</dd>
    <dt>Research</dt><dd>Type any company. FINN reads what its managers promised investors and checks each promise against the results that followed.</dd></dl></section>
  ${GROUPS.map(([h, keys]) => `<section class="blk"><h2>${h}</h2><dl class="defs">${keys.map((k) => `<dt>${esc(TERMS[k][0])}</dt><dd>${esc(TERMS[k][1])}</dd>`).join("")}</dl></section>`).join("")}
  <section class="blk"><h2>Types of filing</h2><dl class="defs">${Object.entries(CATS).map(([k, v]) => `<dt>${esc(db.meta.labels[k] || k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></section>
  <section class="blk"><h2>Read more</h2><div class="rows">${LINKS.map(([n, u, d]) => `<a class="row" href="${u}" target="_blank" rel="noopener" style="text-decoration:none"><div class="t">${n}</div><div class="more">${d}</div></a>`).join("")}</div></section>`;
}

export async function submit(q, rerender) {
  if (!q || state.busy) return;
  Object.assign(state, { q, a: "", busy: true }); rerender();
  try { state.a = await ask(q); } catch (e) { state.a = `Could not answer: ${e.message}.`; }
  state.busy = false; rerender();
}
export function handle(act, el, rerender) { if (act === "suggest") { submit(el.dataset.q, rerender); return true; } return false; }
