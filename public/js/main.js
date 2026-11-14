// Router, one delegated event handler, and re-render. No framework, no build step.
import { load, db } from "./store.js";
import { closeSheet, openSheet } from "./ui.js";
import * as today from "./today.js";
import * as watch from "./watch.js";
import * as research from "./research.js";
import * as learn from "./learn.js";
import { TERMS, CATS } from "./glossary.js";
import { esc } from "./ui.js";

const app = document.getElementById("app");
const screens = { today, watch, research, learn };
let tab = "today";

function route() {
  const [, t = "today", arg] = location.hash.split("/");
  tab = screens[t] ? t : "today";
  document.querySelectorAll("#tabs a").forEach((a) => a.toggleAttribute("aria-current", false) || (a.dataset.tab === tab && a.setAttribute("aria-current", "page")));
  if (tab === "research" && arg && arg !== research.current()) research.open(decodeURIComponent(arg), paint);
  paint();
  window.scrollTo(0, 0);
}

function paint() {
  const y = window.scrollY;
  app.innerHTML = screens[tab].render();
  window.scrollTo(0, y);
}

document.addEventListener("click", (e) => {
  if (e.target.closest("[data-stop]")) return;
  if (e.target.closest("[data-close]") || e.target.id === "sheet") return closeSheet();
  const g = e.target.closest("[data-term], [data-cat].term, [data-guide]");
  if (g) {
    e.stopPropagation();
    if (g.dataset.guide !== undefined) { location.hash = "#/learn"; return; }
    if (g.dataset.term && TERMS[g.dataset.term]) return openSheet(`<h3>${esc(TERMS[g.dataset.term][0])}</h3><p>${esc(TERMS[g.dataset.term][1])}</p>`);
    if (g.dataset.cat && CATS[g.dataset.cat]) return openSheet(`<h3>${esc(db.meta.labels[g.dataset.cat] || g.dataset.cat)}</h3><p>${esc(CATS[g.dataset.cat])}</p>`);
    return;
  }
  const el = e.target.closest("[data-act]");
  if (!el) return;
  const act = el.dataset.act;
  if (act === "explain") {
    const ctx = today.contextFor(el.dataset.id);
    openSheet(`<h3>In plain English</h3><p id="xp">Reading the filing for you</p>`);
    learn.ask("Explain this filing to me simply: what happened, and why might an investor care?", ctx)
      .then((a) => { const p = document.getElementById("xp"); if (p) p.textContent = a; })
      .catch((err) => { const p = document.getElementById("xp"); if (p) p.textContent = `Could not explain this one: ${err.message}.`; });
    return;
  }
  if (act === "related" || act === "whyhere") { const html = today.sheetFor(act, el.dataset.id); if (html) openSheet(html); return; }
  screens[tab].handle?.(act, el, paint);
});
document.addEventListener("input", (e) => { if (tab === "watch") watch.onInput(e.target); });
document.addEventListener("change", (e) => {
  const k = e.target.dataset?.date;
  if (k) import("./ui.js").then(({ settings, save }) => {
    const lo = e.target.min, hi = e.target.max;       // never accept a date outside the data FINN holds
    let v = e.target.value; if (lo && v < lo) v = lo; if (hi && v > hi) v = hi;
    settings[k] = v; save(); paint();
  });
});
document.addEventListener("submit", (e) => {
  if (e.target.dataset.form === "ask") { e.preventDefault(); return learn.submit(new FormData(e.target).get("q").trim(), paint); }
  if (e.target.dataset.form !== "research") return;
  e.preventDefault();
  const sym = new FormData(e.target).get("sym").trim().toUpperCase();
  if (sym) location.hash = `#/research/${encodeURIComponent(sym)}`;
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });
window.addEventListener("hashchange", route);

load().then(route).catch((e) => { app.innerHTML = `<p class="boot">Could not load data: ${e.message}</p>`; });
