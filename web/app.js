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
function panelNote(title, msg) {
  return panel(title, `<div class="dim">${esc(msg || "unavailable")}</div>`);
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

function _renderCotCard(c) {
  if (c.ok === false) return panelErr(`${c.code || ""} ${c.name || ""}`, c.error);
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
}

function renderCot(env) {
  const d = env.data || {};
  const cards = Object.values(d).map((c) => _renderCotCard(c)).join("");
  return `<div class="grid">${cards}</div>`;
}

function renderTerm(env) {
  const d = env.data || {};
  const cards = Object.values(d).map((t) => {
    if (t.unavailable) return panelNote(`${t.code || ""} ${t.name || ""}`, t.note);
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

async function _cotInstrumentOptions(selectedId) {
  try {
    const env = await fetchJSON("/instruments");
    const list = ((env.data || {}).instruments || []).filter((i) => i.capabilities && i.capabilities.cot);
    if (!list.length) {
      return {
        html: '<option value="">— add futures (GC, NQ, 6E…) in Registry —</option>',
        labels: {},
      };
    }
    const labels = {};
    const html = list.map((i) => {
      labels[i.id] = i.label || i.symbol;
      return `<option value="${esc(i.id)}"${i.id === selectedId ? " selected" : ""}>${esc(labels[i.id])}</option>`;
    }).join("");
    return { html, labels };
  } catch (e) {
    return { html: '<option value="">unavailable</option>', labels: {} };
  }
}

async function _fundamentalsInstrumentOptions(selectedSymbol) {
  try {
    const env = await fetchJSON("/instruments");
    const list = ((env.data || {}).instruments || []).filter((i) => i.capabilities && i.capabilities.fundamentals);
    if (!list.length) {
      return { html: '<option value="">— add equities/ETFs in Registry —</option>', labels: {} };
    }
    const labels = {};
    const html = list.map((i) => {
      const sym = (i.symbol || "").toUpperCase();
      labels[sym] = i.label || sym;
      return `<option value="${esc(sym)}"${sym === selectedSymbol ? " selected" : ""}>${esc(labels[sym])} (${esc(i.asset)})</option>`;
    }).join("");
    return { html, labels };
  } catch (e) {
    return { html: '<option value="">unavailable</option>', labels: {} };
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

let _registryCache = null;
let _registryCacheAt = 0;

async function _loadRegistry() {
  if (_registryCache && Date.now() - _registryCacheAt < 30000) return _registryCache;
  const env = await fetchJSON("/instruments");
  _registryCache = (env.data || {}).instruments || [];
  _registryCacheAt = Date.now();
  return _registryCache;
}

function _acTokenAt(value, pos) {
  const before = value.slice(0, pos ?? value.length);
  const start = before.lastIndexOf(",") + 1;
  return {
    prefix: value.slice(0, start),
    token: before.slice(start).trimStart(),
    end: pos ?? value.length,
  };
}

function _acInsert(input, pick, multiComma) {
  if (!multiComma) {
    input.value = pick;
    return;
  }
  const { prefix, token, end } = _acTokenAt(input.value, input.selectionStart);
  const lead = prefix && !prefix.endsWith(",") && !prefix.endsWith(", ") ? prefix + ", " : prefix;
  const rest = input.value.slice(end);
  const tail = rest.startsWith(",") ? rest : (rest ? ", " + rest.trim() : "");
  input.value = lead + pick + tail;
}

async function _acSearchHits(assets, query) {
  const q = (query || "").trim();
  if (!q) return [];
  const reg = await _loadRegistry();
  const assetSet = new Set(assets);
  const seen = new Set();
  const out = [];
  for (const i of reg) {
    if (!assetSet.has(i.asset)) continue;
    const sym = (i.symbol || "").toUpperCase();
    const blob = `${sym} ${(i.label || "")} ${i.id}`.toUpperCase();
    if (!blob.includes(q.toUpperCase()) && !sym.startsWith(q.toUpperCase())) continue;
    seen.add(sym);
    out.push({
      symbol: i.symbol,
      name: i.label || i.symbol,
      pick: i.symbol,
      tracked: true,
      badge: "tracked",
    });
  }
  let searchNote = "";
  for (const asset of assets) {
    try {
      const r = await fetchJSON(
        "/instruments/search?asset=" + encodeURIComponent(asset) + "&query=" + encodeURIComponent(q) + "&limit=20"
      );
      if (r.ok === false && r.error) searchNote = r.error;
      if ((r.data || {}).note) searchNote = r.data.note;
      for (const h of (r.data || {}).results || []) {
        const sym = (h.symbol || "").toUpperCase();
        if (seen.has(sym)) continue;
        seen.add(sym);
        out.push({
          symbol: h.symbol,
          name: h.name || "",
          pick: h.symbol,
          tracked: false,
          badge: "catalog",
        });
      }
    } catch (e) {
      searchNote = e.message || "search failed";
    }
  }
  if (!out.length && searchNote) {
    return [{ _error: searchNote }];
  }
  return out.slice(0, 25);
}

/** Type-ahead symbol picker — registry + catalog, shared across Registry and Brain fields. */
function _bindInstrumentAutocomplete(opts) {
  const input = typeof opts.input === "string" ? $(opts.input) : opts.input;
  const list = typeof opts.list === "string" ? $(opts.list) : opts.list;
  if (!input || !list) return;

  const getAssets = () => {
    if (opts.assets) return opts.assets;
    const a = typeof opts.asset === "function" ? opts.asset() : opts.asset;
    return a ? [a] : ["equity"];
  };
  const multiComma = !!opts.multiComma;
  const requireTracked = !!opts.requireTracked;

  let hits = [];
  let activeIdx = -1;
  let timer = null;

  const hide = () => { list.classList.add("hidden"); activeIdx = -1; };
  const show = () => list.classList.remove("hidden");

  const applyPick = (h) => {
    if (!h) return;
    if (requireTracked && !h.tracked) {
      if (opts.onUntracked) opts.onUntracked(h);
      return;
    }
    _acInsert(input, h.pick, multiComma);
    hide();
    if (opts.onPick) opts.onPick(h, input);
  };

  const render = () => {
    if (!hits.length) {
      list.innerHTML = '<div class="ac-empty">no matches — check spelling or add in Registry</div>';
      show();
      return;
    }
    if (hits[0]._error) {
      list.innerHTML = `<div class="ac-empty err">${esc(hits[0]._error)}</div>`;
      show();
      return;
    }
    list.innerHTML = hits.map((h, i) =>
      `<button type="button" class="ac-item${i === activeIdx ? " active" : ""}" data-idx="${i}">
        <span class="sym">${esc(h.symbol)}</span><span class="nm">${esc(h.name || "")}</span>
        <span class="dim" style="margin-left:6px;font-size:11px">${esc(h.badge || "")}</span>
      </button>`).join("");
    list.querySelectorAll(".ac-item").forEach((btn) => {
      btn.addEventListener("mousedown", (ev) => {
        ev.preventDefault();
        applyPick(hits[Number(btn.dataset.idx)]);
      });
    });
    show();
  };

  const queryToken = () => (multiComma ? _acTokenAt(input.value, input.selectionStart).token : input.value.trim());

  const fetchHits = async () => {
    const q = queryToken();
    if (q.length < 1) { hits = []; hide(); return; }
    try {
      hits = await _acSearchHits(getAssets(), q);
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
  input.addEventListener("focus", () => { if (queryToken()) fetchHits(); });
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
      if (hits.length && activeIdx >= 0) {
        ev.preventDefault();
        applyPick(hits[activeIdx]);
      } else if (opts.onEnter) {
        ev.preventDefault();
        opts.onEnter(input);
      }
    } else if (ev.key === "Escape") hide();
  });
  if (opts.onAssetChange) {
    const prev = opts.onAssetChange;
    opts.onAssetChange = () => { prev(); hits = []; hide(); if (queryToken()) fetchHits(); };
  }
}

function _bindSymbolAutocomplete(addFn) {
  const input = $("#c-symbol");
  const list = $("#c-suggest");
  const assetSel = $("#c-asset");
  if (!input || !list || !assetSel) return;
  _bindInstrumentAutocomplete({
    input,
    list,
    asset: () => assetSel.value,
    onPick: (h) => addFn(assetSel.value, h.symbol),
    onEnter: (inp) => addFn(assetSel.value, inp.value.trim()),
  });
  assetSel.addEventListener("change", () => {
    input.placeholder = ASSET_PLACEHOLDER[assetSel.value] || "type to search…";
  });
  input.placeholder = ASSET_PLACEHOLDER[assetSel.value] || "type to search…";
}

function _acFieldHtml(inputId, listId, placeholder) {
  return `<div class="ac-wrap">
    <input id="${inputId}" class="inp" autocomplete="off" spellcheck="false" placeholder="${esc(placeholder)}" />
    <div id="${listId}" class="ac-list hidden"></div>
  </div>`;
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
    try { await apiSend("/instruments", "POST", { asset, symbol: sym }); _registryCache = null; await reload(); }
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

async function loadCotOne(id, label) {
  const body = document.getElementById("cot-body");
  if (!body) return;
  body.innerHTML = `<div class="loading">Loading ${esc(label || id)}…</div>`;
  try {
    const env = await fetchJSON("/cot/positioning?instrument=" + encodeURIComponent(id));
    if (env.freshness) $("#freshness").textContent = env.freshness;
    if (env.ok === false) {
      body.innerHTML = _renderCotCard({ ok: false, name: label || id, error: env.error });
      return;
    }
    body.innerHTML = `<div class="grid">${_renderCotCard({ ok: true, name: label || id, ...(env.data || {}) })}</div>`;
  } catch (e) {
    body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`;
  }
}

async function loadCot() {
  const sec = $("#view-cot");
  const { html, labels } = await _cotInstrumentOptions("");
  sec.innerHTML = panel("COT positioning — weekly CFTC report",
    `<div class="sub mb-sm">Pick a futures contract from your registry. Most liquid CME/CBOT/COMEX/NYMEX roots (GC, CL, NG, ES, NQ, ZN, 6E, 6J…) resolve their CFTC code automatically.</div>
     <select id="cot-pick" class="btn">${html}</select>
     <div id="cot-body" class="mt-md"></div>`);
  const pick = document.getElementById("cot-pick");
  if (pick && pick.value) {
    const load = () => loadCotOne(pick.value, labels[pick.value] || pick.value);
    pick.addEventListener("change", load);
    load();
  } else if (document.getElementById("cot-body")) {
    document.getElementById("cot-body").innerHTML =
      '<div class="dim">Add futures in the Registry tab — COT is available for contracts with CFTC metadata (e.g. GC, NQ, 6E).</div>';
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
  decision: "Decision Brief",
  "news-pulse": "News Pulse",
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
  "crypto-brain": "Crypto Brain",
  "forex-brain": "Forex Brain",
  hitlist: "Daily Hitlist",
  "trade-setup": "Trade Setup",
  "market-setup": "Crypto/FX Setup",
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

function renderMarketBrain(env) {
  const d = env.data || {};
  if (d.error && !d.conviction) {
    return `<div class="err">${esc(d.error)}</div>`;
  }
  const conv = d.conviction;
  const c = d.components || {};
  const p = d.price || {};
  const v = d.volatility || {};
  const vr = v.regime || {};
  const flags = (d.flags || []).map((x) => `<span class="pill amber" style="margin:2px">${esc(x)}</span>`).join(" ");
  const hero = conv ? panel("Decision", `
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span class="pill ${_CONV_CLASS[conv] || ""}" style="font-size:13px">${esc(String(conv).toUpperCase())}</span>
      <span style="font-size:14px"><b>${esc(d.summary || "")}</b></span></div>
    <div class="sub" style="margin-top:8px">score ${num(d.score, 0)}
      (momentum ${num(c.momentum, 0)} · macro ${num(c.macro, 0)} · vol ${num(c.vol, 0)} · usd ${num(c.usd, 0)})
      · regime ${esc(c.macro_regime || "—")}</div>
    ${flags ? `<div style="margin-top:6px">${flags}</div>` : ""}`) : "";
  const pricePanel = panel("Price & momentum", `<div class="tiles">
    ${_fundTile("Last", num(p.last, 4))}
    ${_fundTile("1w", pct(p.change_1w_pct))}
    ${_fundTile("1m", pct(p.change_1m_pct))}
    ${_fundTile("Realized vol", p.vol_annualized != null ? num(p.vol_annualized * 100, 1) + "%" : "—", p.regime || "")}
  </div>`);
  const volPanel = v.ok ? panel("Volatility", `<div class="tiles">
    ${_fundTile("Regime", _volPill(vr.regime), vr.percentile != null ? num(vr.percentile, 0) + "th pct ~3y" : "")}
    ${_fundTile("Ann. vol", num((v.current_vol_annualized || 0) * 100, 1) + "%")}
    ${_fundTile("EWMA forecast", num(((v.forecast || {}).ewma || 0) * 100, 1) + "%", num((v.forecast || {}).horizon_days, 0) + "d")}
  </div><div class="sub" style="margin-top:6px">${esc(v.read || "")}</div>`) : "";
  return hero + `<div class="grid" style="grid-template-columns:1fr">${pricePanel}${volPanel}</div>`
    + `<div class="exec-help dim" style="margin-top:8px">${esc(d.disclaimer || "")}</div>`;
}

async function _assetInstrumentOptions(asset, selectedId) {
  try {
    const env = await fetchJSON("/instruments");
    const list = ((env.data || {}).instruments || []).filter((i) => i.asset === asset);
    if (!list.length) {
      return { html: `<option value="">— add ${asset} symbols in Registry —</option>`, labels: {} };
    }
    const labels = {};
    const html = list.map((i) => {
      labels[i.id] = i.label || i.symbol;
      return `<option value="${esc(i.id)}"${i.id === selectedId ? " selected" : ""}>${esc(labels[i.id])}</option>`;
    }).join("");
    return { html, labels };
  } catch (e) {
    return { html: '<option value="">unavailable</option>', labels: {} };
  }
}

async function loadMarketBrainOne(prefix, id, label) {
  const body = document.getElementById(`${prefix}-brain-body`);
  if (!body) return;
  body.innerHTML = `<div class="loading">Loading ${esc(label || id)}…</div>`;
  try {
    const env = await fetchJSON(`/brain/${prefix}/` + encodeURIComponent(id));
    if (env.ok === false) { body.innerHTML = `<div class="err">${esc(env.error || "unavailable")}</div>`; return; }
    body.innerHTML = renderMarketBrain(env);
  } catch (e) { body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; }
}

async function loadMarketBrain(asset) {
  const prefix = asset;
  const title = asset === "crypto" ? "Crypto Brain" : "Forex Brain";
  const sec = $(`#view-${prefix}-brain`);
  const { html, labels } = await _assetInstrumentOptions(asset, "");
  sec.innerHTML =
    panel(`${title} screen — rank conviction`, `
      <div class="sub mb-sm">Leave blank to rank every tracked ${asset} symbol in your registry. Type to search tracked symbols (add in Registry first).</div>
      <div class="addbar">
        ${_acFieldHtml(`${prefix}-scr-input`, `${prefix}-scr-suggest`, ASSET_PLACEHOLDER[asset] + " (optional)")}
        <button id="${prefix}-scr-go" class="btn">Screen</button>
      </div>
      <div id="${prefix}-scr-body" style="margin-top:12px"><div class="sub dim">Run a screen to rank ${asset} symbols by conviction.</div></div>`)
    + panel(`${title} — per symbol`, `
      <div class="sub mb-sm">Momentum (1w & 1m) + macro regime + vol + USD backdrop. Research context only.</div>
      <select id="${prefix}-brain-pick" class="btn">${html}</select>
      <div id="${prefix}-brain-body" class="mt-md"></div>`);

  const pick = document.getElementById(`${prefix}-brain-pick`);
  if (pick && pick.value) {
    const load = () => loadMarketBrainOne(prefix, pick.value, labels[pick.value] || pick.value);
    pick.addEventListener("change", load);
    load();
  } else if (document.getElementById(`${prefix}-brain-body`)) {
    document.getElementById(`${prefix}-brain-body`).innerHTML =
      `<div class="dim">Add ${asset} symbols in the Registry tab first.</div>`;
  }

  const scrBody = document.getElementById(`${prefix}-scr-body`);
  const screen = async () => {
    const syms = (document.getElementById(`${prefix}-scr-input`).value || "").trim();
    scrBody.innerHTML = `<div class="loading">Screening…</div>`;
    try {
      const q = syms ? "?symbols=" + encodeURIComponent(syms) : "";
      const env = await fetchJSON(`/brain/${prefix}/screen` + q);
      if (env.ok === false) { scrBody.innerHTML = `<div class="err">${esc(env.error || "unavailable")}</div>`; return; }
      scrBody.innerHTML = renderBrainScreen(env);
    } catch (e) { scrBody.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; }
  };
  document.getElementById(`${prefix}-scr-go`).addEventListener("click", screen);
  document.getElementById(`${prefix}-scr-input`).addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !listVisible(`${prefix}-scr-suggest`)) screen();
  });
  _bindInstrumentAutocomplete({
    input: `#${prefix}-scr-input`,
    list: `#${prefix}-scr-suggest`,
    asset,
    multiComma: true,
    requireTracked: true,
    onUntracked: (h) => {
      scrBody.innerHTML = `<div class="err">Add <b>${esc(h.symbol)}</b> in Registry first, then screen.</div>`;
    },
  });
}

function listVisible(listId) {
  const el = document.getElementById(listId);
  return el && !el.classList.contains("hidden");
}

async function loadCryptoBrain() { return loadMarketBrain("crypto"); }
async function loadForexBrain() { return loadMarketBrain("forex"); }

// --- Signals: Trade Setup + Daily Hitlist (ROADMAP H7) ----------------------
const _BIAS_CLASS = { long: "green", short: "red", neutral: "amber" };

// Signed component tile (trend/momentum/catalyst/smart-money/context): coloured
// by sign so the drivers read at a glance.
function _signedTile(label, val) {
  if (val === null || val === undefined) return _fundTile(label, "—");
  const cls = val > 0 ? "up" : val < 0 ? "down" : "dim";
  const txt = `<span class="${cls}">${val > 0 ? "+" : ""}${val}</span>`;
  return _fundTile(label, txt);
}

function renderTradeSetup(env) {
  const d = env.data || {};
  if (d.enabled === false) return `<div class="err">${esc(d.error || "trade setup unavailable")}</div>`;
  const bias = d.bias || "neutral";
  const c = d.components || {};
  const part = d.participation || {};
  const mom = d.momentum || {};
  const triggers = (d.triggers || []).map((t) => `<li>${esc(t)}</li>`).join("");
  const flags = (d.flags || []).map((x) => `<span class="pill amber" style="margin:2px">${esc(x)}</span>`).join(" ");
  const errs = d.errors ? `<div class="exec-help dim" style="margin-top:8px">degraded axes: ${esc(Object.keys(d.errors).join(", "))}</div>` : "";

  const hero = panel("Setup", `
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span class="pill ${_BIAS_CLASS[bias] || ""}" style="font-size:13px">${esc(bias.toUpperCase())}</span>
      <span style="font-size:14px"><b>${esc(d.symbol)}</b> ${d.price != null ? "$" + num(d.price, 2) : ""}</span>
      <span class="pill">${esc(d.conviction || "—")} conviction</span>
      <span class="pill ${part.in_play ? "green" : ""}">${part.in_play ? "IN PLAY" : "quiet"}</span>
    </div>
    <div class="sub" style="margin-top:8px">${esc(d.read || "")}</div>
    ${flags ? `<div style="margin-top:6px">${flags}</div>` : ""}`);

  const components = panel("Drivers", `<div class="tiles">
    ${_signedTile("Trend", c.trend)}${_signedTile("Momentum", c.momentum)}${_signedTile("Catalyst", c.catalyst)}
    ${_signedTile("Smart money", c.smart_money)}${_signedTile("Context", c.context)}
    ${_fundTile("Score", `<span class="${(d.score || 0) > 0 ? "up" : (d.score || 0) < 0 ? "down" : "dim"}">${d.score > 0 ? "+" : ""}${num(d.score, 0)}</span>`)}</div>`);

  const participation = panel("Participation", `<div class="tiles">
    ${_fundTile("Rel. volume", part.relative_volume != null ? num(part.relative_volume, 2) + "×" : "—", "vs avg")}
    ${_fundTile("RSI(14)", mom.rsi != null ? num(mom.rsi, 0) : "—")}
    ${_fundTile("ADX", mom.adx != null ? num(mom.adx, 0) : "—", mom.trending ? "trending" : "choppy")}
    ${_fundTile("52w range", part.range_position_52w != null ? num(part.range_position_52w * 100, 0) + "%" : "—", "0=low · 100=high")}</div>`);

  const trig = triggers ? panel("Triggers", `<ul class="sub" style="margin:0;padding-left:18px">${triggers}</ul>`) : "";
  const ctx = d.context ? panel("Longer-horizon context (Stock Brain)", `<div class="sub">${esc(d.context)}</div>`) : "";

  return hero + `<div class="grid" style="grid-template-columns:1fr">${components}${participation}${trig}${ctx}</div>`
    + `<div class="exec-help dim" style="margin-top:8px">${esc(d.disclaimer || "")}</div>` + errs;
}

async function loadTradeSetup() {
  const sec = $("#view-trade-setup");
  sec.innerHTML = panel("Trade Setup — daily directional bias", `
    <div class="sub mb-sm">Per-ticker bias fusing trend (50/200 MA), momentum (RSI/ADX), catalysts (analyst/news/earnings), and smart money (insider + congress). Research context, never an auto-executed signal.</div>
    <div class="addbar">
      ${_acFieldHtml("ts-input", "ts-suggest", "type AAPL, NVDA, TSLA…")}
      <button id="ts-go" class="btn">Analyze</button>
    </div>
    <div id="ts-body" style="margin-top:12px"></div>`);
  $("#ts-input").value = "AAPL";
  const body = $("#ts-body");
  const go = async () => {
    const t = ($("#ts-input").value || "").trim().toUpperCase();
    if (!t) return;
    body.innerHTML = `<div class="loading">Analyzing ${esc(t)}…</div>`;
    try {
      const env = await fetchJSON("/signals/setup/" + encodeURIComponent(t));
      if (env.ok === false) { body.innerHTML = `<div class="err">${esc(env.error || "unavailable")}</div>`; return; }
      body.innerHTML = renderTradeSetup(env);
    } catch (e) { body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; }
  };
  $("#ts-go").addEventListener("click", go);
  $("#ts-input").addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !listVisible("ts-suggest")) go(); });
  _bindInstrumentAutocomplete({
    input: "#ts-input",
    list: "#ts-suggest",
    assets: ["equity", "etf"],
    onPick: (h) => { $("#ts-input").value = h.symbol; go(); },
    onEnter: () => go(),
  });
  go();
}

function renderHitlist(env) {
  const d = env.data || {};
  if (d.enabled === false) return `<div class="err">${esc(d.error || "hitlist unavailable")}</div>`;
  if (d.error) return `<div class="err">${esc(d.error)}</div>`;
  const rows = d.hitlist || [];
  if (!rows.length) return `<div class="sub dim">No names cleared the scan today.</div>`;
  const lf = d.liquidity_floor || {};
  const head = `<div class="sub" style="margin-bottom:6px">
    as of ${esc(d.as_of || "—")} · scanned ${num(d.scanned, 0)} · <span class="up">${num(d.long_count, 0)} long</span> / <span class="down">${num(d.short_count, 0)} short</span>
    · floor ≥$${num(lf.min_price, 0)} &amp; ≥${_fmtBig(lf.min_dollar_volume)} $-vol</div>`;
  const body = rows.map((r) => {
    const bias = r.bias || "neutral";
    const trigs = (r.triggers || []).slice(0, 3).join("; ");
    return `<tr>
      <td><b>${esc(r.ticker)}</b></td>
      <td>${r.price != null ? "$" + num(r.price, 2) : "—"}</td>
      <td>${pct(r.change_1d_pct)}</td>
      <td><span class="pill ${_BIAS_CLASS[bias] || ""}">${esc(String(bias).toUpperCase())}</span></td>
      <td style="text-align:right">${r.score == null ? "—" : (r.score > 0 ? "+" : "") + num(r.score, 0)}</td>
      <td style="text-align:center">${r.confluence ? "✓" : ""}</td>
      <td style="text-align:center">${r.event_risk ? '<span class="pill amber">⚠</span>' : ""}</td>
      <td class="sub">${esc(trigs)}</td>
    </tr>`;
  }).join("");
  return head + `<table style="margin-top:6px"><thead><tr>
    <th>Ticker</th><th>Price</th><th>1d</th><th>Bias</th><th style="text-align:right">Score</th>
    <th style="text-align:center">Confl.</th><th style="text-align:center">Event</th><th>Triggers</th></tr></thead><tbody>${body}</tbody></table>`;
}

async function loadHitlist() {
  const sec = $("#view-hitlist");
  sec.innerHTML = panel("Daily Hitlist — market-wide morning scan", `
    <div class="sub mb-sm">Today's biggest movers (liquid names only), enriched with catalyst + smart-money signals and ranked by confluence → conviction → intensity. Research context, never a trade trigger.</div>
    <div class="addbar">
      <label class="sub">Min move %</label><input id="hl-move" class="inp" style="max-width:80px" value="2" />
      <label class="sub">Top</label><input id="hl-limit" class="inp" style="max-width:80px" value="15" />
      <button id="hl-go" class="btn">Scan</button>
    </div>
    <div id="hl-body" style="margin-top:12px"></div>`);
  const body = $("#hl-body");
  const go = async () => {
    const move = ($("#hl-move").value || "2").trim();
    const limit = ($("#hl-limit").value || "15").trim();
    body.innerHTML = `<div class="loading">Scanning the market…</div>`;
    try {
      const env = await fetchJSON(`/signals/hitlist?limit=${encodeURIComponent(limit)}&min_move_pct=${encodeURIComponent(move)}`);
      if (env.ok === false) { body.innerHTML = `<div class="err">${esc(env.error || "unavailable")}</div>`; return; }
      body.innerHTML = renderHitlist(env);
    } catch (e) { body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; }
  };
  $("#hl-go").addEventListener("click", go);
  $("#hl-move").addEventListener("keydown", (ev) => { if (ev.key === "Enter") go(); });
  $("#hl-limit").addEventListener("keydown", (ev) => { if (ev.key === "Enter") go(); });
  go();
}

// --- Crypto/FX Market Setup (technical analog of stock Trade Setup) ----------
function renderMarketSetup(env) {
  const d = env.data || {};
  if (d.enabled === false) return `<div class="err">${esc(d.error || "market setup unavailable")}</div>`;
  const bias = d.bias || "neutral";
  const c = d.components || {};
  const part = d.participation || {};
  const mom = d.momentum || {};
  const flags = (d.flags || []).map((x) => `<span class="pill amber" style="margin:2px">${esc(x)}</span>`).join(" ");
  const errs = d.errors ? `<div class="exec-help dim" style="margin-top:8px">degraded axes: ${esc(Object.keys(d.errors).join(", "))}</div>` : "";
  const hero = panel("Setup", `
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span class="pill ${_BIAS_CLASS[bias] || ""}" style="font-size:13px">${esc(bias.toUpperCase())}</span>
      <span style="font-size:14px"><b>${esc(d.symbol)}</b> ${d.price != null ? num(d.price, d.price < 10 ? 4 : 2) : ""}</span>
      <span class="pill">${esc(d.conviction || "—")} conviction</span>
      <span class="pill ${part.in_play ? "green" : ""}">${part.in_play ? "IN PLAY" : "quiet"}</span>
      <span class="dim">${esc(d.asset || "")}</span>
    </div>
    <div class="sub" style="margin-top:8px">${esc(d.read || "")}</div>
    ${flags ? `<div style="margin-top:6px">${flags}</div>` : ""}`);
  const drivers = panel("Drivers", `<div class="tiles">
    ${_signedTile("Trend", c.trend)}${_signedTile("Momentum", c.momentum)}
    ${_fundTile("Score", `<span class="${(d.score || 0) > 0 ? "up" : (d.score || 0) < 0 ? "down" : "dim"}">${d.score > 0 ? "+" : ""}${num(d.score, 0)}</span>`)}</div>`);
  const partPanel = panel("Participation", `<div class="tiles">
    ${_fundTile("Rel. volume", part.relative_volume != null ? num(part.relative_volume, 2) + "×" : "—", "vs avg")}
    ${_fundTile("RSI(14)", mom.rsi != null ? num(mom.rsi, 0) : "—")}
    ${_fundTile("ADX", mom.adx != null ? num(mom.adx, 0) : "—", mom.trending ? "trending" : "choppy")}
    ${_fundTile("52w range", part.range_position_52w != null ? num(part.range_position_52w * 100, 0) + "%" : "—", "0=low · 100=high")}</div>`);
  return hero + `<div class="grid" style="grid-template-columns:1fr">${drivers}${partPanel}</div>`
    + `<div class="exec-help dim" style="margin-top:8px">${esc(d.disclaimer || "")} · No catalyst/insider axes — those don't exist for crypto/FX.</div>` + errs;
}

function renderMarketScreen(env) {
  const d = env.data || {};
  if (d.enabled === false) return `<div class="err">${esc(d.error || "unavailable")}</div>`;
  const rows = d.ranked || [];
  if (!rows.length) return `<div class="sub dim">No setups returned.</div>`;
  const head = `<div class="sub" style="margin-bottom:6px">${rows.length} ranked · ${esc(d.universe || "")} universe · ${esc(d.asset || "")}</div>`;
  const body = rows.map((r) => {
    const bias = r.bias || "neutral";
    const c = r.components || {};
    const detail = r.error ? `<span class="dim">${esc(r.error)}</span>`
      : `<span class="dim">trend ${num(c.trend, 0)} · mom ${num(c.momentum, 0)}${r.in_play ? " · in play" : ""}</span>`;
    return `<tr>
      <td><b>${esc(r.symbol)}</b></td>
      <td><span class="pill ${_BIAS_CLASS[bias] || ""}">${esc(String(bias).toUpperCase())}</span></td>
      <td style="text-align:right">${r.score == null ? "—" : (r.score > 0 ? "+" : "") + num(r.score, 0)}</td>
      <td class="sub">${esc(r.read || "")} ${detail}</td>
    </tr>`;
  }).join("");
  return head + `<table style="margin-top:6px"><thead><tr><th>Symbol</th><th>Bias</th><th style="text-align:right">Score</th><th>Read</th></tr></thead><tbody>${body}</tbody></table>`;
}

async function loadMarketSetup() {
  const sec = $("#view-market-setup");
  sec.innerHTML = panel("Crypto/FX Setup — technical day-trade bias", `
    <div class="sub mb-sm">The crypto/FX analog of Trade Setup: trend (50/200 MA) + momentum (RSI/ADX) + in-play participation. No catalyst/smart-money axes (don't exist for these assets). Research context, never a trade trigger.</div>
    <div class="addbar">
      <select id="ms-asset" class="btn"><option value="crypto">Crypto</option><option value="forex">Forex</option></select>
      ${_acFieldHtml("ms-input", "ms-suggest", "type BTC, ETH, EUR…")}
      <button id="ms-go" class="btn">Analyze</button>
      <button id="ms-screen" class="btn">Screen majors</button>
    </div>
    <div id="ms-body" style="margin-top:12px"></div>`);
  $("#ms-input").value = "BTC-USD";
  const body = $("#ms-body");
  const asset = () => $("#ms-asset").value || "crypto";
  const one = async () => {
    const s = ($("#ms-input").value || "").trim();
    if (!s) return;
    body.innerHTML = `<div class="loading">Analyzing ${esc(s.toUpperCase())}…</div>`;
    try {
      const env = await fetchJSON(`/signals/market/${encodeURIComponent(asset())}/` + encodeURIComponent(s));
      if (env.ok === false) { body.innerHTML = `<div class="err">${esc(env.error || "unavailable")}</div>`; return; }
      body.innerHTML = renderMarketSetup(env);
    } catch (e) { body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; }
  };
  const screen = async () => {
    body.innerHTML = `<div class="loading">Screening ${esc(asset())} majors… (first run can be slow)</div>`;
    try {
      const env = await fetchJSON(`/signals/market/${encodeURIComponent(asset())}/screen`);
      if (env.ok === false) { body.innerHTML = `<div class="err">${esc(env.error || "unavailable")}</div>`; return; }
      body.innerHTML = renderMarketScreen(env);
    } catch (e) { body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; }
  };
  $("#ms-asset").addEventListener("change", () => {
    $("#ms-input").value = asset() === "crypto" ? "BTC-USD" : "EURUSD";
  });
  $("#ms-go").addEventListener("click", one);
  $("#ms-screen").addEventListener("click", screen);
  $("#ms-input").addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !listVisible("ms-suggest")) one(); });
  _bindInstrumentAutocomplete({
    input: "#ms-input",
    list: "#ms-suggest",
    asset: asset,  // follows the Crypto/Forex toggle
    onPick: (h) => { $("#ms-input").value = h.symbol; one(); },
    onEnter: () => one(),
  });
  one();
}

// --- Decision Brief: the one-call composed package Alice receives -----------
function _briefConviction(s) {
  if (!s) return "";
  const conv = s.conviction || "—";
  return panel("Conviction", `
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span class="pill ${_CONV_CLASS[conv] || ""}" style="font-size:13px">${esc(String(conv).toUpperCase())}</span>
      ${s.score != null ? `<span class="dim">score ${s.score > 0 ? "+" : ""}${num(s.score, 0)}</span>` : ""}
    </div>
    <div class="sub" style="margin-top:8px">${esc(s.summary || "")}</div>`);
}
function _briefSetup(s) {
  if (!s) return "";
  const bias = s.bias || "neutral";
  const trigs = (s.triggers || []).slice(0, 4).map((t) => `<li>${esc(t)}</li>`).join("");
  return panel("Setup", `
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span class="pill ${_BIAS_CLASS[bias] || ""}" style="font-size:13px">${esc(String(bias).toUpperCase())}</span>
      ${s.score != null ? `<span class="dim">score ${s.score > 0 ? "+" : ""}${num(s.score, 0)}</span>` : ""}
      ${s.conviction ? `<span class="pill">${esc(s.conviction)} conviction</span>` : ""}
      <span class="pill ${s.in_play ? "green" : ""}">${s.in_play ? "IN PLAY" : "quiet"}</span>
    </div>
    ${trigs ? `<ul class="sub" style="margin:8px 0 0;padding-left:18px">${trigs}</ul>` : ""}`);
}
function _briefPositioning(s) {
  if (!s) return "";
  const r1 = s.range_1y && typeof s.range_1y === "object" ? s.range_1y.percentile : s.range_1y;
  return panel("COT positioning", `<div class="tiles">
    ${_fundTile("Non-comm net", num(s.non_commercial_net, 0), "large specs")}
    ${_fundTile("Commercial net", num(s.commercial_net, 0), "hedgers")}
    ${_fundTile("1w change", s.net_change_1w != null ? (s.net_change_1w > 0 ? "+" : "") + num(s.net_change_1w, 0) : "—")}
    ${_fundTile("Specs vs 1y", r1 != null ? num(r1, 0) + "%" : "—", "range %ile")}
    ${_fundTile("Trend", esc(s.trend || "—"))}</div>
    <div class="sub" style="margin-top:6px">report ${esc(s.report_date || "—")}</div>`);
}
function _briefVol(s) {
  if (!s || s.ok === false) return "";
  const vr = s.regime || {};
  return panel("Volatility", `<div class="tiles">
    ${_fundTile("Regime", esc((vr.regime || s.regime_label || "—")), vr.percentile != null ? num(vr.percentile, 0) + "th pct ~3y" : "")}
    ${_fundTile("Ann. vol", s.current_vol_annualized != null ? num(s.current_vol_annualized * 100, 1) + "%" : "—")}
    ${_fundTile("EWMA fcst", (s.forecast || {}).ewma != null ? num(s.forecast.ewma * 100, 1) + "%" : "—", num((s.forecast || {}).horizon_days, 0) + "d")}</div>`);
}
function _briefNews(items) {
  if (!items || !items.length) return "";
  const rows = items.map((h) => `<li><a href="${esc(h.url || "#")}" target="_blank" rel="noopener">${esc(h.title || "")}</a> <span class="dim">${esc(h.source || "")} · ${esc(String(h.date || "").slice(0, 10))}</span></li>`).join("");
  return panel("News", `<ul class="sub" style="margin:0;padding-left:18px">${rows}</ul>`);
}

function _briefPulse(p) {
  if (!p || !p.direction) return "";
  const dir = String(p.direction).toLowerCase();
  const cats = (p.catalysts || []).slice(0, 4).map((x) => `<span class="pill" style="margin:2px">${esc(x)}</span>`).join(" ");
  return panel("24h News Pulse", `
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
      <span class="pill ${_DIR_CLASS[dir] || ""}">${esc(dir.toUpperCase())}</span>
      <span class="pill">${esc(p.confidence || "—")}</span>
      <span class="dim">${p.engine === "llm" ? "analyst" : "rule-based"}</span>
    </div>
    <div class="sub" style="margin-top:6px">${esc(p.summary || "")}</div>${cats ? `<div style="margin-top:4px">${cats}</div>` : ""}`);
}

function renderDecision(env) {
  const d = env.data || {};
  const s = d.sections || {};
  const regime = (d.macro || {}).regime;
  const cf = d.conflict || {};
  const cfCls = { high: "red", medium: "amber", low: "" }[cf.caution] || "";
  const conflictBanner = (cf.class && cf.class !== "none" && cf.class !== "aligned")
    ? panel("⚠ Conflict", `<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        <span class="pill ${cfCls}">${esc(String(cf.class).replace(/_/g, " ").toUpperCase())}</span>
        <span class="pill ${cfCls}">${esc(cf.caution || "")} caution</span></div>
        <div class="sub" style="margin-top:6px">${esc(cf.note || "")}</div>`, cf.caution === "high")
    : "";
  const hero = panel("Decision Brief", `
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span style="font-size:15px"><b>${esc(d.symbol)}</b></span>
      <span class="pill">${esc(d.asset || "")}</span>
      ${regime ? `<span class="pill ${regime.startsWith("risk-on") ? "green" : regime.startsWith("risk-off") ? "red" : "amber"}">macro ${esc(regime)}</span>` : ""}
      ${d.in_registry ? '<span class="dim">tracked</span>' : '<span class="dim">not in registry</span>'}
    </div>
    <div style="font-size:14px;margin-top:8px"><b>${esc(d.synthesis || "")}</b></div>`);
  const briefPanel = s.brief ? panel("What's moving it", `<div class="sub">${esc(s.brief.read || s.brief.summary || JSON.stringify(s.brief).slice(0, 400))}</div>`) : "";
  const body = [
    conflictBanner,
    _briefConviction(s.conviction),
    _briefSetup(s.setup),
    _briefPulse(s.news_pulse),
    briefPanel,
    _briefPositioning(s.positioning),
    _briefVol(s.volatility),
    _briefNews(s.news),
  ].filter(Boolean).join("");
  const errs = d.errors ? `<div class="exec-help dim" style="margin-top:8px">unavailable sections: ${esc(Object.keys(d.errors).join(", "))}</div>` : "";
  return hero + `<div class="grid" style="grid-template-columns:1fr">${body}</div>`
    + `<div class="exec-help dim" style="margin-top:8px">${esc(d.disclaimer || "")}</div>` + errs;
}

async function loadDecision() {
  const sec = $("#view-decision");
  sec.innerHTML = panel("Decision Brief — the full package Alice receives", `
    <div class="sub mb-sm">One call composes everything for a symbol: conviction, setup, COT, vol, news, framed by the macro regime. Routed by asset (stocks, crypto, FX, futures). Research context, never a trade trigger.</div>
    <div class="addbar">
      ${_acFieldHtml("dec-input", "dec-suggest", "type AAPL, BTC-USD, GC=F…")}
      <button id="dec-go" class="btn">Brief</button>
    </div>
    <div id="dec-body" style="margin-top:12px"></div>`);
  $("#dec-input").value = "AAPL";
  const body = $("#dec-body");
  const go = async () => {
    const t = ($("#dec-input").value || "").trim();
    if (!t) return;
    body.innerHTML = `<div class="loading">Composing brief for ${esc(t.toUpperCase())}…</div>`;
    try {
      const env = await fetchJSON("/analysis/decision/" + encodeURIComponent(t));
      if (env.ok === false) { body.innerHTML = `<div class="err">${esc(env.error || "unavailable")}</div>`; return; }
      body.innerHTML = renderDecision(env);
    } catch (e) { body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; }
  };
  $("#dec-go").addEventListener("click", go);
  $("#dec-input").addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !listVisible("dec-suggest")) go(); });
  _bindInstrumentAutocomplete({
    input: "#dec-input",
    list: "#dec-suggest",
    assets: ["equity", "etf", "crypto", "forex", "futures"],
    onPick: (h) => { $("#dec-input").value = h.symbol; go(); },
    onEnter: () => go(),
  });
  go();
}

// --- News Pulse: 24h news-driven directional read --------------------------
const _DIR_CLASS = { up: "green", down: "red", neutral: "amber" };

function renderNewsPulse(env) {
  const d = env.data || {};
  const dir = (d.direction || "neutral").toLowerCase();
  const s = d.news_sentiment || {};
  const cats = (d.catalysts || []).map((x) => `<li>${esc(x)}</li>`).join("");
  const cavs = (d.caveats || []).map((x) => `<li>${esc(x)}</li>`).join("");
  const heads = (d.headlines || []).slice(0, 8).map((h) =>
    `<li><a href="${esc(h.url || "#")}" target="_blank" rel="noopener">${esc(h.title || "")}</a> <span class="dim">${esc(h.source || "")} · ${esc(String(h.date || "").slice(0, 10))}</span></li>`).join("");
  const engineBadge = d.engine === "llm"
    ? '<span class="pill green">analyst (Claude)</span>'
    : '<span class="pill">rule-based</span>';

  const hero = panel("24h Pulse", `
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <span class="pill ${_DIR_CLASS[dir] || ""}" style="font-size:14px">${esc(dir.toUpperCase())}</span>
      <span class="pill">${esc(d.confidence || "—")} confidence</span>
      ${engineBadge}
      <span class="dim">${esc(d.symbol)} · ${esc(d.asset || "")} · next ~24h</span>
    </div>
    <div style="font-size:14px;margin-top:10px"><b>${esc(d.summary || "")}</b></div>`);

  const drivers = panel("News sentiment", `<div class="tiles">
    ${_fundTile("Lean", `<span class="${_DIR_CLASS[(s.lean || "neutral")] === "green" ? "up" : _DIR_CLASS[s.lean] === "red" ? "down" : "dim"}">${esc((s.lean || "—").toUpperCase())}</span>`)}
    ${_fundTile("Positive", num(s.positive, 0))}${_fundTile("Negative", num(s.negative, 0))}
    ${_fundTile("Net", `<span class="${(s.score || 0) > 0 ? "up" : (s.score || 0) < 0 ? "down" : "dim"}">${s.score > 0 ? "+" : ""}${num(s.score, 0)}</span>`)}
    ${_fundTile("Headlines 24h", num(s.headline_count, 0))}
    ${_fundTile("Technical", esc(d.technical_bias || "—"))}${_fundTile("Macro", esc(d.macro_regime || "—"))}</div>`);

  const catPanel = cats ? panel("Catalysts (24h)", `<ul class="sub" style="margin:0;padding-left:18px">${cats}</ul>`) : "";
  const cavPanel = cavs ? panel("What could flip it", `<ul class="sub" style="margin:0;padding-left:18px">${cavs}</ul>`) : "";
  const headPanel = heads ? panel("Headlines", `<ul class="sub" style="margin:0;padding-left:18px">${heads}</ul>`) : "";
  const base = (d.baseline && d.engine === "llm")
    ? `<div class="exec-help dim" style="margin-top:8px">rule-based baseline: ${esc(d.baseline.direction)} (${esc(d.baseline.confidence)})</div>` : "";
  const note = d.engine !== "llm"
    ? `<div class="exec-help dim" style="margin-top:8px">Set ANTHROPIC_API_KEY to upgrade this to a reasoned analyst summary (catalysts + caveats).</div>` : "";
  const errs = d.errors ? `<div class="exec-help dim" style="margin-top:6px">degraded: ${esc(Object.keys(d.errors).join(", "))}</div>` : "";

  return hero + `<div class="grid" style="grid-template-columns:1fr">${drivers}${catPanel}${cavPanel}${headPanel}</div>`
    + `<div class="exec-help dim" style="margin-top:8px">${esc(d.disclaimer || "")}</div>` + base + note + errs;
}

async function loadNewsPulse() {
  const sec = $("#view-news-pulse");
  sec.innerHTML = panel("News Pulse — 24h directional read", `
    <div class="sub mb-sm">Monitors the day's headlines for a symbol and gives a brief summary + which way price may lean for the current trading day, fusing news sentiment + technicals + macro. Analyst summary when an Anthropic key is set, else rule-based. Research, not a forecast.</div>
    <div class="addbar">
      ${_acFieldHtml("np-input", "np-suggest", "type AAPL, BTC-USD, GC=F…")}
      <button id="np-go" class="btn">Pulse</button>
    </div>
    <div id="np-body" style="margin-top:12px"></div>`);
  $("#np-input").value = "AAPL";
  const body = $("#np-body");
  const go = async () => {
    const t = ($("#np-input").value || "").trim();
    if (!t) return;
    body.innerHTML = `<div class="loading">Reading the tape for ${esc(t.toUpperCase())}…</div>`;
    try {
      const env = await fetchJSON("/news/pulse/" + encodeURIComponent(t));
      if (env.ok === false) { body.innerHTML = `<div class="err">${esc(env.error || "unavailable")}</div>`; return; }
      body.innerHTML = renderNewsPulse(env);
    } catch (e) { body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; }
  };
  $("#np-go").addEventListener("click", go);
  $("#np-input").addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !listVisible("np-suggest")) go(); });
  _bindInstrumentAutocomplete({
    input: "#np-input",
    list: "#np-suggest",
    assets: ["equity", "etf", "crypto", "forex", "futures"],
    onPick: (h) => { $("#np-input").value = h.symbol; go(); },
    onEnter: () => go(),
  });
  go();
}

async function loadFundamentalsOne(symbol, label) {
  const body = $("#fund-body");
  if (!body) return;
  const t = (symbol || "").trim().toUpperCase();
  if (!t) return;
  body.innerHTML = `<div class="loading">Loading ${esc(label || t)}…</div>`;
  try {
    const env = await fetchJSON("/brain/" + encodeURIComponent(t));
    if (env.ok === false) { body.innerHTML = `<div class="err">${esc(env.error || "unavailable")}</div>`; return; }
    body.innerHTML = renderFundamentals(env);
  } catch (e) { body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`; }
}

async function loadFundamentals() {
  const sec = $("#view-fundamentals");
  const { html, labels } = await _fundamentalsInstrumentOptions("");
  sec.innerHTML =
    panel("Brain Screen — rank conviction", `
      <div class="addbar">
        ${_acFieldHtml("scr-input", "scr-suggest", "type AAPL, MSFT… (blank = tracked equities/ETFs)")}
        <button id="scr-go" class="btn">Screen</button>
      </div>
      <div id="scr-body" style="margin-top:12px"><div class="sub dim">Run a screen to rank the universe by conviction.</div></div>`)
    + panel("Stock Brain — conviction + fundamentals", `
      <div class="sub mb-sm">Pick an equity or ETF from your registry. You can also type any US ticker below for a one-off lookup.</div>
      <select id="fund-pick" class="btn">${html}</select>
      <div class="addbar mt-sm">
        ${_acFieldHtml("fund-input", "fund-suggest", "or type to search any ticker")}
        <button id="fund-go" class="btn">Load</button>
      </div>
      <div id="fund-body" style="margin-top:12px"></div>`);

  const loadSymbol = (sym) => {
    const t = (sym || "").trim().toUpperCase();
    if (!t) return;
    const inp = $("#fund-input");
    if (inp) inp.value = t;
    loadFundamentalsOne(t, labels[t] || t);
  };

  const pick = $("#fund-pick");
  if (pick && pick.value) {
    pick.addEventListener("change", () => loadSymbol(pick.value));
    loadSymbol(pick.value);
  } else if ($("#fund-body")) {
    $("#fund-body").innerHTML = '<div class="dim">Add equities or ETFs in Registry, or enter a ticker above.</div>';
  }

  $("#fund-go").addEventListener("click", () => loadSymbol($("#fund-input").value));
  $("#fund-input").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !listVisible("fund-suggest")) loadSymbol($("#fund-input").value);
  });
  _bindInstrumentAutocomplete({
    input: "#fund-input",
    list: "#fund-suggest",
    assets: ["equity", "etf"],
    onPick: (h) => loadSymbol(h.symbol),
    onEnter: (inp) => loadSymbol(inp.value.trim()),
  });

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
  $("#scr-input").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !listVisible("scr-suggest")) screen();
  });
  _bindInstrumentAutocomplete({
    input: "#scr-input",
    list: "#scr-suggest",
    assets: ["equity", "etf"],
    multiComma: true,
  });
}

function _loadFor(view) {
  if (view === "fundamentals") return loadFundamentals();
  if (view === "crypto-brain") return loadCryptoBrain();
  if (view === "forex-brain") return loadForexBrain();
  if (view === "hitlist") return loadHitlist();
  if (view === "trade-setup") return loadTradeSetup();
  if (view === "market-setup") return loadMarketSetup();
  if (view === "decision") return loadDecision();
  if (view === "news-pulse") return loadNewsPulse();
  if (view === "execution") return loadExecution();
  if (view === "analysis") return loadAnalysis();
  if (view === "focus") return loadFocus();
  if (view === "cot") return loadCot();
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
