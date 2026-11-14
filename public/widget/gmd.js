/*
 * Global Market Desk widget — advisor4u.in
 * WP shortcode [gmd_dashboard mode="public|private"] हा file GitHub Pages वरून load करतो.
 * इथे बदल push केला की ~10 मिनिटांत दोन्ही पानं update होतात — WP मध्ये काही बदलायची गरज नाही.
 */
(function () {
  'use strict';

  // Mode WP shortcode च्या data-mode वरून ठरतो (default 'public' — सुरक्षित)
  var MODE = 'public';

  // GitHub Pages वरचे files (workflow हेच बनवतो)
  var BASE_URL = 'https://pankajsahare.github.io/global-market-desk/';
  var DATA_URL = BASE_URL + 'data/market.json';
  var LOG_URL = BASE_URL + 'log/cue-log.json';
  var MACRO_URL = BASE_URL + 'log/macro.json';
  var TRACK_WINDOW = 30;    // hit-rate साठी शेवटचे किती sessions
  var TRACK_ROWS = 10;      // table मध्ये किती ओळी

  // पानाचा HTML ढाचा (बाहेरचा डेटा यात नाही — म्हणून innerHTML सुरक्षित)
  var MARKUP = `<div class="gmd__print-head">Global Markets Snapshot</div>
  <div class="gmd__top">
    <h1 id="gmd-title">Global Markets</h1>
    <button type="button" class="gmd__print" id="gmd-print">Print / Save PDF</button>
  </div>
  <div class="gmd__meta" id="gmd-updated">Loading market data…</div>
  <div class="gmd__closed" id="gmd-closed" hidden></div>
  <div class="gmd__banner" id="gmd-stale" hidden></div>

  <!-- Public disclaimer (footer शी जुळणारं नाव व ARN) -->
  <div class="gmd__disc" data-mode="public">
    <strong>Disclaimer:</strong> Sahare Wealth is an AMFI-registered Mutual Fund Distributor (ARN-151469).
    Mutual Fund investments are subject to market risks, read all scheme related documents carefully.
    Market data is delayed, sourced from third parties, and shown for information only. It is not investment advice or a recommendation.
  </div>
  <div class="gmd__disc" data-mode="private" hidden>
    <strong>Internal use only.</strong> Rule-based summary of delayed global data for discussion. Not a forecast, research report or investment advice. Do not share publicly.
  </div>

  <!-- PRIVATE: India-open cue + Risk mood -->
  <div class="gmd__grid2" data-mode="private" hidden>
    <div class="gmd__card">
      <h3>India Open — Global Cue</h3>
      <div class="gmd__big" id="gmd-cue-label">—</div>
      <div class="gmd__sub" id="gmd-cue-score"></div>
      <table><thead><tr><th>Component</th><th>Weight</th><th>Move</th><th>Impact</th></tr></thead>
        <tbody id="gmd-cue-rows"></tbody></table>
    </div>
    <div class="gmd__card">
      <h3>Risk Mood</h3>
      <div class="gmd__big" id="gmd-mood-label">—</div>
      <div class="gmd__sub" id="gmd-mood-score"></div>
      <div class="gmd__gauge"><div class="gmd__gauge-mark" id="gmd-mood-mark" style="left:50%"></div></div>
      <ul class="gmd__list" id="gmd-mood-reasons"></ul>
      <div class="gmd__note">Describes current conditions only — not a predictor. In the backtest, mood showed no link with NIFTY 50's next 5 sessions.</div>
    </div>
  </div>

  <div class="gmd__card" id="gmd-summary-card" hidden>
    <h3>What Moved</h3>
    <ul class="gmd__summary" id="gmd-summary"></ul>
  </div>

  <!-- India Macro Snapshot — public/log/macro.json (आठवड्यातून एकदा, macro.yml) -->
  <div class="gmd__card gmd__macro" id="gmd-macro" hidden>
    <h3>India Macro Snapshot</h3>
    <div class="gmd__macro-tiles" id="gmd-macro-tiles"></div>
    <div class="gmd__grid2 gmd__macro-charts">
      <div><div class="gmd__macro-chart-title">CPI inflation, % (year on year) <span class="gmd__macro-key">\u2014 CPI</span> <span class="gmd__macro-key gmd__macro-key--repo">\u2014 Repo rate</span></div><div id="gmd-macro-cpi"></div></div>
      <div><div class="gmd__macro-chart-title">Forex reserves, US$ billion (weekly)</div><div id="gmd-macro-fx"></div></div>
    </div>
    <div class="gmd__note" id="gmd-macro-note"></div>
  </div>

  <!-- S2: FD real value calculator (public) — फक्त FD चं गणित, MF परताव्याचा अंदाज नाही -->
  <div class="gmd__card gmd__calc" id="gmd-calc" hidden>
    <h3>What Is Your FD Really Worth?</h3>
    <div class="gmd__sub">See what a fixed deposit grows to after income tax, and what that amount buys in today's money.</div>
    <div class="gmd__calc-form">
      <label>Amount (&#8377;)<input type="number" id="calc-amount" min="1000" step="1000" value="500000" inputmode="numeric"></label>
      <label>Years<input type="number" id="calc-years" min="1" max="20" step="1" value="5" inputmode="numeric"></label>
      <label>FD rate (% a year)<input type="number" id="calc-rate" min="0" max="15" step="0.05"></label>
      <label>Your tax slab<select id="calc-slab"><option value="0">0%</option><option value="5">5%</option><option value="10">10%</option><option value="15">15%</option><option value="20">20%</option><option value="30" selected>30%</option></select></label>
      <label>Inflation (% a year)<input type="number" id="calc-infl" min="0" max="20" step="0.05"></label>
    </div>
    <div class="gmd__calc-out" id="calc-out"></div>
    <div class="gmd__note">Illustration only. Assumes yearly compounding, tax at your slab plus 4% cess on interest each year, and constant inflation (default: latest CPI). Actual FD terms, TDS and future inflation will differ. Not investment advice.</div>
    <div class="gmd__cta"><a id="calc-wa" href="https://wa.me/919405908605" target="_blank" rel="noopener">Discuss My Savings on WhatsApp</a></div>
  </div>

  <div class="gmd__card">
    <h3>World Markets — Today</h3>
    <div id="gmd-heatmap"></div>
  </div>

  <div class="gmd__card">
    <h3>Risk Indicators</h3>
    <table><thead><tr><th>Indicator</th><th>Last</th><th>1D</th><th>1W</th><th>1M</th><th>3M trend</th></tr></thead>
      <tbody id="gmd-risk"></tbody></table>
  </div>

  <div class="gmd__card">
    <h3>Fund Category Trend (index proxies)</h3>
    <table><thead><tr><th>Category</th><th>Index</th><th>1W</th><th>1M</th><th>3M</th><th>1Y</th></tr></thead>
      <tbody id="gmd-funds"></tbody></table>
    <div class="gmd__note">Index returns are shown as a proxy for each fund category. Actual fund returns will differ.</div>
  </div>

  <!-- PRIVATE: Sector rotation (S2) -->
  <div class="gmd__card" data-mode="private" hidden>
    <h3>Sector Rotation — 1 Month</h3>
    <div id="gmd-rotation"></div>
  </div>

  <!-- PUBLIC: plain sector table (private mode मध्ये फक्त print साठी) -->
  <div class="gmd__card gmd__card--sectors" data-mode="public">
    <h3>Indian Sectors</h3>
    <table><thead><tr><th>Sector</th><th>Last</th><th>1D</th><th>1M</th><th>1Y</th></tr></thead>
      <tbody id="gmd-sectors"></tbody></table>
  </div>

  <!-- PRIVATE: Economic calendar (S1) — TradingView free widget -->
  <div class="gmd__card" data-mode="private" hidden>
    <h3>Economic Calendar</h3>
    <div id="gmd-calendar"></div>
  </div>

  <!-- PRIVATE: Cue track record (S3) -->
  <div class="gmd__card" data-mode="private" hidden>
    <h3>Cue Track Record</h3>
    <div class="gmd__track-rate" id="gmd-track-rate">—</div>
    <div class="gmd__sub" id="gmd-track-sub">Loading…</div>
    <div class="gmd__sub" id="gmd-track-strength"></div>
    <table><thead><tr><th>Date</th><th>Cue</th><th>Score</th><th>NIFTY open gap</th><th>Result</th></tr></thead>
      <tbody id="gmd-track"></tbody></table>
    <div class="gmd__note">A cue counts as correct when its direction (up / flat / down, ±0.15 band) matches NIFTY 50's opening gap versus the previous close (±0.15% band).</div>
  </div>

  <div class="gmd__card" data-mode="private" hidden>
    <h3>How the summary is calculated</h3>
    <ul class="gmd__list" id="gmd-rules"></ul>
  </div>

  <!-- S1: Weekly recap signup CTA — form पानावर CSS ID "recap-signup" असलेल्या भागात -->
  <div class="gmd__card gmd__signup" data-mode="public">
    <div>
      <h3>Get the Weekly Market Recap</h3>
      <div class="gmd__sub">A one-page summary of global and Indian markets, free every Saturday on WhatsApp or email.</div>
    </div>
    <a class="gmd__signup-btn" href="#recap-signup">Subscribe free</a>
  </div>

  <div class="gmd__cta" data-mode="public">
    <a href="https://wa.me/919405908605?text=Hi%2C%20I%20saw%20the%20Global%20Markets%20page%20on%20advisor4u.in" target="_blank" rel="noopener">Chat with Us on WhatsApp</a>
  </div>

  <div class="gmd__print-foot">
    Sahare Wealth · AMFI-registered Mutual Fund Distributor · ARN-151469 · www.advisor4u.in<br>
    Mutual Fund investments are subject to market risks, read all scheme related documents carefully.
    Market data is delayed (source: Yahoo Finance) and shown for information only; not investment advice or a recommendation.
  </div>`;
  var STALE_MINUTES = 60;   // weekday ला यापेक्षा जुना डेटा → warning
  var REGION_ORDER = ['India', 'US', 'Europe', 'Asia'];

  // ---------- India-open cue: components आणि weights ----------
  var CUE_COMPONENTS = [
    { label: 'US close (S&P 500, Nasdaq, Dow)', weight: 0.30, symbols: ['^GSPC', '^IXIC', '^DJI'], invert: false },
    { label: 'Asia now (Nikkei, Hang Seng, Shanghai, KOSPI)', weight: 0.30, symbols: ['^N225', '^HSI', '000001.SS', '^KS11'], invert: false },
    { label: 'US futures (S&P 500, Nasdaq 100)', weight: 0.20, symbols: ['ES=F', 'NQ=F'], invert: false },
    { label: 'USD/INR (weaker rupee = negative)', weight: 0.10, symbols: ['INR=X'], invert: true },
    { label: 'Brent crude (higher = negative for India)', weight: 0.10, symbols: ['BZ=F'], invert: true }
  ];

  var RULE_TEXT = [
    'India-open cue: weighted average of 1-day moves (each capped at ±2%). Score ≥ 0.5 Positive, ≥ 0.15 Mildly Positive, ≤ −0.15 Mildly Negative, ≤ −0.5 Negative, otherwise Flat.',
    'Risk mood starts at 50 and moves with: CBOE VIX (< 16: +10, > 22: −15), India VIX (< 13: +5, > 18: −10), Dollar Index 1W (> +1%: −10, < −1%: +5), US 10Y yield 1W (> +0.10: −10, < −0.10: +5), Brent 1W (> +5%: −10, < −5%: +5), Gold up > 2% in 1W while world equities fall: −5, and world breadth (> 66% of indices up today: +10, < 33%: −10).',
    'Mood ≥ 60 = Risk-On, ≤ 40 = Risk-Off, otherwise Neutral.',
    'Asian markets are live during Indian morning hours; US and Europe show their last close. Data is delayed by 15–30 minutes.'
  ];

  // ---------- helpers ----------
  function $(id) { return document.getElementById(id); }

  // textContent वापरतो — बाहेरचा डेटा HTML म्हणून कधीच चालत नाही
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function avg(values) {
    var xs = values.filter(isNum);
    if (!xs.length) return null;
    return xs.reduce(function (a, b) { return a + b; }, 0) / xs.length;
  }

  function fmt(v, digits) {
    if (!isNum(v)) return '—';
    var d = digits === undefined ? 2 : digits;
    return v.toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  function pctText(v) {
    if (!isNum(v)) return '—';
    return (v >= 0 ? '▲ +' : '▼ ') + v.toFixed(2) + '%';
  }

  function pctCell(v) {
    var td = el('td', isNum(v) ? (v >= 0 ? 'is-up' : 'is-down') : '', pctText(v));
    return td;
  }

  // r1d वरून tile चा रंग — जितका मोठा move तितका गडद
  function tileColor(v) {
    if (!isNum(v)) return '#374151';
    var alpha = clamp(Math.abs(v) / 2, 0.25, 0.95).toFixed(2);
    return v >= 0 ? 'rgba(16,185,129,' + alpha + ')' : 'rgba(239,68,68,' + alpha + ')';
  }

  // छोटा SVG sparkline
  function sparkline(values) {
    var ns = 'http://www.w3.org/2000/svg';
    var w = 90, h = 24;
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('width', w);
    svg.setAttribute('height', h);
    svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
    var pts = (values || []).filter(isNum);
    if (pts.length < 2) return svg;
    var min = Math.min.apply(null, pts), max = Math.max.apply(null, pts);
    var span = max - min || 1;
    var coords = pts.map(function (v, i) {
      return (i / (pts.length - 1) * w).toFixed(1) + ',' + (h - 2 - (v - min) / span * (h - 4)).toFixed(1);
    });
    var line = document.createElementNS(ns, 'polyline');
    line.setAttribute('points', coords.join(' '));
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', pts[pts.length - 1] >= pts[0] ? '#10b981' : '#ef4444');
    line.setAttribute('stroke-width', '1.5');
    svg.appendChild(line);
    return svg;
  }

  function label(item) { return item.name + (item.stale ? ' *' : ''); }

  // US 10Y: Yahoo कधी 42.5 (×10) तर कधी 4.25 देतो — दोन्ही handle करा
  function yieldValue(v, ref) { return isNum(v) && isNum(ref) && ref > 20 ? v / 10 : v; }

  // ---------- calculations ----------
  function computeCue(map) {
    var total = 0, usedWeight = 0, rows = [];
    CUE_COMPONENTS.forEach(function (c) {
      var move = avg(c.symbols.map(function (s) { return map[s] ? map[s].r1d : null; }));
      if (move === null) { rows.push({ c: c, move: null, impact: null }); return; }
      var signal = clamp(c.invert ? -move : move, -2, 2);
      total += signal * c.weight;
      usedWeight += c.weight;
      rows.push({ c: c, move: move, impact: signal * c.weight });
    });
    var score = usedWeight ? total / usedWeight : 0;  // डेटा कमी असल्यास re-normalise
    var text = score >= 0.5 ? 'Positive' : score >= 0.15 ? 'Mildly Positive'
      : score <= -0.5 ? 'Negative' : score <= -0.15 ? 'Mildly Negative' : 'Flat';
    return { score: score, label: text, rows: rows, coverage: usedWeight };
  }

  function computeMood(map, globals) {
    var score = 50, reasons = [];
    function add(points, text) { score += points; reasons.push({ points: points, text: text }); }

    var vix = map['^VIX'];
    if (vix && isNum(vix.last)) {
      if (vix.last < 16) add(10, 'CBOE VIX at ' + fmt(vix.last, 1) + ' (below 16): calm US market');
      else if (vix.last > 22) add(-15, 'CBOE VIX at ' + fmt(vix.last, 1) + ' (above 22): fear rising');
      else add(0, 'CBOE VIX at ' + fmt(vix.last, 1) + ': neutral zone');
    }

    var ivix = map['^INDIAVIX'];
    if (ivix && isNum(ivix.last)) {
      if (ivix.last < 13) add(5, 'India VIX at ' + fmt(ivix.last, 1) + ' (below 13): low volatility');
      else if (ivix.last > 18) add(-10, 'India VIX at ' + fmt(ivix.last, 1) + ' (above 18): high volatility');
      else add(0, 'India VIX at ' + fmt(ivix.last, 1) + ': normal');
    }

    var dxy = map['DX-Y.NYB'];
    if (dxy && isNum(dxy.r1w)) {
      if (dxy.r1w > 1) add(-10, 'Dollar Index up ' + dxy.r1w.toFixed(2) + '% in 1W: pressure on emerging markets');
      else if (dxy.r1w < -1) add(5, 'Dollar Index down ' + Math.abs(dxy.r1w).toFixed(2) + '% in 1W: supportive for emerging markets');
      else add(0, 'Dollar Index stable in 1W (' + dxy.r1w.toFixed(2) + '%)');
    }

    var tnx = map['^TNX'];
    if (tnx && isNum(tnx.d1w)) {
      var dy = yieldValue(tnx.d1w, tnx.last);
      var y = yieldValue(tnx.last, tnx.last);
      if (dy > 0.10) add(-10, 'US 10Y yield up ' + dy.toFixed(2) + ' pts in 1W to ' + fmt(y, 2) + '%');
      else if (dy < -0.10) add(5, 'US 10Y yield down ' + Math.abs(dy).toFixed(2) + ' pts in 1W to ' + fmt(y, 2) + '%');
      else add(0, 'US 10Y yield steady at ' + fmt(y, 2) + '%');
    }

    var brent = map['BZ=F'];
    if (brent && isNum(brent.r1w)) {
      if (brent.r1w > 5) add(-10, 'Brent up ' + brent.r1w.toFixed(2) + '% in 1W: negative for India');
      else if (brent.r1w < -5) add(5, 'Brent down ' + Math.abs(brent.r1w).toFixed(2) + '% in 1W: positive for India');
      else add(0, 'Brent move in 1W: ' + brent.r1w.toFixed(2) + '%');
    }

    var gold = map['GC=F'];
    var worldWeek = avg(globals.map(function (g) { return g.r1w; }));
    if (gold && isNum(gold.r1w) && worldWeek !== null && gold.r1w > 2 && worldWeek < 0) {
      add(-5, 'Gold up ' + gold.r1w.toFixed(2) + '% while world equities fell in 1W: safe-haven demand');
    }

    var withMove = globals.filter(function (g) { return isNum(g.r1d); });
    if (withMove.length) {
      var upShare = withMove.filter(function (g) { return g.r1d > 0; }).length / withMove.length;
      var pct = Math.round(upShare * 100) + '% of world indices up today';
      if (upShare > 0.66) add(10, pct + ': broad strength');
      else if (upShare < 0.33) add(-10, pct + ': broad weakness');
      else add(0, pct + ': mixed');
    }

    score = clamp(Math.round(score), 0, 100);
    var text = score >= 60 ? 'Risk-On' : score <= 40 ? 'Risk-Off' : 'Neutral';
    return { score: score, label: text, reasons: reasons };
  }

  // ---------- renderers ----------
  function renderMeta(data, all) {
    var updated = new Date(data.updated);
    var ageMin = Math.round((Date.now() - updated.getTime()) / 60000);
    $('gmd-updated').textContent = 'Last updated: ' +
      updated.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' }) +
      ' IST · Source: ' + (data.source || 'third-party data') + ' · * = older value';

    var day = new Date().toLocaleString('en-US', { timeZone: 'Asia/Kolkata', weekday: 'short' });
    var weekend = day === 'Sat' || day === 'Sun';
    var staleCount = all.filter(function (i) { return i.stale; }).length;
    var msgs = [];
    if (!weekend && ageMin > STALE_MINUTES) msgs.push('Data is ' + ageMin + ' minutes old.');
    if (staleCount) msgs.push(staleCount + ' item(s) could not be refreshed and show older values.');
    if (msgs.length) { $('gmd-stale').textContent = msgs.join(' '); $('gmd-stale').hidden = false; }
    renderClosed(data, weekend);
  }

  // S1: weekend / सुट्टी — "Markets closed" banner
  function istDateString(d) {
    return d.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });  // YYYY-MM-DD
  }

  function prettyDate(iso) {
    var parts = iso.split('-');
    var d = new Date(Date.UTC(+parts[0], +parts[1] - 1, +parts[2], 12));
    return d.toLocaleDateString('en-IN', { timeZone: 'UTC', weekday: 'short', day: 'numeric', month: 'short' });
  }

  function renderClosed(data, weekend) {
    var globals = ((data.groups || {}).global || []).filter(function (g) { return g.asof; });
    if (!globals.length) return;
    var today = istDateString(new Date());
    var latest = globals.map(function (g) { return g.asof; }).sort().pop();
    var nifty = globals.filter(function (g) { return g.symbol === '^NSEI'; })[0];
    var hourIst = +new Date().toLocaleString('en-US', { timeZone: 'Asia/Kolkata', hour: 'numeric', hourCycle: 'h23' });
    var text = '';
    if (weekend) {
      text = 'Markets closed for the weekend — showing last close (' + prettyDate(latest) + ').';
    } else if (latest < today && hourIst >= 10) {
      text = 'Most markets are closed today — showing last close (' + prettyDate(latest) + ').';
    } else if (nifty && nifty.asof < today && hourIst >= 10) {
      text = 'Indian markets are closed today — Indian values show the last close (' + prettyDate(nifty.asof) + ').';
    }
    if (text) { $('gmd-closed').textContent = text; $('gmd-closed').hidden = false; }
  }

  // S2: "What moved" — build_data.py ने बनवलेली वाक्यं (फक्त घडलेल्या घटना)
  function renderSummary(lines) {
    if (!Array.isArray(lines) || !lines.length) return;
    var list = $('gmd-summary');
    list.textContent = '';
    lines.forEach(function (t) { list.appendChild(el('li', '', String(t))); });
    $('gmd-summary-card').hidden = false;
  }

  function renderHeatmap(globals) {
    var box = $('gmd-heatmap');
    box.textContent = '';
    REGION_ORDER.forEach(function (region) {
      var items = globals.filter(function (g) { return g.region === region; });
      if (!items.length) return;
      var wrap = el('div', 'gmd__region');
      wrap.appendChild(el('div', 'gmd__region-name', region));
      var tiles = el('div', 'gmd__tiles');
      items.forEach(function (it) {
        var tile = el('div', 'gmd__tile');
        tile.style.background = tileColor(it.r1d);
        tile.appendChild(el('div', 'gmd__tile-name', label(it)));
        tile.appendChild(el('div', 'gmd__tile-last', fmt(it.last)));
        tile.appendChild(el('div', 'gmd__tile-chg', pctText(it.r1d)));
        tiles.appendChild(tile);
      });
      wrap.appendChild(tiles);
      box.appendChild(wrap);
    });
  }

  function renderRisk(items) {
    var body = $('gmd-risk');
    body.textContent = '';
    items.forEach(function (it) {
      var tr = el('tr');
      tr.appendChild(el('td', '', label(it)));
      var digits = it.symbol === '^TNX' ? 3 : 2;
      tr.appendChild(el('td', '', fmt(it.last, digits)));
      tr.appendChild(pctCell(it.r1d));
      tr.appendChild(pctCell(it.r1w));
      tr.appendChild(pctCell(it.r1m));
      var sp = el('td');
      sp.appendChild(sparkline(it.spark));
      tr.appendChild(sp);
      body.appendChild(tr);
    });
  }

  function renderFunds(items) {
    var body = $('gmd-funds');
    body.textContent = '';
    items.forEach(function (it) {
      var tr = el('tr');
      tr.appendChild(el('td', '', it.category || '—'));
      tr.appendChild(el('td', '', label(it)));
      tr.appendChild(pctCell(it.r1w));
      tr.appendChild(pctCell(it.r1m));
      tr.appendChild(pctCell(it.r3m));
      tr.appendChild(pctCell(it.r1y));
      body.appendChild(tr);
    });
  }

  function renderSectors(items) {
    var body = $('gmd-sectors');
    body.textContent = '';
    items.forEach(function (it) {
      var tr = el('tr');
      tr.appendChild(el('td', '', label(it)));
      tr.appendChild(el('td', '', fmt(it.last)));
      tr.appendChild(pctCell(it.r1d));
      tr.appendChild(pctCell(it.r1m));
      tr.appendChild(pctCell(it.r1y));
      body.appendChild(tr);
    });
  }

  // S2: 1M returns वर sorted bars, top 3 / bottom 3 badges
  function renderRotation(items) {
    var box = $('gmd-rotation');
    box.textContent = '';
    var rows = items.filter(function (i) { return isNum(i.r1m); })
      .sort(function (a, b) { return b.r1m - a.r1m; });
    if (!rows.length) { box.textContent = 'No sector data available.'; return; }
    var maxAbs = Math.max.apply(null, rows.map(function (r) { return Math.abs(r.r1m); })) || 1;
    rows.forEach(function (it, idx) {
      var row = el('div', 'gmd__bar-row');
      var name = el('div', '', label(it));
      if (idx < 3) name.appendChild(el('span', 'gmd__badge gmd__badge--top', 'Top ' + (idx + 1)));
      if (idx >= rows.length - 3 && rows.length > 3) name.appendChild(el('span', 'gmd__badge gmd__badge--bottom', 'Bottom ' + (rows.length - idx)));
      row.appendChild(name);
      var track = el('div', 'gmd__bar-track');
      var bar = el('div', 'gmd__bar');
      var widthPct = Math.abs(it.r1m) / maxAbs * 50;
      bar.style.width = widthPct.toFixed(1) + '%';
      bar.style.left = it.r1m >= 0 ? '50%' : (50 - widthPct).toFixed(1) + '%';
      bar.style.background = it.r1m >= 0 ? '#10b981' : '#ef4444';
      track.appendChild(bar);
      track.appendChild(el('div', 'gmd__bar-axis'));
      row.appendChild(track);
      row.appendChild(el('div', it.r1m >= 0 ? 'is-up' : 'is-down', (it.r1m >= 0 ? '+' : '') + it.r1m.toFixed(2) + '%'));
      box.appendChild(row);
    });
  }

  function renderCue(cue) {
    $('gmd-cue-label').textContent = cue.label;
    $('gmd-cue-label').className = 'gmd__big ' + (cue.score >= 0.15 ? 'is-up' : cue.score <= -0.15 ? 'is-down' : '');
    $('gmd-cue-score').textContent = 'Score ' + cue.score.toFixed(2) + ' (range −2 to +2) · data coverage ' + Math.round(cue.coverage * 100) + '%';
    var body = $('gmd-cue-rows');
    body.textContent = '';
    cue.rows.forEach(function (r) {
      var tr = el('tr');
      tr.appendChild(el('td', '', r.c.label));
      tr.appendChild(el('td', '', Math.round(r.c.weight * 100) + '%'));
      tr.appendChild(pctCell(r.move));
      tr.appendChild(el('td', isNum(r.impact) ? (r.impact >= 0 ? 'is-up' : 'is-down') : '',
        isNum(r.impact) ? (r.impact >= 0 ? '+' : '') + r.impact.toFixed(2) : 'n/a'));
      body.appendChild(tr);
    });
  }

  function renderMood(mood) {
    $('gmd-mood-label').textContent = mood.label;
    $('gmd-mood-label').className = 'gmd__big ' + (mood.score >= 60 ? 'is-up' : mood.score <= 40 ? 'is-down' : '');
    $('gmd-mood-score').textContent = 'Score ' + mood.score + ' / 100';
    $('gmd-mood-mark').style.left = mood.score + '%';
    var list = $('gmd-mood-reasons');
    list.textContent = '';
    mood.reasons.forEach(function (r) {
      var li = el('li');
      li.appendChild(el('span', 'gmd__pts ' + (r.points > 0 ? 'is-up' : r.points < 0 ? 'is-down' : ''),
        (r.points > 0 ? '+' : '') + r.points));
      li.appendChild(el('span', '', r.text));
      list.appendChild(li);
    });
  }

  function renderRules() {
    var list = $('gmd-rules');
    list.textContent = '';
    RULE_TEXT.forEach(function (t) { list.appendChild(el('li', '', t)); });
  }

  // S1: TradingView economic calendar (फक्त private mode मध्ये load)
  function loadCalendar() {
    var box = $('gmd-calendar');
    if (!box || box.childNodes.length) return;
    var wrap = el('div', 'tradingview-widget-container');
    wrap.appendChild(el('div', 'tradingview-widget-container__widget'));
    var s = document.createElement('script');
    s.src = 'https://s3.tradingview.com/external-embedding/embed-widget-events.js';
    s.async = true;
    s.textContent = JSON.stringify({
      colorTheme: 'dark', isTransparent: true, width: '100%', height: 480, locale: 'en',
      importanceFilter: '0,1', countryFilter: 'in,us,eu,gb,jp,cn'
    });
    wrap.appendChild(s);
    box.appendChild(wrap);
  }

  // S3: cue log → hit-rate + शेवटच्या नोंदी
  function renderTrack(log) {
    var entries = (log && Array.isArray(log.entries)) ? log.entries : [];
    var done = entries.filter(function (e) { return e.status === 'done'; });
    var recent = done.slice(-TRACK_WINDOW);
    var hits = recent.filter(function (e) { return e.hit === true; }).length;
    if (recent.length) {
      $('gmd-track-rate').textContent = Math.round(hits / recent.length * 100) + '%';
      $('gmd-track-sub').textContent = hits + ' of ' + recent.length + ' sessions correct (last ' + TRACK_WINDOW + ' max)' +
        (recent.length < 20 ? ' · small sample, treat with caution' : '');
    } else {
      $('gmd-track-rate').textContent = '—';
      $('gmd-track-sub').textContent = 'No evaluated sessions yet. The first result appears after the next trading day.';
    }
    // S2: cue किती ठाम होता त्यानुसार live hit-rate (strong |score| ≥ 0.5, mild 0.15–0.5)
    var parts = [['Strong', function (a) { return a >= 0.5; }], ['Mild', function (a) { return a >= 0.15 && a < 0.5; }],
                 ['Flat', function (a) { return a < 0.15; }]].map(function (b) {
      var group = recent.filter(function (e) { return isNum(e.cueScore) && b[1](Math.abs(e.cueScore)); });
      var h = group.filter(function (e) { return e.hit === true; }).length;
      return group.length ? b[0] + ' cues: ' + h + '/' + group.length : null;
    }).filter(Boolean);
    $('gmd-track-strength').textContent = parts.length ? parts.join(' · ') : '';

    var body = $('gmd-track');
    body.textContent = '';
    entries.filter(function (e) { return e.status !== 'holiday'; }).slice(-TRACK_ROWS).reverse().forEach(function (e) {
      var tr = el('tr');
      tr.appendChild(el('td', '', e.date));
      tr.appendChild(el('td', '', e.cueLabel || '—'));
      tr.appendChild(el('td', '', isNum(e.cueScore) ? (e.cueScore >= 0 ? '+' : '') + e.cueScore.toFixed(2) : '—'));
      tr.appendChild(pctCell(e.actualGapPct));
      var res = e.status === 'done' ? (e.hit ? '✓ Correct' : '✗ Missed') : 'Pending';
      tr.appendChild(el('td', 'gmd__hit ' + (e.status === 'done' ? (e.hit ? 'is-up' : 'is-down') : ''), res));
      body.appendChild(tr);
    });
  }

  // ---------- India Macro Snapshot ----------
  var MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  // "2026-09" किंवा "2026-10-30" → "Sep 2026" / "30 Oct 2026"
  function periodText(p) {
    var m = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/.exec(String(p || ''));
    if (!m) return String(p || '—');
    var month = MONTH_SHORT[parseInt(m[2], 10) - 1] + ' ' + m[1];
    return m[3] ? parseInt(m[3], 10) + ' ' + month : month;
  }

  function macroTile(name, value, sub, stale) {
    var tile = el('div', 'gmd__macro-tile');
    tile.appendChild(el('div', 'gmd__macro-name', name + (stale ? ' *' : '')));
    tile.appendChild(el('div', 'gmd__macro-value', value));
    tile.appendChild(el('div', 'gmd__macro-sub', sub));
    return tile;
  }

  // Axis सह छोटा line chart (SVG) — [[label, value], ...]
  // overlay (optional) = points शी जुळणारी दुसरी रेषा (उदा. repo rate), step स्वरूपात
  function lineChart(points, unit, overlay) {
    var ns = 'http://www.w3.org/2000/svg';
    var w = 320, h = 120, padL = 34, padB = 18, padT = 8;
    var pts = (points || []).map(function (p, i) { return p && [p[0], p[1], overlay ? overlay[i] : null]; })
      .filter(function (p) { return p && isNum(p[1]); });
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
    svg.setAttribute('class', 'gmd__macro-svg');
    svg.setAttribute('role', 'img');
    if (pts.length < 2) return svg;
    var vals = pts.map(function (p) { return p[1]; });
    var both = vals.concat(pts.map(function (p) { return p[2]; }).filter(isNum));
    var min = Math.min.apply(null, both), max = Math.max.apply(null, both);
    var pad = (max - min) * 0.1 || 1;
    min -= pad; max += pad;
    function x(i) { return padL + i / (pts.length - 1) * (w - padL - 4); }
    function y(v) { return padT + (max - v) / (max - min) * (h - padT - padB); }
    function text(tx, ty, s, anchor) {
      var t = document.createElementNS(ns, 'text');
      t.setAttribute('x', tx); t.setAttribute('y', ty);
      t.setAttribute('text-anchor', anchor || 'start');
      t.setAttribute('class', 'gmd__macro-axis');
      t.textContent = s;
      svg.appendChild(t);
    }
    [max - pad, min + pad].forEach(function (v) {
      var g = document.createElementNS(ns, 'line');
      g.setAttribute('x1', padL); g.setAttribute('x2', w - 4);
      g.setAttribute('y1', y(v)); g.setAttribute('y2', y(v));
      g.setAttribute('class', 'gmd__macro-grid');
      svg.appendChild(g);
      text(padL - 4, y(v) + 3, v.toFixed(unit === '%' ? 1 : 0), 'end');
    });
    var steps = [];
    pts.forEach(function (p, i) {
      if (!isNum(p[2])) return;
      if (steps.length) steps.push(x(i).toFixed(1) + ',' + steps[steps.length - 1].split(',')[1]);
      steps.push(x(i).toFixed(1) + ',' + y(p[2]).toFixed(1));
    });
    if (steps.length > 1) {
      var repoLine = document.createElementNS(ns, 'polyline');
      repoLine.setAttribute('points', steps.join(' '));
      repoLine.setAttribute('class', 'gmd__macro-line2');
      svg.appendChild(repoLine);
    }
    var line = document.createElementNS(ns, 'polyline');
    line.setAttribute('points', pts.map(function (p, i) { return x(i).toFixed(1) + ',' + y(p[1]).toFixed(1); }).join(' '));
    line.setAttribute('class', 'gmd__macro-line');
    svg.appendChild(line);
    var dot = document.createElementNS(ns, 'circle');
    dot.setAttribute('cx', x(pts.length - 1)); dot.setAttribute('cy', y(vals[vals.length - 1]));
    dot.setAttribute('r', 3); dot.setAttribute('class', 'gmd__macro-dot');
    svg.appendChild(dot);
    text(padL, h - 4, periodText(pts[0][0]));
    text(w - 4, h - 4, periodText(pts[pts.length - 1][0]), 'end');
    var title = document.createElementNS(ns, 'title');
    title.textContent = 'Latest ' + fmt(vals[vals.length - 1], unit === '%' ? 2 : 1) + (unit === '%' ? '%' : ' bn');
    svg.appendChild(title);
    return svg;
  }

  function renderMacro(m) {
    if (!m || !m.repo) return;
    var tiles = $('gmd-macro-tiles');
    tiles.textContent = '';
    var anyStale = false;
    function add(item, name, value, sub) {
      if (!item) return;
      anyStale = anyStale || !!item.stale;
      tiles.appendChild(macroTile(name, value, sub, item.stale));
    }
    add(m.repo, 'RBI Repo Rate', fmt(m.repo.value, 2) + '%', 'Since ' + periodText(m.repo.as_of));
    add(m.cpi, 'CPI Inflation', m.cpi && fmt(m.cpi.value, 2) + '%', m.cpi && 'Year on year \u00b7 ' + periodText(m.cpi.period));
    add(m.gdp, 'Real GDP Growth', m.gdp && fmt(m.gdp.value, 1) + '%', m.gdp && 'Year on year \u00b7 ' + m.gdp.period);
    add(m.forex, 'Forex Reserves', m.forex && 'US$ ' + fmt(m.forex.value, 1) + ' bn',
      m.forex && ('As on ' + periodText(m.forex.as_of) +
        (isNum(m.forex.change_week) ? ' \u00b7 ' + (m.forex.change_week >= 0 ? '+' : '\u2212') + Math.abs(m.forex.change_week).toFixed(1) + ' bn wk' : '')));
    // S2: FD दर − CPI = खरा परतावा (महागाईनंतर)
    if (m.real_return && m.fd) {
      var rr = m.real_return.value;
      var tile = macroTile('Real FD Return', (rr >= 0 ? '+' : '\u2212') + Math.abs(rr).toFixed(2) + '%',
        (m.fd.label || 'Bank FD') + ' ' + fmt(m.fd.value, 2) + '% \u2212 CPI ' + fmt(m.real_return.cpi, 2) + '%', false);
      tile.classList.add(rr >= 0 ? 'is-up' : 'is-down');
      tiles.appendChild(tile);
    }
    add(m.gsec, '10Y G-Sec Yield', m.gsec && fmt(m.gsec.value, 2) + '%',
      m.gsec && (m.gsec.bond + ' \u00b7 ' + periodText(m.gsec.as_of) +
        (isNum(m.gsec.change_week_bp) ? ' \u00b7 ' + (m.gsec.change_week_bp >= 0 ? '+' : '\u2212') + Math.abs(m.gsec.change_week_bp) + ' bp wk' : '')));
    $('gmd-macro-cpi').appendChild(lineChart(m.cpi && m.cpi.history, '%', m.cpi && m.cpi.repo));
    $('gmd-macro-fx').appendChild(lineChart(m.forex && m.forex.history, 'bn'));
    $('gmd-macro-note').textContent = 'Sources: RBI (repo rate, Weekly Statistical Supplement, G-Sec market trends) and MoSPI (CPI base 2024, GDP base 2022-23). ' +
      'Checked daily; each figure shows its own reference period.' +
      (m.cpi && m.cpi.base_2012_until ? ' CPI up to ' + periodText(m.cpi.base_2012_until) + ' is from the older base-2012 series.' : '') +
      (m.fd ? ' Real FD return = ' + (m.fd.label || 'bank FD') + ' rate minus latest CPI inflation, before tax; illustrative only.' : '') +
      (anyStale ? ' * Latest update failed; previous value shown.' : '');
    $('gmd-macro').hidden = false;
    if (MODE === 'public') setupCalc(m);
  }

  // ---------- S2: FD real value calculator ----------
  function inr(v) { return '\u20b9' + Math.round(v).toLocaleString('en-IN'); }

  function setupCalc(m) {
    var ids = ['calc-amount', 'calc-years', 'calc-rate', 'calc-slab', 'calc-infl'];
    if (m.fd && isNum(m.fd.value)) $('calc-rate').value = m.fd.value.toFixed(2);
    else $('calc-rate').value = '6.50';
    $('calc-infl').value = (m.cpi && isNum(m.cpi.value) ? m.cpi.value : 5).toFixed(2);

    function num(id) { var v = parseFloat($(id).value); return isFinite(v) ? v : NaN; }
    function stat(label, value, cls) {
      var box = el('div', 'gmd__calc-stat' + (cls ? ' ' + cls : ''));
      box.appendChild(el('div', 'gmd__macro-name', label));
      box.appendChild(el('div', 'gmd__macro-value', value));
      return box;
    }
    function update() {
      var p = num('calc-amount'), n = Math.round(num('calc-years')), r = num('calc-rate') / 100;
      var t = num('calc-slab') * 1.04 / 100, i = num('calc-infl') / 100;
      var out = $('calc-out');
      out.textContent = '';
      if (!(p > 0) || !(n >= 1 && n <= 40) || !(r >= 0) || !(i >= 0)) {
        out.appendChild(el('div', 'gmd__sub', 'Enter an amount, 1 to 40 years, and rates of 0% or more.'));
        return;
      }
      var gross = p * Math.pow(1 + r, n);
      var net = p * Math.pow(1 + r * (1 - t), n);
      var today = net / Math.pow(1 + i, n);
      var realRate = ((1 + r * (1 - t)) / (1 + i) - 1) * 100;
      out.appendChild(stat('Maturity before tax', inr(gross)));
      out.appendChild(stat('After income tax', inr(net)));
      out.appendChild(stat("In today's money", inr(today), today >= p ? 'is-up' : 'is-down'));
      out.appendChild(stat('Real return a year', (realRate >= 0 ? '+' : '\u2212') + Math.abs(realRate).toFixed(2) + '%', realRate >= 0 ? 'is-up' : 'is-down'));
      var msg = 'Hi, I used the FD calculator on advisor4u.in. ' + inr(p) + ' for ' + n + ' years at ' + (r * 100).toFixed(2) +
        '% works out to ' + inr(today) + " in today's money. I'd like to discuss my savings.";
      $('calc-wa').href = 'https://wa.me/919405908605?text=' + encodeURIComponent(msg);
    }
    ids.forEach(function (id) { $(id).addEventListener('input', update); $(id).addEventListener('change', update); });
    update();
    $('gmd-calc').hidden = false;
  }

  function loadMacro() {
    fetch(MACRO_URL + '?v=' + Math.floor(Date.now() / 3600000), { credentials: 'omit' })
      .then(function (res) { if (!res.ok) throw new Error('HTTP ' + res.status); return res.json(); })
      .then(renderMacro)
      .catch(function () { /* macro नसला तरी बाकी dashboard चालू — card लपलेलंच राहतं */ });
  }

  function loadTrack() {
    fetch(LOG_URL + '?v=' + Math.floor(Date.now() / 300000), { credentials: 'omit' })
      .then(function (res) { if (!res.ok) throw new Error('HTTP ' + res.status); return res.json(); })
      .then(renderTrack)
      .catch(function () { renderTrack(null); });
  }

  function applyMode() {
    var nodes = document.querySelectorAll('#gmd-root [data-mode]');
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].hidden = nodes[i].getAttribute('data-mode') !== MODE;
    }
    $('gmd-title').textContent = MODE === 'private' ? 'Morning Desk — Global Cues' : 'Global Markets';
  }

  function showError() {
    $('gmd-updated').textContent = 'Market data is temporarily unavailable. Please check back shortly.';
  }

  // ---------- start ----------
  function start() {
    var root = document.getElementById('gmd-root');
    if (!root || root.getAttribute('data-gmd-ready')) return;
    root.setAttribute('data-gmd-ready', '1');      // दोनदा render टाळा
    MODE = root.getAttribute('data-mode') === 'private' ? 'private' : 'public';
    root.classList.add('gmd');
    root.innerHTML = MARKUP;

    applyMode();
    $('gmd-print').addEventListener('click', function () { window.print(); });
    if (MODE === 'private') { renderRules(); loadCalendar(); loadTrack(); }
    loadMacro();

    // 5-मिनिटांचा cache-buster — CDN cache मधला खूप जुना डेटा टाळतो
    var bucket = Math.floor(Date.now() / 300000);
    fetch(DATA_URL + '?v=' + bucket, { credentials: 'omit' })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        var groups = (data && data.groups) || {};
        var globals = groups.global || [], risk = groups.risk || [];
        var sectors = groups.sectors || [], funds = groups.funds || [];
        var all = globals.concat(risk, sectors, funds);
        if (!all.length) throw new Error('Empty data');

        var map = {};
        all.forEach(function (i) { map[i.symbol] = i; });

        renderMeta(data, all);
        renderSummary(data.summary);
        renderSectors(sectors);  // private mode मध्ये फक्त print साठी
        renderHeatmap(globals);
        renderRisk(risk);
        renderFunds(funds);

        if (MODE === 'private') {
          renderCue(computeCue(map));
          renderMood(computeMood(map, globals));
          renderRotation(sectors);
        }
      })
      .catch(function (err) {
        console.error('Global Market Desk: data load failed', err);
        showError();
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
