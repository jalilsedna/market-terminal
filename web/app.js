/* Market Terminal dashboard — vanilla JS, consumes the FastAPI JSON.
   Each view fetches its endpoint independently and renders into its section. */
"use strict";

const ENDPOINTS = {
  macro: "/macro/dashboard",
  watchlist: "/watchlist",
  cot: "/cot/dashboard",
  term: "/term-structure",
  volatility: "/volatility?horizon=5",
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
  // Session expired / not signed in: bounce to the login page (auth is a no-op
  // when the deploy is keyless, so this never fires locally).
  if (r.status === 401) {
    window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
    throw new Error("unauthorized");
  }
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
    out.push(panel("Dollar & FX", `
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

// Volatility tab (ROADMAP E4): realized vol, regime vs ~3y, and a short-horizon
// forecast (EWMA, validated best on daily futures; HAR shown faint). Research
// context for sizing/regime awareness — never a trade trigger.
function _volPill(regime) {
  const cls = { calm: "green", normal: "", elevated: "amber", stressed: "red" }[regime] ?? "";
  return `<span class="pill ${cls}">${esc(regime || "—")}</span>`;
}
function renderVolatility(env) {
  const d = env.data || {};
  const insts = d.instruments || {};
  const vals = Object.values(insts);
  const horizon = (vals.find((v) => v.ok) || {}).forecast?.horizon_days || 5;
  const rows = vals.map((v) => {
    if (!v.ok) return `<tr><td>${esc(v.instrument)} <span class="dim">${esc(v.name || "")}</span></td><td colspan="5" class="err">${esc(v.error || "n/a")}</td></tr>`;
    const r = v.regime || {}, f = v.forecast || {};
    return `<tr>
      <td>${esc(v.instrument)} <span class="dim">${esc(v.name)}</span></td>
      <td>${num((v.current_vol_annualized || 0) * 100, 1)}%</td>
      <td>${_volPill(r.regime)}</td>
      <td>${num(r.percentile, 0)}<span class="dim">th</span></td>
      <td>${num((f.ewma || 0) * 100, 1)}%</td>
      <td class="dim">${num((f.har_rv || 0) * 100, 1)}%</td></tr>`;
  }).join("");
  const head = `<div class="sub" style="margin-bottom:8px">Annualized realized volatility, regime vs ~3y history, and a ${num(horizon, 0)}-day forecast (EWMA; HAR shown faint). Research context — not a trade trigger.</div>`;
  const table = panel("Volatility & Regime", head +
    `<table><thead><tr><th>Instrument</th><th>Realized vol</th><th>Regime</th><th>%ile</th><th>Fcst (EWMA)</th><th>HAR</th></tr></thead><tbody>${rows}</tbody></table>`);
  const reads = vals.filter((v) => v.ok && v.read).map((v) => `<div class="sub" style="margin-top:4px">• ${esc(v.read)}</div>`).join("");
  return `<div class="grid" style="grid-template-columns:1fr">${table}${reads ? panel("Reads", reads) : ""}</div>
    <div class="exec-help dim" style="margin-top:8px">${esc(d.disclaimer || "")}</div>`;
}

const RENDERERS = { macro: renderMacro, watchlist: renderWatchlist, cot: renderCot, term: renderTerm, volatility: renderVolatility, sectors: renderSectors, news: renderNews };

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

// Execution tab: frames the SEPARATE OpenAlice app (the execution "hand"). The
// terminal stays research-only — it just hosts a window to Alice; no order logic
// lives here. The URL comes from the backend (/health → alice_url).
async function loadExecution() {
  const sec = $("#view-execution");
  let url = "http://localhost:5173";
  try { url = (await fetchJSON("/health")).alice_url || url; } catch (e) { /* keep default */ }

  const bar = `<div class="exec-bar">
      <span>Execution runs in <b>OpenAlice</b> — a separate app on your machine. Research flows out via MCP; orders stay there.</span>
      <a class="btn" href="${esc(url)}" target="_blank" rel="noopener">Open Alice ↗</a>
    </div>`;

  // A browser won't embed an http:// (localhost) app inside an https:// page —
  // "mixed content". On the deployed terminal that just yields a blank box, so
  // show a clean explanation + launch button instead of a broken iframe. The
  // embedded view works when you run the terminal locally (http → http).
  const mixed = window.location.protocol === "https:" && url.startsWith("http://");
  if (mixed) {
    sec.innerHTML = bar + `<div class="exec-card">
      <h3>Alice runs locally — by design</h3>
      <p class="dim">OpenAlice is your <b>execution</b> app; it holds broker keys, so it stays on your machine and is never deployed. This online terminal can't embed your local <code>${esc(url)}</code> (browsers block http content inside an https page).</p>
      <p><a class="btn" href="${esc(url)}" target="_blank" rel="noopener">Open Alice ↗</a> &nbsp;launches your local Alice in a new tab.</p>
      <p class="dim">Already connected the other way: Alice <b>pulls this terminal's research over MCP</b>. For the embedded side-by-side view, run the terminal locally (<code>uvicorn app.main:app</code>) and open <code>http://localhost:8000</code>.</p>
    </div>`;
    return;
  }

  sec.innerHTML = bar +
    `<iframe class="exec-frame" src="${esc(url)}" title="OpenAlice"></iframe>
    <div class="exec-help dim">Not loading? Make sure OpenAlice is running (<code>pnpm dev</code>) and reachable at
      <a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a>. Some apps block embedding — use the "Open Alice ↗" button.</div>`;
}

// Analysis tab: interpreted signals (regime + COT positioning). Fetches both
// /analysis endpoints and renders the read — research context, not a signal.
function _regimeCls(label) {
  if (!label) return "dim";
  if (label.startsWith("risk-on")) return "up";
  if (label.startsWith("risk-off")) return "down";
  return "dim";
}
function _renderBrief(d) {
  if (!d || d.code === undefined) return '<div class="err">no data</div>';
  const p = d.price || {}, c = d.cot || {}, t = d.term_structure, r = d.regime || {};
  const posCls = c.positioning === "crowded long" ? "red" : c.positioning === "crowded short" ? "green" : "";
  const news = (d.news || []).map((h) =>
    `<div class="news-item"><a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}</a>
     <div class="news-meta"><span>${esc((h.date || "").slice(0, 16))}</span><span>${esc(h.source || "")}</span></div></div>`).join("");
  return `
    <div style="font-size:14px;margin-bottom:10px"><b>${esc(d.read || "")}</b></div>
    <div class="tiles">
      <div class="tile"><div class="label">Regime</div><div class="value ${_regimeCls(r.regime)}">${esc(r.regime || "—")}</div></div>
      <div class="tile"><div class="label">Close</div><div class="value">${num(p.close, 4)}</div><div class="sub">1w ${pct(p.change_1w_pct)}</div></div>
      <div class="tile"><div class="label">ATR(14)</div><div class="value">${num(p.atr_14_pct, 2)}%</div></div>
      ${c.positioning && c.positioning !== "n/a" ? `<div class="tile"><div class="label">COT</div><div class="value"><span class="pill ${posCls}">${esc(c.positioning)}</span></div><div class="sub">${num(c.percentile_1y, 0)}th pct 1y</div></div>` : ""}
      ${t && t.structure ? `<div class="tile"><div class="label">Curve</div><div class="value">${esc(t.structure)}</div><div class="sub">${pct(t.front_back_spread_pct)}</div></div>` : ""}
    </div>
    ${c.bias ? `<div class="sub" style="margin-top:8px">COT: ${esc(c.bias)}${c.weekly_shift && c.weekly_shift !== "n/a" ? " · " + esc(c.weekly_shift) : ""}</div>` : ""}
    ${news ? `<div style="margin-top:10px">${news}</div>` : '<div class="dim" style="margin-top:10px">no tagged news</div>'}`;
}

async function loadBrief(code) {
  const body = document.getElementById("brief-body");
  if (!body) return;
  body.innerHTML = `<div class="loading">Loading ${esc(code)} brief…</div>`;
  try {
    const env = await fetchJSON("/analysis/brief?instrument=" + encodeURIComponent(code));
    if (env.ok === false) { body.innerHTML = `<div class="err">${esc(env.error || "failed")}</div>`; return; }
    body.innerHTML = _renderBrief(env.data || {});
  } catch (e) {
    body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`;
  }
}

async function loadAnalysis() {
  const sec = $("#view-analysis");
  let regime = {}, cot = {};
  try { regime = (await fetchJSON("/analysis/regime")).data || {}; } catch (e) { /* degrade */ }
  try { cot = (await fetchJSON("/analysis/cot")).data || {}; } catch (e) { /* degrade */ }

  const rsig = (regime.signals || []).map((s) =>
    `<tr><td>${esc(s.name)}</td><td>${esc(s.reading)}</td><td class="${_regimeCls(s.leans)}">${esc(s.leans)}</td></tr>`).join("");
  const regimePanel = panel("Macro Regime", `
    <div class="tiles"><div class="tile"><div class="label">Regime</div>
      <div class="value ${_regimeCls(regime.regime)}">${esc(regime.regime || "—")}</div>
      <div class="sub">score ${num(regime.score, 0)}</div></div></div>
    <table style="margin-top:10px"><thead><tr><th>Signal</th><th>Reading</th><th>Leans</th></tr></thead><tbody>${rsig}</tbody></table>
    <div class="exec-help dim">${esc(regime.method || "")}</div>`);

  const rows = Object.entries(cot.signals || {}).map(([code, s]) => {
    if (!s.ok) return `<tr><td>${esc(code)}</td><td colspan="5" class="err">${esc(s.error || "n/a")}</td></tr>`;
    const posCls = s.positioning === "crowded long" ? "down" : s.positioning === "crowded short" ? "up" : "dim";
    return `<tr><td>${esc(code)} <span class="dim">${esc(s.name || "")}</span></td>
      <td>${num(s.non_commercial_net, 0)}</td><td>${num(s.percentile_1y, 0)}%</td>
      <td><span class="pill ${posCls === "down" ? "red" : posCls === "up" ? "green" : ""}">${esc(s.positioning)}</span></td>
      <td style="text-align:left">${esc(s.weekly_shift)}</td>
      <td style="text-align:left">${esc(s.bias)}</td></tr>`;
  }).join("");
  const extremes = (cot.extremes || []).length
    ? `<div class="sub" style="margin-bottom:8px">Extremes: <b class="amber">${(cot.extremes).map(esc).join(", ")}</b></div>` : "";
  const cotPanel = panel("COT Positioning Signals", extremes +
    `<table><thead><tr><th>Instrument</th><th>NC net</th><th>1y %ile</th><th>Positioning</th><th>Weekly shift</th><th>Bias</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="exec-help dim">${esc(cot.method || "")}</div>`);

  const briefPanel = panel("Instrument Brief — what's moving this contract", `
    <select id="brief-pick" class="btn">${["6E", "6B", "GC", "NQ", "YM"].map((k) => `<option${k === "GC" ? " selected" : ""}>${k}</option>`).join("")}</select>
    <div id="brief-body" style="margin-top:10px"></div>`);

  sec.innerHTML = `<div class="grid" style="grid-template-columns:1fr">${briefPanel}${regimePanel}${cotPanel}</div>
    <div class="exec-help dim" style="margin-top:8px">${esc(regime.disclaimer || cot.disclaimer || "")}</div>`;

  const pick = document.getElementById("brief-pick");
  if (pick) pick.addEventListener("change", () => loadBrief(pick.value));
  loadBrief(pick ? pick.value : "GC");
}

// My Watchlist tab (ROADMAP C6): add/remove arbitrary instruments across asset
// classes; each row shows price + change + the vol/regime read. Mutating calls
// (POST/DELETE) go through apiSend.
async function apiSend(path, method, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const r = await fetch(path, opts);
  if (r.status === 401) { window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname); throw new Error("unauthorized"); }
  if (!r.ok) { let m = `HTTP ${r.status}`; try { m = (await r.json()).detail || m; } catch (e) { /* */ } throw new Error(m); }
  return r.json();
}

const CUSTOM_ASSETS = ["crypto", "forex", "equity", "etf", "futures"];

function _customRows(insts) {
  if (!insts.length) return `<tr><td colspan="7" class="dim">Nothing yet — add one above (e.g. crypto <b>BTC-USD</b>, equity <b>AAPL</b>, etf <b>SPY</b>, forex <b>EURUSD</b>).</td></tr>`;
  return insts.map((v) => {
    const body = v.ok === false
      ? `<td colspan="5" class="err">${esc(v.error || "n/a")}</td>`
      : `<td>${num(v.last, 4)}</td><td>${pct(v.change_1d_pct)}</td><td>${pct(v.change_1w_pct)}</td>
         <td>${v.vol_annualized != null ? num(v.vol_annualized * 100, 1) + "%" : '<span class="dim">—</span>'}</td>
         <td>${v.regime ? _volPill(v.regime) : '<span class="dim">—</span>'}</td>`;
    return `<tr><td>${esc(v.label || v.symbol)} <span class="dim">${esc(v.asset)}</span></td>${body}
      <td><button class="btn rm" data-id="${esc(v.id)}" title="remove">✕</button></td></tr>`;
  }).join("");
}

async function loadCustom() {
  const sec = $("#view-custom");
  let env;
  try { env = await fetchJSON("/custom"); }
  catch (e) { sec.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; return; }
  const d = env.data || {};
  const opts = CUSTOM_ASSETS.map((a) => `<option value="${a}">${a}</option>`).join("");
  sec.innerHTML = panel("My Watchlist — add/remove any asset", `
    <div class="addbar">
      <select id="c-asset" class="btn">${opts}</select>
      <input id="c-symbol" class="inp" placeholder="symbol (BTC-USD, AAPL, EURUSD, GC=F)" />
      <button id="c-add" class="btn">+ Add</button>
      <span id="c-msg" class="dim"></span>
    </div>
    <table style="margin-top:10px"><thead><tr><th>Instrument</th><th>Last</th><th>1d</th><th>1w</th><th>Vol</th><th>Regime</th><th></th></tr></thead>
      <tbody>${_customRows(d.instruments || [])}</tbody></table>
    <div class="exec-help dim" style="margin-top:8px">${esc(d.disclaimer || "")} · saved per-instance (resets on redeploy unless a volume is attached).</div>`);

  const reload = () => loadCustom();
  const add = async () => {
    const asset = $("#c-asset").value, symbol = $("#c-symbol").value.trim();
    if (!symbol) return;
    $("#c-msg").textContent = "adding…";
    try { await apiSend("/custom", "POST", { asset, symbol }); await reload(); }
    catch (e) { const m = $("#c-msg"); if (m) m.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  };
  $("#c-add").addEventListener("click", add);
  $("#c-symbol").addEventListener("keydown", (ev) => { if (ev.key === "Enter") add(); });
  sec.querySelectorAll(".rm").forEach((b) => b.addEventListener("click", async () => {
    try { await apiSend("/custom/" + encodeURIComponent(b.dataset.id), "DELETE"); await reload(); } catch (e) { /* ignore */ }
  }));
}

// Focus tab (ROADMAP C4): one instrument → its volatility + the full "what's
// moving this contract" brief (regime, COT, term structure, momentum, news) on a
// single screen. Reuses /volatility/{code} and /analysis/brief.
function _renderVolCard(v) {
  if (!v || v.ok === false) return panelErr("Volatility & Regime", (v && v.error) || "n/a");
  const r = v.regime || {}, f = v.forecast || {};
  return panel("Volatility & Regime", `
    <div class="tiles">
      <div class="tile"><div class="label">Realized vol (ann.)</div><div class="value">${num((v.current_vol_annualized || 0) * 100, 1)}%</div></div>
      <div class="tile"><div class="label">Regime</div><div class="value">${_volPill(r.regime)}</div><div class="sub">${num(r.percentile, 0)}th pct ~3y</div></div>
      <div class="tile"><div class="label">${num(f.horizon_days, 0)}d forecast</div><div class="value">${num((f.ewma || 0) * 100, 1)}%</div><div class="sub">EWMA · HAR ${num((f.har_rv || 0) * 100, 1)}%</div></div>
    </div>
    <div class="sub" style="margin-top:6px">${esc(v.read || "")}</div>`);
}

async function loadFocusOne(code) {
  const body = document.getElementById("focus-body");
  if (!body) return;
  body.innerHTML = `<div class="loading">Loading ${esc(code)}…</div>`;
  let vol = null, brief = null;
  try { vol = (await fetchJSON("/volatility/" + encodeURIComponent(code))).data; } catch (e) { /* degrade */ }
  try { brief = (await fetchJSON("/analysis/brief?instrument=" + encodeURIComponent(code))).data; } catch (e) { /* degrade */ }
  body.innerHTML = `<div class="grid" style="grid-template-columns:1fr">
    ${_renderVolCard(vol)}
    ${panel("What's moving " + esc(code), brief ? _renderBrief(brief) : '<div class="err">unavailable</div>')}
  </div>`;
}

async function loadFocus() {
  const sec = $("#view-focus");
  const codes = ["GC", "NQ", "6E", "6B", "YM"];
  sec.innerHTML = panel("Instrument Focus — one symbol, everything",
    `<select id="focus-pick" class="btn">${codes.map((k) => `<option${k === "GC" ? " selected" : ""}>${k}</option>`).join("")}</select>
     <div id="focus-body" style="margin-top:12px"></div>`);
  const pick = document.getElementById("focus-pick");
  if (pick) pick.addEventListener("change", () => loadFocusOne(pick.value));
  loadFocusOne(pick ? pick.value : "GC");
}

// Lazy loading: only fetch the visible tab; fetch others when first opened (by
// then the background pre-cache has usually warmed them, so they appear fast).
const loaded = new Set();
let active = "macro";

// Admin tab (ROADMAP F2): list / create / disable users. Shown only to admins
// (initSession reveals the tab when /whoami reports role==='admin').
async function loadAdmin() {
  const sec = $("#view-admin");
  let env;
  try { env = await fetchJSON("/admin/users"); }
  catch (e) { sec.innerHTML = `<div class="err">admin only</div>`; return; }
  const rows = (env.users || []).map((u) => `<tr>
    <td>${esc(u.username)}</td>
    <td><span class="pill ${u.role === "admin" ? "amber" : ""}">${esc(u.role)}</span></td>
    <td>${u.disabled ? '<span class="down">disabled</span>' : '<span class="up">active</span>'}</td>
    <td><button class="btn ux" data-u="${esc(u.username)}" data-d="${u.disabled ? 0 : 1}">${u.disabled ? "Enable" : "Disable"}</button></td>
  </tr>`).join("");
  sec.innerHTML = panel("Users", `
    <div class="addbar">
      <input id="a-user" class="inp" placeholder="username (≥3)" />
      <input id="a-pass" class="inp" type="password" placeholder="password (≥8)" />
      <select id="a-role" class="btn"><option value="user">user</option><option value="admin">admin</option></select>
      <button id="a-add" class="btn">+ Create</button>
      <span id="a-msg" class="dim"></span>
    </div>
    <table style="margin-top:10px"><thead><tr><th>Username</th><th>Role</th><th>Status</th><th></th></tr></thead>
      <tbody>${rows || '<tr><td colspan="4" class="dim">no DB users yet (the env admin always works)</td></tr>'}</tbody></table>
    <div class="exec-help dim" style="margin-top:8px">Self-service sign-ups are ${env.registration_open ? "<b>open</b>" : "closed"} (set REGISTRATION_OPEN). The env admin is the bootstrap account.</div>`);

  const reload = () => loadAdmin();
  $("#a-add").addEventListener("click", async () => {
    const username = $("#a-user").value.trim(), password = $("#a-pass").value, role = $("#a-role").value;
    if (!username || !password) return;
    $("#a-msg").textContent = "creating…";
    try { await apiSend("/admin/users", "POST", { username, password, role }); await reload(); }
    catch (e) { const m = $("#a-msg"); if (m) m.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  });
  sec.querySelectorAll(".ux").forEach((b) => b.addEventListener("click", async () => {
    try { await apiSend(`/admin/users/${encodeURIComponent(b.dataset.u)}/disabled?disabled=${b.dataset.d}`, "POST"); await reload(); }
    catch (e) { /* ignore */ }
  }));
}

function _loadFor(view) {
  if (view === "execution") return loadExecution();
  if (view === "analysis") return loadAnalysis();
  if (view === "focus") return loadFocus();
  if (view === "custom") return loadCustom();
  if (view === "admin") return loadAdmin();
  return loadView(view);
}

async function showView(view) {
  active = view;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  if (!loaded.has(view)) {
    loaded.add(view);
    $("#status").textContent = `loading ${view}…`;
    await _loadFor(view);
    $("#status").textContent = "updated " + new Date().toLocaleTimeString();
  }
}

async function refreshActive() {
  $("#status").textContent = "refreshing…";
  await _loadFor(active);
  loaded.add(active);
  $("#status").textContent = "updated " + new Date().toLocaleTimeString();
}

function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => showView(tab.dataset.view)));
}

function tick() { $("#clock").textContent = new Date().toUTCString().slice(17, 25) + " UTC"; }

// Session bar (ROADMAP F1): show who's signed in + a sign-out link, but only on
// an auth-enabled (deployed) instance — keyless local dev shows nothing.
async function initSession() {
  try {
    const w = await fetchJSON("/whoami");
    if (w && w.auth_enabled && w.user) {
      $("#session").innerHTML =
        `<span class="dim">signed in as ${esc(w.user)}${w.role === "admin" ? " · admin" : ""}</span> <a class="btn" href="/logout">Sign out</a>`;
    }
    // Reveal the Admin tab only to admins.
    if (w && w.role === "admin") {
      const t = document.querySelector(".tab-admin");
      if (t) t.style.display = "";
    }
  } catch (e) { /* no session bar if unavailable */ }
}

initTabs();
initSession();
$("#refresh").addEventListener("click", refreshActive);
setInterval(tick, 1000); tick();
showView("macro"); // initial load = visible tab only
setInterval(() => loaded.forEach(_loadFor), 10 * 60 * 1000); // refresh opened tabs every 10 min
