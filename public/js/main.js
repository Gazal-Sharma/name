// Router, one delegated event handler, and re-render. No framework, no build step.
import { load, db } from "./store.js";
import { closeSheet, openSheet } from "./ui.js";
import * as today from "./today.js";
import * as watch from "./watch.js";
import * as research from "./research.js";

const app = document.getElementById("app");
const screens = { today, watch, research };
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
  const el = e.target.closest("[data-act]");
  if (!el) return;
  const act = el.dataset.act;
  if (act === "related" || act === "whyhere") { const html = today.sheetFor(act, el.dataset.id); if (html) openSheet(html); return; }
  screens[tab].handle?.(act, el, paint);
});
document.addEventListener("input", (e) => { if (tab === "watch") watch.onInput(e.target); });
document.addEventListener("change", (e) => {
  const k = e.target.dataset?.date;
  if (k) import("./ui.js").then(({ settings, save }) => { settings[k] = e.target.value; save(); paint(); });
});
document.addEventListener("submit", (e) => {
  if (e.target.dataset.form !== "research") return;
  e.preventDefault();
  const sym = new FormData(e.target).get("sym").trim().toUpperCase();
  if (sym) location.hash = `#/research/${encodeURIComponent(sym)}`;
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });
window.addEventListener("hashchange", route);

load().then(route).catch((e) => { app.innerHTML = `<p class="boot">Could not load data: ${e.message}</p>`; });
