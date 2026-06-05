/* Market Terminal dashboard — vanilla JS, consumes the FastAPI JSON.
   Each view fetches its endpoint independently and renders into its section. */
"use strict";

const ENDPOINTS = {
  macro: "/macro/dashboard",
  watchlist: "/watchlist",
  cot: "/cot/dashboard",
  term: "/term-structure",
  sectors: "/screener/sectors",
  news: "/news?limit=40",
};

// ---- helpers ---------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const num = (v, d = 2) => (v === null || v === undefined || isNaN(v) ? "—" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d }));
const pctCls = (v) => (v > 0 ? "up" : v < 0 ? "down" : "dim");
const pct = (v, d = 2) => (v === null || v === undefined ? '<span class="dim">—</span>' : `<span class="${pctCls(v)}">${v > 0 ? "+" : ""}${num(v, d)}%</span>`);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function fetchJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function panel(title, inner, bad = false) {
  return `<div class="panel ${bad ? "bad" : ""}"><h3>${esc(title)}</h3><div class="body">${inner}</div></div>`;
}
function panelErr(title, msg) {
  return panel(title, `<div class="err">unavailable — ${esc(msg || "no data")}</div>`, true);
}

// ---- renderers -------------------------------------------------------------
function renderMacro(env) {
  const d = env.data || {};
  const out = [];

  // Rates
  const r = d.rates || {};
  if (r.ok) {
    const curve = (r.curve || []).map((p) => `<tr><td>${esc(p.maturity)}</td><td>${num(p.rate_pct, 2)}%</td></tr>`).join("");
    out.push(panel("Rates / Yield Curve", `
      <div class="tiles">
        <div class="tile"><div class="label">2Y</div><div class="value">${num(r.two_year_pct, 2)}%</div></div>
        <div class="tile"><div class="label">10Y</div><div class="value">${num(r.ten_year_pct, 2)}%</div></div>
        <div class="tile"><div class="label">2s10s</div><div class="value ${pctCls(r.spread_2s10s_bps)}">${num(r.spread_2s10s_bps, 1)} bps</div></div>
      </div>
      <table style="margin-top:10px"><thead><tr><th>Maturity</th><th>Rate</th></tr></thead><tbody>${curve}</tbody></table>`));
  } else out.push(panelErr("Rates / Yield Curve", r.error));

  // Dollar & FX
  const fx = d.dollar_fx || {};
  if (fx.ok) {
    const row = (lbl, o) => o ? `<tr><td>${lbl}</td><td>${num(o.value, 4)}</td><td>${pct(o.change_1d_pct)}</td><td>${pct(o.change_1w_pct)}</td><td>${pct(o.change_1m_pct)}</td></tr>` : "";
    out.push(panel("Dollar &amp; FX", `
      <table><thead><tr><th></th><th>Last</th><th>1d</th><th>1w</th><th>1m</th></tr></thead><tbody>
      ${row("Broad USD", fx.dollar_index)}${row("EUR/USD", fx.eurusd)}${row("GBP/USD", fx.gbpusd)}
      </tbody></table>`));
  } else out.push(panelErr("Dollar & FX", fx.error));

  // Macro tiles
  const mt = d.macro_tiles || {};
  if (mt.ok) {
    const tiles = (mt.tiles || []).map((t) => `<div class="tile"><div class="label">${esc(t.label)}</div><div class="value">${num(t.value, 2)}<span style="font-size:12px"> ${esc(t.unit || "")}</span></div><div class="sub">${esc(t.as_of || "")}</div></div>`).join("");
    out.push(panel("Macro Tiles", `<div class="tiles">${tiles}</div>`));
  } else out.push(panelErr("Macro Tiles", mt.error));

  // Indices
  const ix = d.indices || {};
  if (ix.ok) {
    const rows = Object.entries(ix.indices || {}).map(([sym, o]) => `<tr><td>${esc(o.label || sym)}</td><td>${num(o.value, 2)}</td><td>${pct(o.change_1d_pct)}</td><td>${pct(o.change_1w_pct)}</td><td>${pct(o.change_1m_pct)}</td></tr>`).join("");
    out.push(panel("Index Levels", `<table><thead><tr><th></th><th>Last</th><th>1d</th><th>1w</th><th>1m</th></tr></thead><tbody>${rows}</tbody></table>`));
  } else out.push(panelErr("Index Levels", ix.error));

  // Calendar
  const cal = d.calendar || {};
  if (cal.ok) {
    const evs = (cal.events || []).slice(0, 12).map((e) => `<tr><td>${esc(e.date || "")}</td><td>${esc(e.event || "")}</td><td>${esc(e.country || "")}</td></tr>`).join("");
    out.push(panel("Economic Calendar", evs ? `<table><tbody>${evs}</tbody></table>` : '<div class="dim">no events</div>'));
  } else out.push(panelErr("Economic Calendar (needs paid provider)", cal.error));

  return `<div class="grid">${out.join("")}</div>`;
}

function renderWatchlist(env) {
  const d = env.data || {};
  const rows = Object.values(d).map((i) => {
    if (!i.ok) return `<tr><td>${esc(i.code)}</td><td colspan="6" class="err">${esc(i.error)}</td></tr>`;
    const f = i.future || {};
    const p = i.proxy || {};
    const proxy = p.ok === false ? '<span class="dim">—</span>' : `${esc(p.name)}: ${num(p.close, 4)} ${pct(p.change_1d_pct)}`;
    return `<tr>
      <td>${esc(i.code)} <span class="dim">${esc(i.name)}</span></td>
      <td>${num(f.close, 4)}</td><td>${pct(f.change_1d_pct)}</td><td>${pct(f.change_1w_pct)}</td><td>${pct(f.change_1m_pct)}</td>
      <td>${num(i.atr_14, 4)} <span class="dim">(${num(i.atr_14_pct, 2)}%)</span></td>
      <td style="text-align:left">${proxy}</td></tr>`;
  }).join("");
  return panel("Watchlist — futures + spot proxy", `<table><thead><tr><th>Instrument</th><th>Close</th><th>1d</th><th>1w</th><th>1m</th><th>ATR(14)</th><th>Proxy</th></tr></thead><tbody>${rows}</tbody></table>`);
}

function renderCot(env) {
  const d = env.data || {};
  const cards = Object.values(d).map((c) => {
    if (!c.ok) return panelErr(`${c.code || ""} ${c.name || ""}`, c.error);
    const nc = c.non_commercial || {};
    const cm = c.commercial || {};
    const r1y = nc.range_1y || {};
    const pos = r1y.percentile_in_range;
    return panel(`${esc(c.name)} — ${esc(c.contract || "")}`, `
      <div class="tiles">
        <div class="tile"><div class="label">Non-comm net (specs)</div><div class="value ${pctCls(nc.net)}">${num(nc.net, 0)}</div><div class="sub">1w ${nc.net_change_1w > 0 ? "+" : ""}${num(nc.net_change_1w, 0)}</div></div>
        <div class="tile"><div class="label">Commercial net (hedgers)</div><div class="value ${pctCls(cm.net)}">${num(cm.net, 0)}</div><div class="sub">1w ${cm.net_change_1w > 0 ? "+" : ""}${num(cm.net_change_1w, 0)}</div></div>
      </div>
      <div class="sub" style="margin-top:10px">Specs net vs 1y range ${pos === null || pos === undefined ? "" : "(" + num(pos, 0) + "%)"}</div>
      <div class="bar"><span style="left:${Math.max(0, Math.min(100, pos || 0))}%"></span></div>
      <div class="sub" style="margin-top:4px">report ${esc(c.report_date || "")} · ${num(c.history_weeks, 0)} wks</div>`);
  }).join("");
  return `<div class="grid">${cards}</div>`;
}

function renderTerm(env) {
  const d = env.data || {};
  const cards = Object.values(d).map((t) => {
    if (!t.ok) return panelErr(`${t.code || ""} ${t.name || ""}`, t.error);
    const isVix = t.code === "VIX";
    const sig = t.fear_signal ? `<span class="pill ${t.structure === "backwardation" ? "red" : "green"}">${esc(t.fear_signal)}</span>` : "";
    const struct = `<span class="pill ${t.structure === "contango" ? (isVix ? "green" : "amber") : "red"}">${esc(t.structure)}</span>`;
    const curve = (t.curve || []).map((p) => `<tr><td>${esc(p.expiration)}</td><td>${num(p.price, 2)}</td></tr>`).join("");
    return panel(`${esc(t.name)}`, `
      <div>${struct} ${sig}</div>
      <div class="tiles" style="margin-top:10px">
        <div class="tile"><div class="label">Front ${esc(t.front_expiration || "")}</div><div class="value">${num(t.front_price, 2)}</div></div>
        <div class="tile"><div class="label">Back ${esc(t.back_expiration || "")}</div><div class="value">${num(t.back_price, 2)}</div></div>
        <div class="tile"><div class="label">Spread</div><div class="value">${pct(t.front_back_spread_pct)}</div></div>
      </div>
      <table style="margin-top:10px"><tbody>${curve}</tbody></table>`);
  }).join("");
  return `<div class="grid">${cards}</div>`;
}

function renderSectors(env) {
  const d = env.data || {};
  const secs = d.sectors || [];
  const max = Math.max(1, ...secs.map((s) => Math.abs(s.change_1w_pct || 0)));
  const bars = secs.map((s) => {
    const v = s.change_1w_pct || 0;
    const w = (Math.abs(v) / max) * 50; // half-width = 50%
    const color = v >= 0 ? "var(--green)" : "var(--red)";
    const side = v >= 0 ? `left:50%;width:${w}%` : `right:50%;width:${w}%`;
    return `<div class="rot"><div class="name">${esc(s.sector)} <span class="dim">${esc(s.etf)}</span></div>
      <div class="track"><div class="fill" style="${side};background:${color}"></div></div>
      <div class="pct">${pct(v)}</div></div>`;
  }).join("");
  const head = `<div class="sub" style="margin-bottom:8px">Leaders: <span class="up">${(d.leaders || []).map(esc).join(", ")}</span> · Laggards: <span class="down">${(d.laggards || []).map(esc).join(", ")}</span> · ranked by 1-week</div>`;
  return panel("Sector Rotation (1-week)", head + bars);
}

function renderNews(env) {
  const d = env.data || {};
  const items = (d.headlines || []).map((h) => `<div class="news-item">
    <a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}</a>
    <div class="news-meta"><span>${esc((h.date || "").slice(0, 16))}</span><span>${esc(h.source || "")}</span>${(h.tags || []).map((t) => `<span class="pill">${esc(t)}</span>`).join("")}</div>
  </div>`).join("");
  return panel(`News — ${num(d.count, 0)} headlines`, items || '<div class="dim">no headlines</div>');
}

const RENDERERS = { macro: renderMacro, watchlist: renderWatchlist, cot: renderCot, term: renderTerm, sectors: renderSectors, news: renderNews };

// ---- loading + tabs --------------------------------------------------------
async function loadView(view) {
  const sec = $(`#view-${view}`);
  try {
    const env = await fetchJSON(ENDPOINTS[view]);
    if (env.ok === false) { sec.innerHTML = `<div class="err">${esc(env.error || "request failed")}</div>`; return; }
    sec.innerHTML = RENDERERS[view](env);
    if (env.freshness) $("#freshness").textContent = env.freshness;
  } catch (e) {
    sec.innerHTML = `<div class="err">failed to load: ${esc(e.message)}</div>`;
  }
}

async function loadAll() {
  $("#status").textContent = "refreshing…";
  await Promise.all(Object.keys(ENDPOINTS).map(loadView));
  $("#status").textContent = "updated " + new Date().toLocaleTimeString();
}

function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
      tab.classList.add("active");
      $(`#view-${tab.dataset.view}`).classList.add("active");
    });
  });
}

function tick() { $("#clock").textContent = new Date().toUTCString().slice(17, 25) + " UTC"; }

initTabs();
$("#refresh").addEventListener("click", loadAll);
setInterval(tick, 1000); tick();
loadAll();
setInterval(loadAll, 10 * 60 * 1000); // auto-refresh every 10 min
