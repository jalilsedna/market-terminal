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
  movers: "/screener/movers?top=20",
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

function _instrumentRows(insts) {
  const items = Object.values(insts || {});
  if (!items.length) {
    return `<tr><td colspan="8" class="dim">No instruments yet — add forex, futures, crypto, equity, or ETF symbols below. Try Alpaca search for US equities.</td></tr>`;
  }
  return items.map((i) => {
    if (!i.ok) {
      return `<tr><td>${esc(i.id || i.code || "")} <span class="dim">${esc(i.asset || "")}</span></td><td colspan="6" class="err">${esc(i.error)}</td><td><button class="btn rm" data-id="${esc(i.id)}" title="remove">✕</button></td></tr>`;
    }
    const f = i.future || {};
    const last = f.close != null ? f.close : i.last;
    const c1 = f.change_1d_pct != null ? f.change_1d_pct : i.change_1d_pct;
    const c1w = f.change_1w_pct != null ? f.change_1w_pct : i.change_1w_pct;
    const c1m = f.change_1m_pct != null ? f.change_1m_pct : i.change_1m_pct;
    const atr = i.atr_14 != null ? `${num(i.atr_14, 4)} <span class="dim">(${num(i.atr_14_pct, 2)}%)</span>` : '<span class="dim">—</span>';
    const vol = i.vol_annualized != null ? num(i.vol_annualized * 100, 1) + "%" : '<span class="dim">—</span>';
    const regime = i.regime ? _volPill(i.regime) : '<span class="dim">—</span>';
    const label = i.code || i.symbol;
    return `<tr>
      <td>${esc(label)} <span class="dim">${esc(i.name || i.label || "")} · ${esc(i.asset)}</span></td>
      <td>${num(last, 4)}</td><td>${pct(c1)}</td><td>${pct(c1w)}</td><td>${pct(c1m)}</td>
      <td>${atr}</td><td>${vol}</td><td>${regime}</td>
      <td><button class="btn rm" data-id="${esc(i.id)}" title="remove">✕</button></td></tr>`;
  }).join("");
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

// Movers tab (Flat Files): whole-market top gainers/losers/most-active for the
// latest session, from Massive's daily flat file (one download = every ticker).
function _fmtUSD(v) {
  if (v === null || v === undefined) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
  if (a >= 1e6) return "$" + (v / 1e6).toFixed(1) + "M";
  if (a >= 1e3) return "$" + (v / 1e3).toFixed(1) + "K";
  return "$" + num(v, 0);
}
function _moversTable(title, rows) {
  const body = (rows || []).map((r) => `<tr>
    <td><b>${esc(r.ticker)}</b></td><td>${num(r.close, 2)}</td>
    <td>${pct(r.change_1d_pct)}</td><td style="text-align:right">${_fmtUSD(r.dollar_volume)}</td></tr>`).join("");
  return panel(title, `<table><thead><tr><th>Ticker</th><th>Close</th><th>1d</th><th style="text-align:right">$ Vol</th></tr></thead>
    <tbody>${body || '<tr><td colspan="4" class="dim">none</td></tr>'}</tbody></table>`);
}
function renderMovers(env) {
  const d = env.data || {};
  const f = d.filters || {};
  const head = `<div class="sub" style="margin-bottom:8px">Whole US market — ${esc(d.as_of || "")} vs ${esc(d.prev || "")} · ${num(d.universe, 0)} liquid names (price ≥ $${num(f.min_price, 0)}, $vol ≥ ${_fmtUSD(f.min_dollar_volume)})</div>`;
  const grid = `<div class="grid">
    ${_moversTable("Top Gainers (1d)", d.gainers)}
    ${_moversTable("Top Losers (1d)", d.losers)}
    ${_moversTable("Most Active ($ vol)", d.most_active)}</div>`;
  return head + grid + `<div class="exec-help dim" style="margin-top:8px">${esc(d.disclaimer || "")}</div>`;
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

const RENDERERS = { macro: renderMacro, cot: renderCot, term: renderTerm, volatility: renderVolatility, sectors: renderSectors, movers: renderMovers, news: renderNews };

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

  const briefOpts = await _instrumentOptions("");
  const briefPanel = panel("Instrument Brief — what's moving this symbol", `
    <select id="brief-pick" class="btn">${briefOpts}</select>
    <div id="brief-body" class="mt-md"></div>`);

  sec.innerHTML = `<div class="grid grid-1">${briefPanel}${regimePanel}${cotPanel}</div>
    <div class="exec-help dim mt-sm">${esc(regime.disclaimer || cot.disclaimer || "")}</div>`;

  const pick = document.getElementById("brief-pick");
  if (pick && pick.value) {
    pick.addEventListener("change", () => loadBrief(pick.value));
    loadBrief(pick.value);
  } else if (document.getElementById("brief-body")) {
    document.getElementById("brief-body").innerHTML = '<div class="dim">Add instruments in the Registry tab first.</div>';
  }
}

async function _instrumentOptions(selectedId) {
  try {
    const env = await fetchJSON("/instruments");
    const list = (env.data || {}).instruments || [];
    if (!list.length) return '<option value="">— add instruments first —</option>';
    return list.map((i) => {
      const id = i.id;
      const lbl = i.label || i.symbol;
      return `<option value="${esc(id)}"${id === selectedId ? " selected" : ""}>${esc(lbl)} (${esc(i.asset)})</option>`;
    }).join("");
  } catch (e) {
    return '<option value="">unavailable</option>';
  }
}

// Instrument registry: add/remove any asset class; Alpaca search for US equities.
async function apiSend(path, method, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const r = await fetch(path, opts);
  if (r.status === 401) { window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname); throw new Error("unauthorized"); }
  if (!r.ok) { let m = `HTTP ${r.status}`; try { m = (await r.json()).detail || m; } catch (e) { /* */ } throw new Error(m); }
  return r.json();
}

const ASSET_CLASSES = ["futures", "crypto", "forex", "equity", "etf"];
const ASSET_PLACEHOLDER = {
  futures: "type GC, NQ, CL…",
  crypto: "type BTC, ETH, SOL…",
  forex: "type EUR, GBP, AUD…",
  equity: "type AAPL, MSFT, NVDA…",
  etf: "type SPY, QQQ, GLD…",
};

function _bindSymbolAutocomplete(addFn) {
  const input = $("#c-symbol");
  const list = $("#c-suggest");
  const assetSel = $("#c-asset");
  if (!input || !list) return;

  let hits = [];
  let activeIdx = -1;
  let timer = null;

  const hide = () => { list.classList.add("hidden"); activeIdx = -1; };
  const show = () => list.classList.remove("hidden");

  const render = () => {
    if (!hits.length) {
      list.innerHTML = '<div class="ac-empty">no matches — check asset class & spelling</div>';
      show();
      return;
    }
    list.innerHTML = hits.map((h, i) =>
      `<button type="button" class="ac-item${i === activeIdx ? " active" : ""}" data-idx="${i}">
        <span class="sym">${esc(h.symbol)}</span><span class="nm">${esc(h.name || "")}</span>
      </button>`).join("");
    list.querySelectorAll(".ac-item").forEach((btn) => {
      btn.addEventListener("mousedown", (ev) => {
        ev.preventDefault();
        const h = hits[Number(btn.dataset.idx)];
        if (h) { input.value = h.symbol; hide(); addFn(assetSel.value, h.symbol); }
      });
    });
    show();
  };

  const fetchHits = async () => {
    const q = input.value.trim();
    const asset = assetSel.value;
    if (q.length < 1) { hits = []; hide(); return; }
    try {
      const r = await fetchJSON(
        "/instruments/search?asset=" + encodeURIComponent(asset) + "&query=" + encodeURIComponent(q) + "&limit=20"
      );
      hits = (r.data || {}).results || [];
      activeIdx = hits.length ? 0 : -1;
      render();
    } catch (e) {
      list.innerHTML = `<div class="ac-empty">${esc(e.message)}</div>`;
      show();
    }
  };

  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(fetchHits, 200);
  });
  input.addEventListener("focus", () => { if (input.value.trim()) fetchHits(); });
  input.addEventListener("blur", () => setTimeout(hide, 150));
  input.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown") {
      ev.preventDefault();
      if (!hits.length) return;
      activeIdx = Math.min(activeIdx + 1, hits.length - 1);
      render();
    } else if (ev.key === "ArrowUp") {
      ev.preventDefault();
      activeIdx = Math.max(activeIdx - 1, 0);
      render();
    } else if (ev.key === "Enter") {
      ev.preventDefault();
      if (activeIdx >= 0 && hits[activeIdx]) {
        input.value = hits[activeIdx].symbol;
        hide();
        addFn(assetSel.value, hits[activeIdx].symbol);
      } else {
        addFn(assetSel.value, input.value.trim());
      }
    } else if (ev.key === "Escape") hide();
  });
  assetSel.addEventListener("change", () => {
    input.placeholder = ASSET_PLACEHOLDER[assetSel.value] || "type to search…";
    hits = [];
    hide();
    if (input.value.trim()) fetchHits();
  });
  input.placeholder = ASSET_PLACEHOLDER[assetSel.value] || "type to search…";
}

async function loadInstruments() {
  const sec = $("#view-watchlist");
  let env;
  try { env = await fetchJSON("/watchlist"); }
  catch (e) { sec.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; return; }
  const d = env.data || {};
  const opts = ASSET_CLASSES.map((a) => `<option value="${a}">${a}</option>`).join("");
  sec.innerHTML = panel("Instrument registry — track any asset", `
    <div class="sub mb-sm">Pick an asset class, then type the first letters — a dropdown suggests valid symbols. Equity/ETF uses Alpaca; forex/crypto/futures use built-in catalogs.</div>
    <div class="addbar">
      <select id="c-asset" class="btn">${opts}</select>
      <div class="ac-wrap">
        <input id="c-symbol" class="inp" autocomplete="off" spellcheck="false" placeholder="type to search…" />
        <div id="c-suggest" class="ac-list hidden"></div>
      </div>
      <button id="c-add" class="btn">+ Add</button>
      <span id="c-msg" class="dim"></span>
    </div>
    <table class="mt-md"><thead><tr><th>Instrument</th><th>Last</th><th>1d</th><th>1w</th><th>1m</th><th>ATR</th><th>Vol</th><th>Regime</th><th></th></tr></thead>
      <tbody>${_instrumentRows(d.instruments)}</tbody></table>
    <div class="exec-help dim mt-sm">${esc(d.disclaimer || "")} · persisted in SQLite (attach a volume on Railway).</div>`);

  const reload = () => loadInstruments();
  const add = async (asset, symbol) => {
    const sym = (symbol || "").trim();
    if (!sym) return;
    $("#c-msg").textContent = "adding…";
    try { await apiSend("/instruments", "POST", { asset, symbol: sym }); await reload(); }
    catch (e) { const m = $("#c-msg"); if (m) m.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  };
  _bindSymbolAutocomplete(add);
  $("#c-add").addEventListener("click", () => add($("#c-asset").value, $("#c-symbol").value.trim()));
  sec.querySelectorAll(".rm").forEach((b) => b.addEventListener("click", async () => {
    try { await apiSend("/instruments/" + encodeURIComponent(b.dataset.id), "DELETE"); await reload(); } catch (e) { /* */ }
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
  const opts = await _instrumentOptions("");
  sec.innerHTML = panel("Instrument Focus — one symbol, everything",
    `<select id="focus-pick" class="btn">${opts}</select>
     <div id="focus-body" class="mt-md"></div>`);
  const pick = document.getElementById("focus-pick");
  if (pick && pick.value) {
    pick.addEventListener("change", () => loadFocusOne(pick.value));
    loadFocusOne(pick.value);
  } else {
    $("#focus-body").innerHTML = '<div class="dim">Add instruments in the Registry tab first.</div>';
  }
}

// Chart tab: embeds TradingView's Advanced Chart widget (its full TA toolset).
// TradingView is the chart's DISPLAY data source — every number elsewhere in the
// terminal still comes through OpenBB. Symbols come from /chart/symbols (the one
// explicit map in obb_layer/symbols.py), with a free-form box for anything else.
let _tvLoading = null;
function ensureTradingView() {
  if (window.TradingView && window.TradingView.widget) return Promise.resolve();
  if (_tvLoading) return _tvLoading;
  _tvLoading = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://s3.tradingview.com/tv.js";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => { _tvLoading = null; reject(new Error("could not load TradingView (network/blocked)")); };
    document.head.appendChild(s);
  });
  return _tvLoading;
}

async function renderTVChart(containerId, symbol) {
  const el = document.getElementById(containerId);
  if (!el) return;
  try { await ensureTradingView(); }
  catch (e) { el.innerHTML = `<div class="err">${esc(e.message)} — try the "Open in TradingView ↗" link.</div>`; return; }
  el.innerHTML = ""; // tear down any previous widget before re-creating
  // eslint-disable-next-line no-undef
  new TradingView.widget({
    container_id: containerId,
    symbol: symbol || "COMEX:GC1!",
    interval: "D",
    timezone: "Etc/UTC",
    theme: "dark",
    style: "1",
    locale: "en",
    toolbar_bg: "#131722",
    enable_publishing: false,
    allow_symbol_change: true,
    hide_side_toolbar: false,
    autosize: true,
  });
}

// TradingView strategy/alert signals (G3) received via webhook — research only.
function _tvSignalsPanel(sig) {
  if (!sig || sig.enabled === false) {
    return panel("TradingView Signals", '<div class="dim">No webhook configured. Set <code>TV_WEBHOOK_SECRET</code> and point a TradingView alert at <code>/webhook/tradingview?token=…</code> to stream your Pine strategy/alert signals here.</div>');
  }
  const rows = (sig.signals || []).map((s) => `<tr>
    <td style="text-align:left">${esc((s.ts || "").slice(0, 16).replace("T", " "))}</td>
    <td><b>${esc(s.ticker || "—")}</b></td>
    <td>${s.action ? `<span class="pill">${esc(s.action)}</span>` : '<span class="dim">—</span>'}</td>
    <td>${esc(s.price || "—")}</td>
    <td style="text-align:left" class="dim">${esc(s.text || "")}</td></tr>`).join("");
  return panel(`TradingView Signals${sig.count ? " · " + num(sig.count, 0) : ""}`,
    rows
      ? `<table><thead><tr><th>Time</th><th>Ticker</th><th>Action</th><th>Price</th><th style="text-align:left">Message</th></tr></thead><tbody>${rows}</tbody></table>
         <div class="exec-help dim" style="margin-top:6px">${esc(sig.disclaimer || "")}</div>`
      : '<div class="dim">No signals yet — fire a TradingView alert at this terminal\'s webhook.</div>');
}

async function loadChart() {
  const sec = $("#view-chart");
  let picks = [], sig = {};
  try { picks = ((await fetchJSON("/chart/symbols")).data || {}).picks || []; } catch (e) { /* free-form still works */ }
  try { sig = (await fetchJSON("/tradingview/signals?limit=15")).data || {}; } catch (e) { /* panel degrades */ }
  const quick = picks.map((p) => `<button class="btn tv-pick" data-sym="${esc(p.tv_symbol)}" title="${esc(p.name)}">${esc(p.code)}</button>`).join("");
  sec.innerHTML = _tvSignalsPanel(sig) + panel("Chart — TradingView", `
    <div class="addbar">
      <input id="tv-input" class="inp" placeholder="TradingView symbol (e.g. COMEX:GC1!, NASDAQ:AAPL, BINANCE:BTCUSDT, FX:EURUSD)" />
      <button id="tv-go" class="btn">Load</button>
      <a id="tv-ext" class="btn" href="#" target="_blank" rel="noopener">Open in TradingView ↗</a>
      ${quick ? `<span class="dim">quick:</span> ${quick}` : ""}
    </div>
    <div id="tv-chart" class="tv-chart"></div>
    <div class="exec-help dim" style="margin-top:8px">Chart data is TradingView's (entitlement-dependent, often delayed). Visual research context only — the terminal's own numbers come through OpenBB. Not a trade trigger.</div>`);

  const ext = $("#tv-ext");
  const go = (sym) => {
    const s = (sym || $("#tv-input").value).trim();
    if (!s) return;
    $("#tv-input").value = s;
    if (ext) ext.href = "https://www.tradingview.com/chart/?symbol=" + encodeURIComponent(s);
    renderTVChart("tv-chart", s);
  };
  $("#tv-go").addEventListener("click", () => go());
  $("#tv-input").addEventListener("keydown", (ev) => { if (ev.key === "Enter") go(); });
  sec.querySelectorAll(".tv-pick").forEach((b) => b.addEventListener("click", () => go(b.dataset.sym)));
  go(picks[0] ? picks[0].tv_symbol : "COMEX:GC1!");
}

// Lazy loading: only fetch the visible view when first opened (by then the
// background pre-cache has usually warmed it, so it appears fast).
const loaded = new Set();
let active = "macro";

const VIEW_TITLES = {
  macro: "Macro",
  analysis: "Analysis",
  news: "News",
  focus: "Focus",
  watchlist: "Registry",
  chart: "Chart",
  cot: "COT",
  term: "Term Structure",
  volatility: "Volatility",
  sectors: "Sectors",
  movers: "Movers",
  fundamentals: "Stock Brain",
  history: "History & Alerts",
  execution: "Execution · Alice",
  admin: "Admin",
};

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

// History ▸ Alerts tab (ROADMAP C5): charts the recorded daily snapshots
// (vol/regime per instrument, macro regime) and lets you set research alert
// rules over them. Both read /history + /alerts — no new data fetching.
const REGIME_COLOR = {
  calm: "#26a69a", normal: "#7a8294", elevated: "#ffb300", stressed: "#ef5350",
  "risk-on": "#26a69a", "risk-off": "#ef5350", neutral: "#7a8294",
};
const _regimeColor = (r) => REGIME_COLOR[String(r || "").toLowerCase()] || "#7a8294";

// Inline SVG line chart of a snapshot series (no chart lib — fits the terminal).
// Points arrive newest-first; we reverse to chronological. Picks the first
// numeric metric present (vol→%, score, percentile) and draws a regime band.
function _chart(points) {
  const pts = (points || []).slice().reverse();
  const has = (k) => pts.some((p) => p.value && p.value[k] != null);
  let metric, label, scale = 1;
  if (has("vol")) { metric = "vol"; label = "annualized vol %"; scale = 100; }
  else if (has("score")) { metric = "score"; label = "macro regime score"; }
  else if (has("percentile")) { metric = "percentile"; label = "percentile"; }
  else return '<div class="dim">no numeric metric to chart in this series.</div>';

  const xs = [], ys = [], regimes = [];
  pts.forEach((p) => {
    const v = p.value || {};
    if (v[metric] != null) { xs.push(p.ts); ys.push(v[metric] * scale); regimes.push(v.regime); }
  });
  const n = ys.length;
  if (n < 2) return `<div class="dim">not enough history yet (${n} point${n === 1 ? "" : "s"}) — the chart fills in as daily snapshots accrue.</div>`;

  const min = Math.min(...ys), max = Math.max(...ys), span = (max - min) || 1;
  const W = 1000, H = 220, padL = 8, padR = 8, padT = 12, padB = 26;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const X = (i) => padL + (i / (n - 1)) * innerW;
  const Y = (v) => padT + innerH - ((v - min) / span) * innerH;
  const poly = ys.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  const bw = innerW / n, bandY = H - padB + 4;
  const band = regimes.map((r, i) => r
    ? `<rect x="${(X(i) - bw / 2).toFixed(1)}" y="${bandY}" width="${bw.toFixed(1)}" height="6" fill="${_regimeColor(r)}"/>` : "").join("");
  const last = ys[n - 1], lastR = regimes[n - 1];
  return `
    <div class="chart-head"><span class="dim">${esc(label)}</span>
      <span>last <b>${num(last, 2)}</b>${lastR ? " " + _volPill(lastR) : ""} · range ${num(min, 2)}–${num(max, 2)} · ${n} pts</span></div>
    <svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(label)} history">
      <polyline fill="none" stroke="var(--accent)" stroke-width="2" points="${poly}"/>
      <circle cx="${X(n - 1).toFixed(1)}" cy="${Y(last).toFixed(1)}" r="3.5" fill="var(--accent)"/>
      ${band}
    </svg>
    <div class="chart-axis dim"><span>${esc((xs[0] || "").slice(0, 10))}</span><span>${esc((xs[n - 1] || "").slice(0, 10))}</span></div>`;
}

const _ALERT_OPS = { regime: ["==", "!="], percentile: [">=", ">", "<=", "<"], vol: [">=", ">", "<=", "<"], score: [">=", ">", "<=", "<"] };
const _ALERT_PH = { regime: "stressed / elevated / risk-off", percentile: "0–100", vol: "fraction e.g. 0.25", score: "number" };

async function loadHistory() {
  const sec = $("#view-history");
  let seriesList = [], al = {};
  try { seriesList = ((await fetchJSON("/history")).data || {}).series || []; } catch (e) { /* degrade */ }
  try { al = (await fetchJSON("/alerts")).data || {}; } catch (e) { /* degrade */ }

  const aRows = (al.alerts || []).map((a) => {
    const state = !a.enabled ? '<span class="dim">off</span>'
      : a.status !== "ok" ? `<span class="dim">${esc(a.status)}</span>`
      : a.triggered ? '<span class="pill red">TRIGGERED</span>' : '<span class="pill green">ok</span>';
    const cur = a.current == null ? "—" : (typeof a.current === "number" ? num(a.current, 2) : esc(a.current));
    return `<tr><td>${esc(a.label)}</td><td>${esc(a.series)}</td>
      <td>${esc(a.metric)} ${esc(a.op)} ${esc(a.threshold)}</td><td>${cur}</td><td>${state}</td>
      <td><button class="btn al-tog" data-id="${esc(a.id)}" data-e="${a.enabled ? 0 : 1}">${a.enabled ? "Disable" : "Enable"}</button>
          <button class="btn rm al-rm" data-id="${esc(a.id)}" title="remove">✕</button></td></tr>`;
  }).join("");

  const badge = al.triggered_count ? ` · <span class="pill red">${num(al.triggered_count, 0)} triggered</span>` : "";
  const alertsPanel = panel("Alerts" + badge, `
    <div class="addbar">
      <input id="al-series" class="inp" list="al-series-list" placeholder="series (vol:GC, regime:macro)" />
      <datalist id="al-series-list">${seriesList.map((s) => `<option value="${esc(s)}"></option>`).join("")}</datalist>
      <select id="al-metric" class="btn">${["regime", "percentile", "vol", "score"].map((m) => `<option>${m}</option>`).join("")}</select>
      <select id="al-op" class="btn"></select>
      <input id="al-th" class="inp" style="max-width:130px" placeholder="threshold" />
      <button id="al-add" class="btn">+ Add</button>
      <span id="al-msg" class="dim"></span>
    </div>
    <table style="margin-top:10px"><thead><tr><th>Label</th><th>Series</th><th>Condition</th><th>Current</th><th>State</th><th></th></tr></thead>
      <tbody>${aRows || '<tr><td colspan="6" class="dim">No alerts yet — add one (e.g. series <b>vol:GC</b>, metric <b>regime</b> <b>==</b> <b>stressed</b>).</td></tr>'}</tbody></table>
    <div class="exec-help dim" style="margin-top:8px">${esc(al.disclaimer || "")}</div>`);

  const chartPanel = panel("History Chart", seriesList.length
    ? `<select id="h-series" class="btn">${seriesList.map((s) => `<option>${esc(s)}</option>`).join("")}</select>
       <div id="h-chart" style="margin-top:12px"></div>`
    : '<div class="dim">No history recorded yet — daily snapshots (vol/regime per instrument, macro regime) accrue once the pre-cache warmer has run. Check back after a day or two of uptime.</div>');

  sec.innerHTML = `<div class="grid" style="grid-template-columns:1fr">${alertsPanel}${chartPanel}</div>`;

  const syncOps = () => {
    const m = $("#al-metric").value;
    $("#al-op").innerHTML = _ALERT_OPS[m].map((o) => `<option>${o}</option>`).join("");
    $("#al-th").placeholder = _ALERT_PH[m];
  };
  if ($("#al-metric")) { $("#al-metric").addEventListener("change", syncOps); syncOps(); }

  const addAlert = async () => {
    const series = $("#al-series").value.trim(), metric = $("#al-metric").value;
    const op = $("#al-op").value, threshold = $("#al-th").value.trim();
    if (!series || !threshold) { $("#al-msg").textContent = "series + threshold required"; return; }
    $("#al-msg").textContent = "adding…";
    try { await apiSend("/alerts", "POST", { series, metric, op, threshold }); await loadHistory(); refreshAlertBadge(); }
    catch (e) { const m = $("#al-msg"); if (m) m.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  };
  if ($("#al-add")) { $("#al-add").addEventListener("click", addAlert); $("#al-th").addEventListener("keydown", (ev) => { if (ev.key === "Enter") addAlert(); }); }
  sec.querySelectorAll(".al-rm").forEach((b) => b.addEventListener("click", async () => {
    try { await apiSend("/alerts/" + encodeURIComponent(b.dataset.id), "DELETE"); await loadHistory(); refreshAlertBadge(); } catch (e) { /* */ }
  }));
  sec.querySelectorAll(".al-tog").forEach((b) => b.addEventListener("click", async () => {
    try { await apiSend("/alerts/" + encodeURIComponent(b.dataset.id) + "/enabled?enabled=" + b.dataset.e, "POST"); await loadHistory(); refreshAlertBadge(); } catch (e) { /* */ }
  }));

  const hpick = $("#h-series");
  if (hpick) {
    const draw = async () => {
      const box = $("#h-chart");
      box.innerHTML = '<div class="loading">loading…</div>';
      try { const pts = ((await fetchJSON("/history/" + encodeURIComponent(hpick.value))).data || {}).points || []; box.innerHTML = _chart(pts); }
      catch (e) { box.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
    };
    hpick.addEventListener("change", draw); draw();
  }
}

// Header badge: count of triggered alerts, refreshed on load + with opened tabs.
async function refreshAlertBadge() {
  try {
    const d = (await fetchJSON("/alerts")).data || {};
    const b = $("#alert-badge");
    if (!b) return;
    if (d.triggered_count > 0) { b.textContent = d.triggered_count; b.classList.remove("hidden"); }
    else b.classList.add("hidden");
  } catch (e) { /* no badge if unavailable */ }
}

// Fundamentals tab (ROADMAP H, Phase 1): per-ticker bottom-up view from FMP —
// profile, valuation, quality/health, growth, peers.
function _fmtBig(v) {
  if (v === null || v === undefined) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return "$" + (v / 1e12).toFixed(2) + "T";
  if (a >= 1e9) return "$" + (v / 1e9).toFixed(2) + "B";
  if (a >= 1e6) return "$" + (v / 1e6).toFixed(1) + "M";
  return "$" + num(v, 0);
}
const _pctv = (v, d = 1) => (v === null || v === undefined ? "—" : num(v * 100, d) + "%");
function _fundTile(label, value, sub) {
  return `<div class="tile"><div class="label">${esc(label)}</div><div class="value">${value}</div>${sub ? `<div class="sub">${esc(sub)}</div>` : ""}</div>`;
}

const _CONV_CLASS = { constructive: "green", cautious: "red", neutral: "amber", insufficient: "" };

function renderFundamentals(env) {
  const d = env.data || {};
  // /brain nests the dashboard under `fundamentals`; tolerate a raw dashboard too.
  const fd = d.fundamentals || d;
  const p = fd.profile || {}, v = fd.valuation || {}, q = fd.quality || {}, g = fd.growth || {};
  const dcf = fd.dcf || {}, an = fd.analyst || {}, ea = fd.earnings || {};
  const head = `<div class="sub" style="margin-bottom:8px">
    <b>${esc(p.name || fd.symbol)}</b> <span class="dim">${esc(fd.symbol)}</span> · ${esc(p.sector || "—")} / ${esc(p.industry || "—")}
    · ${esc(p.exchange || "")} · mkt cap ${_fmtBig(p.market_cap)} · β ${num(p.beta, 2)}</div>`;

  // Decision hero — the RESULT (H5 brain): conviction + summary + drivers.
  const conv = d.conviction;
  const c = d.components || {};
  const flags = (d.flags || []).map((x) => `<span class="pill amber" style="margin:2px">${esc(x)}</span>`).join(" ");
  const heroPanel = conv ? panel("Decision", `
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span class="pill ${_CONV_CLASS[conv] || ""}" style="font-size:13px">${esc(conv.toUpperCase())}</span>
      <span style="font-size:14px"><b>${esc(d.summary || "")}</b></span></div>
    <div class="sub" style="margin-top:8px">score ${num(d.score, 0)}
      (bottom-up ${num(c.bottom_up, 0)} · analyst ${num(c.analyst, 0)} · macro ${num(c.macro, 0)})
      · regime ${esc(c.macro_regime || "—")}</div>
    ${flags ? `<div style="margin-top:6px">${flags}</div>` : ""}`) : "";

  const valuation = panel("Valuation", `<div class="tiles">
    ${_fundTile("P/E", num(v.pe, 1), v.pe_median != null ? "5y med " + num(v.pe_median, 0) : "")}${_fundTile("P/S", num(v.ps, 1))}${_fundTile("P/B", num(v.pb, 1))}
    ${_fundTile("EV/EBITDA", num(v.ev_ebitda, 1))}${_fundTile("Div yield", _pctv(v.dividend_yield))}
    ${_fundTile("FCF yield", _pctv(v.fcf_yield))}</div>`);

  const dcfAnalyst = panel("DCF & Analyst", `<div class="tiles">
    ${_fundTile("DCF fair value", dcf.fair_value != null ? "$" + num(dcf.fair_value, 2) : "—", dcf.gap != null ? (dcf.gap > 0 ? "undervalued" : "overvalued") : "")}
    ${_fundTile("DCF gap", dcf.gap != null ? pct(dcf.gap * 100, 0) : "—")}
    ${_fundTile("Analyst target", an.target != null ? "$" + num(an.target, 2) : "—", an.rating ? String(an.rating) : "")}
    ${_fundTile("Implied upside", an.upside != null ? pct(an.upside * 100, 0) : "—")}
    ${_fundTile("Next earnings", ea.next_date || "—", ea.days_away != null ? ea.days_away + "d away" : "")}</div>`);
  const quality = panel("Quality & Health", `<div class="tiles">
    ${_fundTile("Piotroski", num(q.piotroski, 0), "0–9, higher better")}
    ${_fundTile("Altman Z", num(q.altman_z, 2), ">3 safe")}
    ${_fundTile("ROE", _pctv(q.roe))}${_fundTile("ROIC", _pctv(q.roic))}
    ${_fundTile("Net margin", _pctv(q.net_margin))}${_fundTile("Debt/Equity", num(q.debt_to_equity, 2))}</div>`);
  const growth = panel("Growth (latest FY)", `<div class="tiles">
    ${_fundTile("Revenue", _pctv(g.revenue))}${_fundTile("EPS", _pctv(g.eps))}
    ${_fundTile("Net income", _pctv(g.net_income))}</div>`);
  const peers = (fd.peers || []).length
    ? panel("Peers", (fd.peers).map((s) => `<span class="pill" style="margin:2px">${esc(s)}</span>`).join(" ")) : "";
  const desc = p.description ? panel("About", `<div class="sub">${esc(p.description)}</div>`) : "";
  const errs = fd.errors ? `<div class="exec-help dim" style="margin-top:8px">unavailable: ${esc(Object.keys(fd.errors).join(", "))} (FMP tier / endpoint)</div>` : "";
  return head + heroPanel + `<div class="grid" style="grid-template-columns:1fr">${valuation}${dcfAnalyst}${quality}${growth}${peers}${desc}</div>`
    + `<div class="exec-help dim" style="margin-top:8px">${esc(d.disclaimer || fd.disclaimer || "")}</div>` + errs;
}

function renderBrainScreen(env) {
  const d = env.data || {};
  const rows = d.ranked || [];
  if (!rows.length) return `<div class="sub dim">No fundamentals-capable instruments tracked. Add equities/ETFs in Watchlist, or screen explicit tickers above.</div>`;
  const head = `<div class="sub" style="margin-bottom:6px">${rows.length} ranked · ${esc(d.universe || "")} universe · regime ${esc(d.regime || "—")}</div>`;
  const body = rows.map((r) => {
    const conv = r.conviction || "—";
    const drivers = r.components
      ? `<span class="dim">bu ${num(r.components.bottom_up, 0)} · an ${num(r.components.analyst, 0)} · mac ${num(r.components.macro, 0)}</span>`
      : (r.error ? `<span class="dim">${esc(r.error)}</span>` : "");
    return `<tr>
      <td><b>${esc(r.symbol)}</b></td>
      <td><span class="pill ${_CONV_CLASS[conv] || ""}">${esc(String(conv).toUpperCase())}</span></td>
      <td style="text-align:right">${r.score == null ? "—" : num(r.score, 0)}</td>
      <td class="sub">${esc(r.summary || "")} ${drivers}</td>
    </tr>`;
  }).join("");
  return head + `<table style="margin-top:6px"><thead><tr><th>Symbol</th><th>Conviction</th><th style="text-align:right">Score</th><th>Read</th></tr></thead><tbody>${body}</tbody></table>`;
}

async function loadFundamentals() {
  const sec = $("#view-fundamentals");
  sec.innerHTML =
    panel("Brain Screen — rank conviction", `
      <div class="addbar">
        <input id="scr-input" class="inp" placeholder="tickers e.g. AAPL,MSFT,NVDA (blank = tracked equities/ETFs)" />
        <button id="scr-go" class="btn">Screen</button>
      </div>
      <div id="scr-body" style="margin-top:12px"><div class="sub dim">Run a screen to rank the universe by conviction.</div></div>`)
    + panel("Stock Brain — enter a ticker", `
      <div class="addbar">
        <input id="fund-input" class="inp" placeholder="ticker (e.g. AAPL, MSFT, NVDA)" value="AAPL" />
        <button id="fund-go" class="btn">Load</button>
      </div>
      <div id="fund-body" style="margin-top:12px"></div>`);

  const body = $("#fund-body");
  const go = async () => {
    const t = ($("#fund-input").value || "").trim().toUpperCase();
    if (!t) return;
    body.innerHTML = `<div class="loading">Loading ${esc(t)}…</div>`;
    try {
      const env = await fetchJSON("/brain/" + encodeURIComponent(t));  // brain → verdict + fundamentals
      if (env.ok === false) { body.innerHTML = `<div class="err">${esc(env.error || "unavailable")}</div>`; return; }
      body.innerHTML = renderFundamentals(env);
    } catch (e) { body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; }
  };
  $("#fund-go").addEventListener("click", go);
  $("#fund-input").addEventListener("keydown", (ev) => { if (ev.key === "Enter") go(); });

  const scrBody = $("#scr-body");
  const screen = async () => {
    const syms = ($("#scr-input").value || "").trim();
    scrBody.innerHTML = `<div class="loading">Screening…</div>`;
    try {
      const q = syms ? "?symbols=" + encodeURIComponent(syms) : "";
      const env = await fetchJSON("/brain/screen" + q);
      if (env.ok === false) { scrBody.innerHTML = `<div class="err">${esc(env.error || "unavailable")}</div>`; return; }
      scrBody.innerHTML = renderBrainScreen(env);
    } catch (e) { scrBody.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; }
  };
  $("#scr-go").addEventListener("click", screen);
  $("#scr-input").addEventListener("keydown", (ev) => { if (ev.key === "Enter") screen(); });

  go();
}

function _loadFor(view) {
  if (view === "fundamentals") return loadFundamentals();
  if (view === "execution") return loadExecution();
  if (view === "analysis") return loadAnalysis();
  if (view === "focus") return loadFocus();
  if (view === "watchlist") return loadInstruments();
  if (view === "admin") return loadAdmin();
  if (view === "history") return loadHistory();
  if (view === "chart") return loadChart();
  return loadView(view);
}

function closeSidebar() {
  $("#sidebar")?.classList.remove("open");
  $("#sidebar-backdrop")?.classList.remove("open");
}

async function showView(view) {
  active = view;
  document.querySelectorAll(".nav-item").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  const title = $("#view-title");
  if (title) title.textContent = VIEW_TITLES[view] || view;
  closeSidebar();
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

function initNav() {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => showView(item.dataset.view));
  });
  const toggle = $("#sidebar-toggle");
  const backdrop = $("#sidebar-backdrop");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const open = $("#sidebar").classList.toggle("open");
      backdrop?.classList.toggle("open", open);
    });
  }
  if (backdrop) backdrop.addEventListener("click", closeSidebar);
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
    // Reveal the Admin nav item only to admins.
    if (w && w.role === "admin") {
      const t = document.querySelector(".nav-admin");
      if (t) t.classList.remove("hidden");
    }
  } catch (e) { /* no session bar if unavailable */ }
}

initNav();
initSession();
refreshAlertBadge();
$("#refresh").addEventListener("click", refreshActive);
setInterval(tick, 1000); tick();
showView("macro"); // initial load = visible tab only
// Refresh opened tabs every 10 min — but skip "chart": TradingView's widget
// self-updates, and re-creating it would reset the user's zoom/drawings.
setInterval(() => loaded.forEach((v) => { if (v !== "chart") _loadFor(v); }), 10 * 60 * 1000);
