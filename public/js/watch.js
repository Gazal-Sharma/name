// Watch: the investor decides what "unusual" means. Sliders show how often each setting would have fired, before committing to it.
import { db, alerts, tradingDays } from "./store.js";
import { esc, settings, save, day } from "./ui.js";
import { moveRow } from "./today.js";

const state = { show: 12 };

function forecast() {
  const days = tradingDays(90), list = alerts();
  const perDay = Object.fromEntries(days.map((d) => [d, 0]));
  for (const a of list) if (a.date in perDay) perDay[a.date]++;
  const max = Math.max(1, ...Object.values(perDay));
  const weeks = days.length / 5, perWeek = list.length / weeks;
  const unexplained = list.filter((a) => !a.cause).length;
  const rate = perWeek >= 1 ? `about ${perWeek.toFixed(perWeek < 3 ? 1 : 0)} a week` : list.length ? `about one every ${Math.round(1 / perWeek)} weeks` : "none";
  return `<p class="fore">These settings would have alerted you <b>${list.length} times</b> in the last ${days.length} sessions, ${rate}. ${unexplained} had no material filing behind them.</p>
    <div class="strip" aria-hidden="true">${days.map((d) => `<i class="${perDay[d] ? "on" : ""}" style="height:${perDay[d] ? 20 + (perDay[d] / max) * 80 : 10}%"></i>`).join("")}</div>
    <p class="hint">Each tick is a session; taller means more of your stocks fired that day.</p>`;
}

export function render() {
  const list = alerts();
  const cats = Object.entries(db.meta.labels).filter(([c]) => c !== "unclassified");
  return `
  <header class="top"><span class="mark">FINN</span><span class="asof">Prices to ${day(db.meta.price_date)}</span></header>
  <h1 class="lede">Tell FINN what counts as unusual.</h1>
  <div class="ctl">
    <label for="mv">Price move in a day <output id="mvo">±${settings.movePct}%</output></label>
    <input id="mv" type="range" min="1.5" max="10" step="0.5" value="${settings.movePct}" data-set="movePct">
    <label for="vx">Volume against its 20-day average <output id="vxo">${settings.volX}×</output></label>
    <input id="vx" type="range" min="1.5" max="6" step="0.25" value="${settings.volX}" data-set="volX">
    <div id="fore">${forecast()}</div>
  </div>
  <div class="sec"><h2>Filing types</h2><span>tap to star, again to mute</span></div>
  <div class="cats">${cats.map(([c, l]) => `<button class="chip" data-act="pref" data-cat="${esc(c)}" data-s="${settings.cats[c] || ""}">${esc(l)}</button>`).join("")}</div>
  <p class="hint">Starred types move up a level in Today. Muted types are always buried.</p>
  <div class="sec"><h2>Alerts</h2><span>${list.length} in 90 sessions</span></div>
  <div class="rows" id="alist">${list.slice(0, state.show).map(moveRow).join("") || `<p class="empty">Nothing crossed these thresholds. Loosen them to see more.</p>`}</div>
  ${list.length > state.show ? `<p class="empty"><button data-act="more">Show ${Math.min(20, list.length - state.show)} more</button></p>` : ""}`;
}

// Slider drags update only the forecast and list, so the thumb never loses focus.
export function onInput(el) {
  const k = el.dataset.set;
  if (!k) return false;
  settings[k] = Number(el.value); save();
  document.getElementById("mvo").textContent = `±${settings.movePct}%`;
  document.getElementById("vxo").textContent = `${settings.volX}×`;
  document.getElementById("fore").innerHTML = forecast();
  const list = alerts();
  document.getElementById("alist").innerHTML = list.slice(0, state.show).map(moveRow).join("") || `<p class="empty">Nothing crossed these thresholds. Loosen them to see more.</p>`;
  return true;
}

export function handle(act, el, rerender) {
  if (act === "pref") { const c = el.dataset.cat, cur = settings.cats[c]; const nxt = !cur ? "star" : cur === "star" ? "mute" : null; if (nxt) settings.cats[c] = nxt; else delete settings.cats[c]; save(); }
  else if (act === "more") state.show += 20;
  else return false;
  rerender();
  return true;
}
