# dashboard_server.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import ccxt
import pandas as pd
from config import API_KEY, SECRET, SYMBOL, TIMEFRAME, STATE_FILE
from strategy import apply_indicators

exchange = ccxt.binance({
    'apiKey': API_KEY, 'secret': SECRET, 'enableRateLimit': True
})

# ─────────────────────────────────────────────────────────────────────────────
HTML_CONTENT = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Dashboard Robô BTC</title>
    <script src="https://unpkg.com/lightweight-charts@3.8.0/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: #0d1117; color: #c9d1d9;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            height: 100vh; display: flex; flex-direction: column; overflow: hidden;
        }

        /* ── HEADER ──────────────────────────────────────────────────────── */
        .header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 0 18px; height: 40px; flex-shrink: 0;
            background: #161b22; border-bottom: 1px solid #21262d;
        }
        .header-left { display: flex; align-items: center; gap: 10px; }
        .header h1   { font-size: .87rem; font-weight: 700; color: #f0f6fc; }
        .live-badge  {
            display: flex; align-items: center; gap: 4px;
            background: rgba(126,231,135,.1); border: 1px solid rgba(126,231,135,.3);
            border-radius: 20px; padding: 2px 8px; font-size: .61rem; color: #7ee787; font-weight: 700;
        }
        .live-dot { width: 5px; height: 5px; border-radius: 50%; background: #7ee787; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.2} }
        .header-right { font-size: .66rem; color: #8b949e; }

        /* ── CARDS ───────────────────────────────────────────────────────── */
        .cards {
            display: grid; grid-template-columns: repeat(6,1fr);
            gap: 5px; padding: 5px 18px; flex-shrink: 0;
        }
        .card {
            background: #161b22; border: 1px solid #21262d;
            border-radius: 7px; padding: 6px 10px;
            position: relative; overflow: hidden; transition: border-color .4s;
        }
        .card-glow { position: absolute; top: 0; left: 0; right: 0; height: 2px; border-radius: 7px 7px 0 0; transition: background .4s; }
        .card-label { font-size: .56rem; color: #8b949e; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 1px; }
        .card-value { font-size: 1.1rem; font-weight: 700; line-height: 1.1; }
        .card-sub   { font-size: .59rem; color: #8b949e; margin-top: 1px; }

        /* ── CONDITIONS STRIP ────────────────────────────────────────────── */
        .cond-strip {
            display: flex; align-items: center; gap: 6px;
            padding: 0 18px; height: 34px; flex-shrink: 0;
            background: #0a0d12; border-bottom: 1px solid #21262d;
            overflow-x: auto;
        }
        .cond-strip::-webkit-scrollbar { display: none; }
        .strip-lbl {
            font-size: .58rem; color: #8b949e; text-transform: uppercase;
            letter-spacing: .07em; font-weight: 700; flex-shrink: 0; white-space: nowrap;
        }
        .pill {
            display: flex; align-items: center; gap: 3px; padding: 2px 9px;
            border-radius: 20px; font-size: .65rem; font-weight: 700;
            transition: all .4s; flex-shrink: 0; white-space: nowrap;
        }
        .pill.ok   { background: rgba(126,231,135,.1); border: 1px solid rgba(126,231,135,.3); color: #7ee787; }
        .pill.fail { background: rgba(30,36,44,.8); border: 1px solid #1c2128; color: #3d444d; }
        .pill-sell.ok   { background: rgba(248,81,73,.1); border: 1px solid rgba(248,81,73,.3); color: #f85149; }
        .pill-sell.fail { background: rgba(30,36,44,.8); border: 1px solid #1c2128; color: #3d444d; }
        .strip-sep  { color: #21262d; flex-shrink: 0; }
        #strip-cnt  { margin-left: auto; padding: 2px 8px; border-radius: 10px; font-size: .68rem; font-weight: 700; flex-shrink: 0; }
        .sc-ok  { background: rgba(126,231,135,.15); color: #7ee787; }
        .sc-mid { background: rgba(241,224,90,.12);  color: #f1e05a; }
        .sc-low { background: rgba(30,36,44,.8);     color: #3d444d; }

        /* ── CHARTS ──────────────────────────────────────────────────────── */
        .charts-wrap {
            flex: 1; min-height: 0; display: flex; flex-direction: column;
            padding: 4px 18px; gap: 3px;
        }
        .chart-box {
            position: relative; background: #161b22;
            border: 1px solid #21262d; border-radius: 7px; overflow: hidden;
        }
        .chart-inner { width: 100%; height: 100%; }
        #main-box { flex: 5; }
        #didi-box { flex: 2; }
        .chart-label {
            position: absolute; top: 5px; left: 9px; z-index: 10;
            font-size: .57rem; font-weight: 600; color: #8b949e;
            letter-spacing: .05em; pointer-events: none;
        }
        .leg { font-size: .57rem; }
        #main-loading {
            position: absolute; top: 50%; left: 50%;
            transform: translate(-50%,-50%);
            color: #8b949e; font-size: .78rem; z-index: 5;
        }

        /* ── BOTTOM ──────────────────────────────────────────────────────── */
        .bottom-row {
            display: grid; grid-template-columns: 1fr 1fr;
            gap: 5px; padding: 3px 18px 9px; flex-shrink: 0;
        }
        .panel {
            background: #161b22; border: 1px solid #21262d;
            border-radius: 7px; padding: 7px 11px; overflow: hidden;
        }
        .panel-title {
            font-size: .58rem; color: #8b949e; text-transform: uppercase;
            letter-spacing: .08em; margin-bottom: 5px;
            display: flex; align-items: center; justify-content: space-between;
        }
        .ind-section { margin-bottom: 4px; }
        .ind-hdr {
            font-size: .54rem; color: #3d444d; text-transform: uppercase;
            letter-spacing: .06em; margin-bottom: 2px; padding-bottom: 2px;
            border-bottom: 1px solid #1c2128;
        }
        .ind-row {
            display: grid; grid-template-columns: 70px 1fr auto;
            align-items: center; gap: 4px;
            padding: 1.5px 0; font-size: .69rem;
        }
        .ind-name { color: #8b949e; font-size: .62rem; font-weight: 600; }
        .ind-val  { font-weight: 700; color: #f0f6fc; }
        .ind-tag  { font-size: .59rem; padding: 1px 5px; border-radius: 4px; font-weight: 600; text-align: center; }
        .tag-up  { background: rgba(38,166,154,.15); color: #26a69a; }
        .tag-dn  { background: rgba(239,83,80,.15);  color: #ef5350; }
        .tag-neu { background: rgba(139,148,158,.1); color: #8b949e; }
        .tag-wht { background: rgba(255,255,255,.1); color: #fff; }

        /* Faixa Branca badge */
        .faixa-badge {
            display: inline-flex; align-items: center; gap: 4px;
            padding: 2px 8px; border-radius: 4px; font-size: .64rem; font-weight: 700;
            margin-top: 3px; width: 100%;
        }
        .fb-setup  { background: rgba(255,255,255,.1); border: 1px solid rgba(255,255,255,.2); color: #fff; }
        .fb-normal { background: rgba(30,36,44,.8); border: 1px solid #1c2128; color: #3d444d; }

        /* Trade log */
        .trade-row {
            display: flex; align-items: center; gap: 5px;
            padding: 2.5px 0; border-bottom: 1px solid #1c2128; font-size: .69rem;
        }
        .trade-row:last-child { border-bottom: none; }
        .trade-badge { padding: 1px 5px; border-radius: 3px; font-size: .58rem; font-weight: 700; text-transform: uppercase; flex-shrink: 0; }
        .b-buy  { background: rgba(59,130,246,.15); color: #3b82f6; border: 1px solid rgba(59,130,246,.3); }
        .b-sell { background: rgba(251,191,36,.12); color: #fbbf24; border: 1px solid rgba(251,191,36,.3); }
        .t-price{ font-weight: 600; color: #f0f6fc; }
        .t-pnl  { margin-left: auto; font-weight: 600; flex-shrink: 0; }
        .t-time { color: #8b949e; font-size: .6rem; flex-shrink: 0; }
        .no-trades { color: #8b949e; font-size: .71rem; text-align: center; padding: 8px 0; line-height: 1.6; }

        /* Colors */
        .c-blue  { color: #3b82f6; } .c-green { color: #7ee787; }
        .c-red   { color: #f85149; } .c-yellow{ color: #fbbf24; }
        .c-gray  { color: #8b949e; } .c-white { color: #f0f6fc; }
        .c-orange{ color: #fb923c; } .c-purple{ color: #c084fc; }
        .c-pink  { color: #f0abfc; }

        /* ── Nav Buttons (rolar para cima/baixo) ─────────────────────────── */
        #chart-nav {
            position: absolute; right: 66px; top: 50%;
            transform: translateY(-50%); z-index: 20;
            display: flex; flex-direction: column; gap: 3px;
        }
        #chart-nav button {
            width: 26px; height: 26px;
            background: rgba(13,17,23,.88);
            border: 1px solid #30363d; border-radius: 5px;
            color: #8b949e; font-size: .72rem; cursor: pointer;
            transition: border-color .2s, color .2s; padding: 0; line-height: 1;
        }
        #chart-nav button:hover  { border-color: #58a6ff; color: #58a6ff; }
        #chart-nav button:active { opacity: .65; }
        #chart-nav .btn-fit { font-size: .62rem; }
        #chart-nav .btn-tip {
            font-size: .52rem; color: #484f58; text-align: center;
            margin-top: 1px; letter-spacing: -.01em; line-height: 1.2;
        }

        /* Toast */
        #toast {
            position: fixed; top: 46px; right: 15px; z-index: 9999;
            background: #1c2128; border: 1px solid #30363d; border-radius: 9px;
            padding: 8px 13px; font-size: .76rem; font-weight: 600;
            box-shadow: 0 8px 32px rgba(0,0,0,.7);
            transform: translateX(120%); transition: transform .35s cubic-bezier(.175,.885,.32,1.275);
            max-width: 230px; line-height: 1.5;
        }
        #toast.show { transform: translateX(0); }
        @keyframes card-flash {
            0%  { background: rgba(59,130,246,.2); border-color: #3b82f6; }
            100%{ background: #161b22; border-color: #21262d; }
        }
        .card.flash { animation: card-flash 2s ease; }
        @keyframes buy-flash {
            0%,100%{ opacity: 1; } 50%{ opacity: .4; }
        }
        .blink { animation: buy-flash 1s infinite; }
    </style>
</head>
<body>

<!-- ── HEADER ──────────────────────────────────────────────────────────────── -->
<div class="header">
    <div class="header-left">
        <h1>🤖 Robô BTC/USDT</h1>
        <div class="live-badge"><div class="live-dot"></div>AO VIVO</div>
    </div>
    <div class="header-right">
        Timeframe: <strong style="color:#f0f6fc">15m</strong>
        &nbsp;·&nbsp; Supertrend + EMA50 + Didi WDO Master (Welles Wilder)
        &nbsp;·&nbsp; <span id="last-update">--:--:--</span>
    </div>
</div>

<!-- ── CARDS ───────────────────────────────────────────────────────────────── -->
<div class="cards">
    <div class="card">
        <div class="card-glow" style="background:linear-gradient(90deg,#3b82f6,#1d4ed8)"></div>
        <div class="card-label">💰 Preço BTC</div>
        <div class="card-value c-blue" id="c-price">$0.00</div>
        <div class="card-sub" id="c-price-sub">–</div>
    </div>
    <div class="card">
        <div class="card-glow" id="st-glow" style="background:#3d444d"></div>
        <div class="card-label">🌊 Supertrend</div>
        <div class="card-value c-gray" id="c-st">–</div>
        <div class="card-sub" id="c-st-sub">ATR 10 · mult 2.5</div>
    </div>
    <div class="card">
        <div class="card-glow" id="ema-glow" style="background:#3d444d"></div>
        <div class="card-label">📈 EMA 50</div>
        <div class="card-value c-gray" id="c-ema">–</div>
        <div class="card-sub" id="c-ema-sub">vs Preço atual</div>
    </div>
    <div class="card">
        <div class="card-glow" id="didi-glow" style="background:#3d444d"></div>
        <div class="card-label">🎯 Didi Agulhada</div>
        <div class="card-value c-gray" id="c-didi">–</div>
        <div class="card-sub" id="c-didi-sub">Welles Wilder 3/8/20</div>
    </div>
    <div class="card" id="card-status-el">
        <div class="card-glow" id="status-glow" style="background:#3d444d"></div>
        <div class="card-label">🤖 Status</div>
        <div class="card-value c-gray" id="c-status">CONECTANDO</div>
        <div class="card-sub" id="c-status-sub">–</div>
    </div>
    <div class="card">
        <div class="card-glow" id="pnl-glow" style="background:#21262d"></div>
        <div class="card-label">💼 P&amp;L / Sinal</div>
        <div class="card-value c-gray" id="c-pnl">–</div>
        <div class="card-sub" id="c-pnl-sub">Sem posição</div>
    </div>
</div>

<!-- ── CONDITIONS STRIP ────────────────────────────────────────────────────── -->
<div class="cond-strip">
    <span class="strip-lbl">COMPRA:</span>
    <div class="pill fail" id="pill1">⬜ Supertrend Bullish</div>
    <div class="pill fail" id="pill2">⬜ Preço &gt; EMA50</div>
    <div class="pill fail" id="pill3">⬜ Agulhada ↑</div>
    <div class="pill fail" id="pill4">⬜ Volume OK</div>
    <span class="strip-sep">│</span>
    <span class="strip-lbl" style="color:#f85149">VENDA:</span>
    <div class="pill pill-sell fail" id="pills1">⬜ ST Bearish</div>
    <div class="pill pill-sell fail" id="pills2">⬜ Agulhada ↓</div>
    <div id="strip-cnt" class="sc-low">0/4</div>
</div>

<!-- ── CHARTS ───────────────────────────────────────────────────────────────── -->
<div class="charts-wrap">

    <div class="chart-box" id="main-box">
        <div id="main-loading">⏳ Carregando gráfico...</div>

        <!-- Botões de navegação vertical -->
        <div id="chart-nav">
            <button onclick="scrollPrice(-1)" title="Rolar para CIMA  (ou Shift + Scroll ↑  ou tecla ↑)">▲</button>
            <button class="btn-fit" onclick="fitChart()" title="Ajustar à tela — ver todos os candles  (ou tecla F)">⊙</button>
            <button onclick="scrollPrice(1)"  title="Rolar para BAIXO  (ou Shift + Scroll ↓  ou tecla ↓)">▼</button>
            <div class="btn-tip">Shift<br>+Scroll</div>
        </div>

        <div class="chart-label">
            BTC/USDT · 15m &nbsp;
            <span class="leg">
                <span style="color:#fb923c">■</span> EMA50 &nbsp;
                <span style="color:#c084fc">■</span> SMA200 &nbsp;
                <span style="color:#f0abfc">■</span> VWAP &nbsp;
                <span style="color:#26a69a">■</span>/<span style="color:#f85149">■</span> Supertrend
            </span>
        </div>
        <div class="chart-inner" id="main-inner"></div>
    </div>

    <div class="chart-box" id="didi-box">
        <div class="chart-label">
            DIDI INDEX WDO Master · Welles Wilder (3/8/20) — Faixa Branca ±0.02% &nbsp;
            <span class="leg">
                <span style="color:#3b82f6">■</span> Linha3 Curta &nbsp;
                <span style="color:#fbbf24">─</span> Linha20 Longa &nbsp;
                <span style="color:#fff;opacity:.5">▓</span> Faixa Branca
            </span>
        </div>
        <div class="chart-inner" id="didi-inner"></div>
    </div>

</div>

<!-- ── BOTTOM ────────────────────────────────────────────────────────────────── -->
<div class="bottom-row">

    <!-- Indicadores ao Vivo -->
    <div class="panel">
        <div class="panel-title">
            <span>📊 Indicadores ao Vivo</span>
            <span id="ind-sig" style="font-size:.65rem;font-weight:700"></span>
        </div>
        <div id="ind-body"><div class="no-trades">Aguardando dados...</div></div>
    </div>

    <!-- Log de Operações -->
    <div class="panel">
        <div class="panel-title">
            <span>📋 Log de Operações</span>
            <span id="trade-count" style="color:#8b949e">0 trades</span>
        </div>
        <div id="trade-log">
            <div class="no-trades">Nenhuma operação ainda.<br>O robô age quando as 4 condições estiverem ativas.</div>
        </div>
    </div>

</div>
<div id="toast"></div>

<!-- ── SCRIPT ──────────────────────────────────────────────────────────────── -->
<script>
// ── Globals ──────────────────────────────────────────────────────────────────
let mainChart, candleSeries, stBullS, stBearS, ema50S, sma200S, vwapS, volS;
let didiChart, didiShortS, didiLongS;
let syncing = false;
let prevPosition = null, prevTradeCount = 0;

const TZ = new Date().getTimezoneOffset() * 60;
const lt  = t => t - TZ;

// ── Init Charts ───────────────────────────────────────────────────────────────
function initCharts() {
    const mBox = document.getElementById('main-box');
    const dBox = document.getElementById('didi-box');

    const base = {
        layout:    { backgroundColor: '#161b22', textColor: '#c9d1d9' },
        grid:      { vertLines: { color: '#1c2128' }, horzLines: { color: '#1c2128' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { autoScale: true, borderColor: '#21262d' },
        handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true },
        handleScale:  { mouseWheel: true, pinch: true, axisPressedMouseMove: { time: true, price: true } }
    };

    // ── Gráfico Principal ─────────────────────────────────────────────────
    mainChart = LightweightCharts.createChart(document.getElementById('main-inner'), {
        ...base, width: mBox.clientWidth, height: mBox.clientHeight,
        timeScale: { visible: false }
    });

    volS = mainChart.addHistogramSeries({
        color: '#26a69a', priceFormat: { type: 'volume' }, overlay: true,
        scaleMargins: { top: 0.82, bottom: 0 }
    });
    candleSeries = mainChart.addCandlestickSeries({
        upColor: '#26a69a', downColor: '#ef5350',
        borderVisible: false, wickUpColor: '#26a69a', wickDownColor: '#ef5350'
    });
    // SMA200 (branco/roxo claro — MMS 200 do Pine Script)
    sma200S = mainChart.addLineSeries({ color: '#c084fc', lineWidth: 2, title: 'SMA200', priceLineVisible: false, lastValueVisible: true });
    // EMA50 (laranja — MME 50 do Pine Script)
    ema50S  = mainChart.addLineSeries({ color: '#fb923c', lineWidth: 2, title: 'EMA50',  priceLineVisible: false, lastValueVisible: true });
    // VWAP (magenta — do Pine Script color.rgb(255,0,255))
    vwapS   = mainChart.addLineSeries({ color: '#f0abfc', lineWidth: 2, title: 'VWAP', lineStyle: 0, priceLineVisible: false, lastValueVisible: true });
    // Supertrend
    stBullS = mainChart.addLineSeries({ color: '#26a69a', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    stBearS = mainChart.addLineSeries({ color: '#f85149', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });

    // ── Didi Index ────────────────────────────────────────────────────────
    didiChart = LightweightCharts.createChart(document.getElementById('didi-inner'), {
        ...base, width: dBox.clientWidth, height: dBox.clientHeight,
        timeScale: { visible: true, timeVisible: true, secondsVisible: false, borderColor: '#21262d' }
    });

    // Linha3 como histograma colorido (azul quando > 0, vermelho quando < 0)
    didiShortS = didiChart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: true });

    // Linha20 como linha amarela
    didiLongS = didiChart.addLineSeries({
        color: '#fbbf24', lineWidth: 2, title: 'Longa',
        priceLineVisible: false, lastValueVisible: true
    });

    // ── Faixa Branca: linhas em ±0.02 (do margem_visual do Pine Script) ───
    didiShortS.createPriceLine({ price:  0.02, color: 'rgba(255,255,255,.35)', lineWidth: 1, lineStyle: 0, axisLabelVisible: true, title: 'FB+' });
    didiShortS.createPriceLine({ price: -0.02, color: 'rgba(255,255,255,.35)', lineWidth: 1, lineStyle: 0, axisLabelVisible: true, title: 'FB-' });
    // Linha zero (eixo)
    didiShortS.createPriceLine({ price:  0,    color: '#484f58',               lineWidth: 1, lineStyle: 2, axisLabelVisible: false });

    // ── Sincronização ─────────────────────────────────────────────────────
    function sync(src) {
        if (syncing) return; syncing = true;
        const r = src.timeScale().getVisibleLogicalRange();
        if (r) [mainChart, didiChart].forEach(c => { if (c !== src) c.timeScale().setVisibleLogicalRange(r); });
        syncing = false;
    }
    mainChart.timeScale().subscribeVisibleLogicalRangeChange(() => sync(mainChart));
    didiChart.timeScale().subscribeVisibleLogicalRangeChange(() => sync(didiChart));

    window.addEventListener('resize', () => {
        mainChart.resize(mBox.clientWidth, mBox.clientHeight);
        didiChart.resize(dBox.clientWidth, dBox.clientHeight);
    });
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(html, color) {
    const t = document.getElementById('toast');
    t.innerHTML = html; t.style.borderColor = color; t.style.color = color;
    t.classList.add('show'); clearTimeout(t._t);
    t._t = setTimeout(() => t.classList.remove('show'), 6000);
}

// ── Cards ─────────────────────────────────────────────────────────────────────
function updateCards(d) {
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString('pt-BR');
    const price = d.current_price || 0;
    const c     = d.conditions   || {};

    // Preço + VWAP
    document.getElementById('c-price').textContent =
        '$' + price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (c.vwap_val != null) {
        const vd = ((price - c.vwap_val) / c.vwap_val * 100).toFixed(2);
        document.getElementById('c-price-sub').textContent =
            'VWAP $' + Math.round(c.vwap_val).toLocaleString('en-US') +
            ' (' + (vd >= 0 ? '+' : '') + vd + '%)';
    }

    // Supertrend
    const stEl = document.getElementById('c-st'), stGl = document.getElementById('st-glow');
    if (c.st_bullish !== undefined) {
        stEl.textContent = c.st_bullish ? 'BULLISH' : 'BEARISH';
        stEl.className   = c.st_bullish ? 'card-value c-green' : 'card-value c-red';
        stGl.style.background = c.st_bullish ? '#7ee787' : '#f85149';
        document.getElementById('c-st-sub').textContent = c.st_bullish ? '🟢 Suporte ATR' : '🔴 Resistência ATR';
    }

    // EMA50
    const eEl = document.getElementById('c-ema'), eGl = document.getElementById('ema-glow');
    if (c.ema50_val != null) {
        const pd2 = ((price - c.ema50_val) / c.ema50_val * 100).toFixed(2);
        const above = price > c.ema50_val;
        eEl.textContent = above ? '↗ ACIMA' : '↘ ABAIXO';
        eEl.className   = above ? 'card-value c-green' : 'card-value c-red';
        eGl.style.background = above ? '#fb923c' : '#f85149';
        document.getElementById('c-ema-sub').textContent =
            '$' + Math.round(c.ema50_val).toLocaleString('en-US') +
            ' (' + (pd2 >= 0 ? '+' : '') + pd2 + '%)';
    }

    // Didi Agulhada
    const dEl = document.getElementById('c-didi'), dGl = document.getElementById('didi-glow');
    const ds = c.didi_short_val, dl = c.didi_long_val;
    if (ds != null) {
        const buyState  = ds > dl && ds > 0;
        const sellState = ds < dl && ds < 0;
        const fb = Math.abs(ds) <= 0.02 && dl != null && Math.abs(dl) <= 0.02;
        if (fb) {
            dEl.textContent = '⚡ SETUP';
            dEl.className   = 'card-value c-white blink';
            dGl.style.background = 'rgba(255,255,255,.5)';
            document.getElementById('c-didi-sub').textContent = 'Faixa Branca — Agulhada iminente!';
        } else if (buyState) {
            dEl.textContent = '🔵 COMPRA';
            dEl.className   = 'card-value c-blue';
            dGl.style.background = '#3b82f6';
            document.getElementById('c-didi-sub').textContent = 'L3 +' + ds.toFixed(3) + '% acima L20';
        } else if (sellState) {
            dEl.textContent = '🟡 VENDA';
            dEl.className   = 'card-value c-yellow';
            dGl.style.background = '#fbbf24';
            document.getElementById('c-didi-sub').textContent = 'L3 ' + ds.toFixed(3) + '% abaixo L20';
        } else {
            dEl.textContent = 'NEUTRO';
            dEl.className   = 'card-value c-gray';
            dGl.style.background = '#3d444d';
            document.getElementById('c-didi-sub').textContent =
                'L3 ' + (ds >= 0 ? '+' : '') + ds.toFixed(3) + '%';
        }
    }

    // Status
    const pos = d.position;
    const sEl = document.getElementById('c-status'), sGl = document.getElementById('status-glow');
    if (pos === 'buy') {
        sEl.textContent = 'COMPRADO'; sEl.className = 'card-value c-green';
        sGl.style.background = '#7ee787';
        document.getElementById('c-status-sub').textContent = '📡 Monitorando TP/SL';
    } else {
        sEl.textContent = 'AGUARDANDO'; sEl.className = 'card-value c-gray';
        sGl.style.background = '#3d444d';
        document.getElementById('c-status-sub').textContent = '🔍 Buscando agulhada';
    }
    if (prevPosition !== null && prevPosition !== pos) {
        const card = document.getElementById('card-status-el');
        card.classList.remove('flash'); void card.offsetWidth; card.classList.add('flash');
        if (pos === 'buy') showToast('🔵 ROBÔ ENTROU EM POSIÇÃO<br>Compra @ $' + price.toLocaleString('en-US', { minimumFractionDigits: 2 }), '#3b82f6');
        else               showToast('🟡 POSIÇÃO FECHADA<br>Venda @ $' + price.toLocaleString('en-US', { minimumFractionDigits: 2 }), '#fbbf24');
    }
    prevPosition = pos;

    // P&L
    const entry = d.entry_price || 0;
    const pEl = document.getElementById('c-pnl'), pGl = document.getElementById('pnl-glow');
    if (pos === 'buy' && entry > 0) {
        const pct = (price - entry) / entry * 100;
        pEl.textContent = (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%';
        pEl.className   = pct >= 0 ? 'card-value c-green' : 'card-value c-red';
        pGl.style.background = pct >= 0 ? '#7ee787' : '#f85149';
        const tp = entry * 1.03, sl = entry * 0.98;
        document.getElementById('c-pnl-sub').textContent =
            'TP +' + ((tp - price) / price * 100).toFixed(2) + '% · SL -' + ((price - sl) / price * 100).toFixed(2) + '%';
    } else {
        const met = [c.st_bullish, c.ema50_bull, c.didi_agulhada_buy, c.volume_ok].filter(Boolean).length;
        pEl.textContent = met + '/4';
        pEl.className   = met === 4 ? 'card-value c-green' : met >= 2 ? 'card-value c-yellow' : 'card-value c-gray';
        pGl.style.background = met === 4 ? '#7ee787' : '#21262d';
        document.getElementById('c-pnl-sub').textContent = met === 4 ? '🚀 Sinal ativo!' : met + ' de 4 ativas';
    }
}

// ── Conditions Strip ──────────────────────────────────────────────────────────
function updateStrip(d) {
    const c   = d.conditions || {};
    const met = [c.st_bullish, c.ema50_bull, c.didi_agulhada_buy, c.volume_ok].filter(Boolean).length;
    const pills = [
        { id: 'pill1', ok: c.st_bullish,         label: 'Supertrend Bullish' },
        { id: 'pill2', ok: c.ema50_bull,          label: 'Preço > EMA50' },
        { id: 'pill3', ok: c.didi_agulhada_buy,   label: 'Agulhada ↑' },
        { id: 'pill4', ok: c.volume_ok,           label: 'Volume OK' },
    ];
    pills.forEach(p => {
        const el = document.getElementById(p.id);
        el.textContent = (p.ok ? '✅' : '⬜') + ' ' + p.label;
        el.className   = 'pill ' + (p.ok ? 'ok' : 'fail');
    });
    const sp1 = !c.st_bullish, sp2 = c.didi_agulhada_sell;
    document.getElementById('pills1').textContent = (sp1 ? '🔴' : '⬜') + ' ST Bearish';
    document.getElementById('pills2').textContent = (sp2 ? '🔴' : '⬜') + ' Agulhada ↓';
    document.getElementById('pills1').className = 'pill pill-sell ' + (sp1 ? 'ok' : 'fail');
    document.getElementById('pills2').className = 'pill pill-sell ' + (sp2 ? 'ok' : 'fail');

    const cnt = document.getElementById('strip-cnt');
    cnt.textContent = met + '/4';
    cnt.className   = met === 4 ? 'sc-ok' : met >= 2 ? 'sc-mid' : 'sc-low';
}

// ── Indicators Panel ──────────────────────────────────────────────────────────
function updateIndicators(d) {
    const c     = d.conditions || {};
    const price = d.current_price || 0;
    const met   = [c.st_bullish, c.ema50_bull, c.didi_agulhada_buy, c.volume_ok].filter(Boolean).length;

    const sigEl = document.getElementById('ind-sig');
    if (met === 4) { sigEl.textContent = '🚀 SINAL ATIVO — PODE COMPRAR!'; sigEl.style.color = '#7ee787'; }
    else if (c.didi_agulhada_sell || !c.st_bullish) { sigEl.textContent = '⚠️ SINAL DE VENDA'; sigEl.style.color = '#f85149'; }
    else if (c.faixa_branca) { sigEl.textContent = '⚡ Faixa Branca Ativa!'; sigEl.style.color = '#fff'; }
    else { sigEl.textContent = met + '/4 condições'; sigEl.style.color = '#8b949e'; }

    const fmt = v => v != null ? '$' + Math.round(v).toLocaleString('en-US') : '–';
    const pdist = (v) => {
        if (!v || !price) return { t: '–', c: 'tag-neu' };
        const p = ((price - v) / v * 100);
        return { t: (p >= 0 ? '+' : '') + p.toFixed(2) + '%', c: p >= 0 ? 'tag-up' : 'tag-dn' };
    };
    const e50  = pdist(c.ema50_val);
    const s200 = pdist(c.sma200_val);
    const vwp  = pdist(c.vwap_val);
    const ds   = c.didi_short_val, dl = c.didi_long_val, vr = c.volume_ratio || 0;
    const fb   = c.faixa_branca;

    document.getElementById('ind-body').innerHTML = `
        <div class="ind-section">
            <div class="ind-hdr">📈 Médias (do Pine Script)</div>
            <div class="ind-row">
                <span class="ind-name" style="color:#fb923c">EMA 50</span>
                <span class="ind-val">${fmt(c.ema50_val)}</span>
                <span class="ind-tag ${e50.c}">${e50.t}</span>
            </div>
            <div class="ind-row">
                <span class="ind-name" style="color:#c084fc">SMA 200</span>
                <span class="ind-val">${c.sma200_val != null ? fmt(c.sma200_val) : '– (insuf.)'}</span>
                <span class="ind-tag ${s200.c}">${s200.t}</span>
            </div>
            <div class="ind-row">
                <span class="ind-name" style="color:#f0abfc">VWAP</span>
                <span class="ind-val">${fmt(c.vwap_val)}</span>
                <span class="ind-tag ${vwp.c}">${vwp.t}</span>
            </div>
        </div>
        <div class="ind-section">
            <div class="ind-hdr">🎯 Didi Index WDO Master</div>
            <div class="faixa-badge ${fb ? 'fb-setup' : 'fb-normal'}">
                ${fb ? '⚡ FAIXA BRANCA ATIVA — Agulhada iminente!' : '▓ Faixa Branca (±0.02%): aguardando compressão'}
            </div>
            <div class="ind-row" style="margin-top:2px">
                <span class="ind-name" style="color:#3b82f6">L3 Curta</span>
                <span class="ind-val ${ds != null && ds > 0 ? 'c-green' : 'c-red'}">${ds != null ? (ds >= 0 ? '+' : '') + ds.toFixed(4) + '%' : '–'}</span>
                <span class="ind-tag ${ds != null && ds > dl ? 'tag-up' : 'tag-dn'}">${ds != null && ds > dl ? 'Acima L20' : 'Abaixo L20'}</span>
            </div>
            <div class="ind-row">
                <span class="ind-name" style="color:#fbbf24">L20 Longa</span>
                <span class="ind-val c-yellow">${dl != null ? (dl >= 0 ? '+' : '') + dl.toFixed(4) + '%' : '–'}</span>
                <span class="ind-tag tag-neu">referência</span>
            </div>
        </div>
        <div class="ind-section" style="margin-bottom:0">
            <div class="ind-hdr">📦 Volume &amp; Supertrend</div>
            <div class="ind-row">
                <span class="ind-name">Volume</span>
                <span class="ind-val ${vr >= 1.2 ? 'c-green' : 'c-gray'}">${vr.toFixed(2)}× média</span>
                <span class="ind-tag ${vr >= 1.2 ? 'tag-up' : 'tag-neu'}">${vr >= 1.2 ? '✅ OK' : (1.2 - vr).toFixed(2) + '× falta'}</span>
            </div>
            <div class="ind-row">
                <span class="ind-name">Supertrend</span>
                <span class="ind-val ${c.st_bullish ? 'c-green' : 'c-red'}">${c.st_line != null ? fmt(c.st_line) : '–'}</span>
                <span class="ind-tag ${c.st_bullish ? 'tag-up' : 'tag-dn'}">${c.st_bullish ? 'BULLISH' : 'BEARISH'}</span>
            </div>
        </div>`;
}

// ── Trade Log ─────────────────────────────────────────────────────────────────
function updateTradeLog(d) {
    const trades = (d.trade_log || []).slice().reverse();
    document.getElementById('trade-count').textContent = trades.length + ' trade' + (trades.length !== 1 ? 's' : '');
    if (trades.length > prevTradeCount && prevTradeCount > 0) {
        const t = trades[0];
        const p = parseFloat(t.price).toLocaleString('en-US', { minimumFractionDigits: 2 });
        if (t.type === 'buy') showToast('🔵 AGULHADA DE COMPRA!<br>Entrada @ $' + p, '#3b82f6');
        else { const s = (t.pnl_pct || 0) >= 0 ? '+' : ''; showToast('🟡 SAÍDA EXECUTADA<br>$' + p + '&nbsp; P&L: ' + s + (t.pnl_pct || 0).toFixed(2) + '%', '#fbbf24'); }
    }
    prevTradeCount = trades.length;
    const body = document.getElementById('trade-log');
    if (!trades.length) {
        body.innerHTML = '<div class="no-trades">Nenhuma operação ainda.<br>Aguardando agulhada de compra com ST bullish.</div>';
        return;
    }
    body.innerHTML = trades.slice(0, 8).map(t => {
        const pnl = t.pnl_pct !== undefined
            ? `<span class="t-pnl ${t.pnl_pct >= 0 ? 'c-green' : 'c-red'}">${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%</span>` : '';
        return `<div class="trade-row">
            <span class="trade-badge ${t.type === 'buy' ? 'b-buy' : 'b-sell'}">${t.type === 'buy' ? '▲ COMPRA' : '▼ VENDA'}</span>
            <span class="t-price">$${parseFloat(t.price).toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            ${pnl}<span class="t-time">${t.datetime || ''}</span></div>`;
    }).join('');
}

// ── Chart Update ──────────────────────────────────────────────────────────────
function updateChart(d) {
    if (!d.history_candles || !d.history_candles.length) return;
    document.getElementById('main-loading').style.display = 'none';

    const cs = d.history_candles.map(c => ({ ...c, time: lt(c.time) }));
    const flt = key => cs.filter(c => c[key] != null).map(c => ({ time: c.time, value: c[key] }));

    // Candles + Volume
    candleSeries.setData(cs);
    volS.setData(cs.map(c => ({
        time: c.time, value: c.volume || 0,
        color: c.close >= c.open ? 'rgba(38,166,154,.28)' : 'rgba(239,83,80,.28)'
    })));

    // Médias do Pine Script
    if (flt('sma200').length) sma200S.setData(flt('sma200'));
    if (flt('ema50').length)  ema50S.setData(flt('ema50'));

    // VWAP (linha quebrada por dia — omite NaN)
    if (flt('vwap').length) vwapS.setData(flt('vwap'));

    // Supertrend
    const stBull = cs.filter(c => c.st_dir === 1  && c.st_line != null).map(c => ({ time: c.time, value: c.st_line }));
    const stBear = cs.filter(c => c.st_dir === -1 && c.st_line != null).map(c => ({ time: c.time, value: c.st_line }));
    if (stBull.length) stBullS.setData(stBull);
    if (stBear.length) stBearS.setData(stBear);

    // Didi Index
    // Linha3 (curta): histograma azul quando > 0, vermelho quando < 0
    const didiShort = cs.filter(c => c.didi_short != null).map(c => ({
        time: c.time, value: c.didi_short,
        color: c.didi_short >= 0 ? 'rgba(59,130,246,.85)' : 'rgba(248,81,73,.7)'
    }));
    // Linha20 (longa): linha amarela
    const didiLong = cs.filter(c => c.didi_long != null).map(c => ({ time: c.time, value: c.didi_long }));
    if (didiShort.length) didiShortS.setData(didiShort);
    if (didiLong.length)  didiLongS.setData(didiLong);

    // ── Marcadores de Agulhada no gráfico Didi (azul ▲ compra, amarelo ▼ venda)
    const didiMarkers = cs
        .filter(c => c.didi_signal && c.didi_signal !== 0)
        .map(c => ({
            time:     c.time,
            position: c.didi_signal === 1 ? 'belowBar' : 'aboveBar',
            color:    c.didi_signal === 1 ? '#3b82f6'  : '#fbbf24',
            shape:    c.didi_signal === 1 ? 'arrowUp'  : 'arrowDown',
            text:     c.didi_signal === 1 ? '▲ COMPRA' : '▼ VENDA'
        }))
        .sort((a, b) => a.time - b.time);
    if (didiMarkers.length) didiShortS.setMarkers(didiMarkers);

    // ── Marcadores de ordens no gráfico principal
    const markers = (d.trade_log || [])
        .filter(t => t.time)
        .map(t => ({
            time:     lt(t.time),
            position: t.type === 'buy' ? 'belowBar' : 'aboveBar',
            color:    t.type === 'buy' ? '#3b82f6'  : '#fbbf24',
            shape:    t.type === 'buy' ? 'arrowUp'  : 'arrowDown',
            text:     t.type === 'buy' ? '▲ COMPRA' : '▼ VENDA'
        }))
        .sort((a, b) => a.time - b.time);
    if (markers.length) candleSeries.setMarkers(markers);
}

// ── Main Loop ─────────────────────────────────────────────────────────────────
async function fetchAndUpdate() {
    try {
        const res  = await fetch('/api/data');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        if (!data || !data.current_price) return;
        updateCards(data);
        updateStrip(data);
        updateIndicators(data);
        updateTradeLog(data);
        updateChart(data);
    } catch (e) {
        console.error('Erro:', e);
        const el = document.getElementById('main-loading');
        el.style.display = 'block'; el.textContent = '❌ ' + e.message;
    }
}

initCharts();
fetchAndUpdate();
setInterval(fetchAndUpdate, 3000);

// ── Navegação Vertical de Preço ───────────────────────────────────────────────

// Ajusta o gráfico para mostrar todos os candles e restaura autoScale
function fitChart() {
    mainChart.applyOptions({ rightPriceScale: { autoScale: true } });
    mainChart.timeScale().fitContent();
    didiChart.applyOptions({ rightPriceScale: { autoScale: true } });
    didiChart.timeScale().fitContent();
}

// Rola o eixo de preço: direction -1 = cima, +1 = baixo
function scrollPrice(direction) {
    // Desativa autoScale para manter posição manual
    mainChart.applyOptions({ rightPriceScale: { autoScale: false } });

    const el     = document.getElementById('main-inner');
    const canvas = el.querySelector('canvas');
    if (!canvas) return;

    const rect    = canvas.getBoundingClientRect();
    // O eixo de preço fica nos últimos ~58px à direita do canvas
    const axisX   = rect.right - 38;
    const centerY = rect.top + rect.height / 2;
    const pixels  = 55 * direction;   // pixels de arrasto: -55 sobe, +55 desce

    // Simula um arrasto no eixo de preço (mousedown → mousemove × 4 → mouseup)
    const opts = (y) => ({ bubbles: true, cancelable: true, button: 0, clientX: axisX, clientY: y });
    canvas.dispatchEvent(new MouseEvent('mousedown', opts(centerY)));
    canvas.dispatchEvent(new MouseEvent('mousemove', opts(centerY + pixels * 0.25)));
    canvas.dispatchEvent(new MouseEvent('mousemove', opts(centerY + pixels * 0.5)));
    canvas.dispatchEvent(new MouseEvent('mousemove', opts(centerY + pixels * 0.75)));
    canvas.dispatchEvent(new MouseEvent('mousemove', opts(centerY + pixels)));
    canvas.dispatchEvent(new MouseEvent('mouseup',   opts(centerY + pixels)));
}

// ── Shift + Roda do Mouse = rolar preço vertical ──────────────────────────────
document.getElementById('main-box').addEventListener('wheel', function(e) {
    if (e.shiftKey) {
        e.preventDefault();
        e.stopPropagation();
        scrollPrice(e.deltaY > 0 ? 1 : -1);
    }
}, { passive: false });

// ── Teclas de atalho (quando o mouse está sobre o gráfico) ───────────────────
let _overChart = false;
document.getElementById('main-box').addEventListener('mouseenter', () => _overChart = true);
document.getElementById('main-box').addEventListener('mouseleave', () => _overChart = false);
document.addEventListener('keydown', function(e) {
    if (!_overChart) return;
    if (e.key === 'ArrowUp')             { e.preventDefault(); scrollPrice(-1); }
    if (e.key === 'ArrowDown')           { e.preventDefault(); scrollPrice(1);  }
    if (e.key === 'f' || e.key === 'F')  { e.preventDefault(); fitChart();      }
});
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
def _f(val):
    try:
        v = float(val)
        return None if (v != v) else v
    except Exception:
        return None


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def handle_error(self, *_): pass

    def do_GET(self):

        if self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()

            candles_list  = []
            current_price = 0
            conditions    = {}

            try:
                current_price = float(exchange.fetch_ticker(SYMBOL)['last'])
                # 250 candles: SMA200 precisa de 200+ candles
                ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=250)
                df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                df = apply_indicators(df)

                last = df.iloc[-1]

                ema50_v  = _f(last['ema50'])
                sma200_v = _f(last['sma200'])
                vwap_v   = _f(last['vwap'])
                ds_v     = _f(last['didi_short'])
                dl_v     = _f(last['didi_long'])
                st_dir_v = _f(last['st_dir'])
                st_line_v= _f(last['st_line'])
                vol_mean = _f(last['vol_mean']) or 0
                vol_cur  = float(last['volume'])

                st_bull      = st_dir_v == 1.0 if st_dir_v is not None else False
                ema_bull     = (float(last['close']) > ema50_v) if ema50_v else False
                didi_buy     = (ds_v > dl_v and ds_v > 0) if (ds_v is not None and dl_v is not None) else False
                didi_sell    = (ds_v < dl_v and ds_v < 0) if (ds_v is not None and dl_v is not None) else False
                vol_ok       = (vol_cur >= vol_mean * 1.2) if vol_mean > 0 else False
                vol_ratio    = round(vol_cur / vol_mean, 3) if vol_mean > 0 else 0
                faixa_branca = (abs(ds_v) <= 0.02 and abs(dl_v) <= 0.02) if (ds_v is not None and dl_v is not None) else False

                conditions = {
                    "st_bullish":         st_bull,
                    "ema50_bull":         ema_bull,
                    "didi_agulhada_buy":  didi_buy,
                    "didi_agulhada_sell": didi_sell,
                    "volume_ok":          vol_ok,
                    "faixa_branca":       faixa_branca,
                    "volume_ratio":       vol_ratio,
                    "didi_short_val":     ds_v,
                    "didi_long_val":      dl_v,
                    "ema50_val":          ema50_v,
                    "sma200_val":         sma200_v,
                    "vwap_val":           vwap_v,
                    "st_line":            st_line_v,
                }

                for _, r in df.iterrows():
                    candles_list.append({
                        "time":        int(r['time'] / 1000),
                        "open":        float(r['open']),
                        "high":        float(r['high']),
                        "low":         float(r['low']),
                        "close":       float(r['close']),
                        "volume":      float(r['volume']),
                        "st_dir":      _f(r['st_dir']),
                        "st_line":     _f(r['st_line']),
                        "ema50":       _f(r['ema50']),
                        "sma200":      _f(r['sma200']),
                        "vwap":        _f(r['vwap']),
                        "didi_short":  _f(r['didi_short']),
                        "didi_long":   _f(r['didi_long']),
                        "didi_signal": int(r['didi_signal']) if not pd.isna(r['didi_signal']) else 0,
                    })

            except Exception as e:
                print(f"Aviso API: {e}")

            position_status = None
            entry_price     = 0.0
            trade_log       = []

            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, 'r') as f:
                        bj = json.load(f)
                        position_status = bj.get("position")
                        entry_price     = bj.get("entry_price", 0.0)
                        trade_log       = bj.get("trade_log", [])
                        if bj.get("current_price"):
                            current_price = bj["current_price"]
                except Exception:
                    pass

            self.wfile.write(json.dumps({
                "current_price":   current_price,
                "position":        position_status,
                "entry_price":     entry_price,
                "conditions":      conditions,
                "history_candles": candles_list,
                "trade_log":       trade_log,
            }).encode())

        elif self.path in ('/', '/index.html'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode('utf-8'))


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'w') as f:
            json.dump({"position": None, "entry_price": 0.0,
                       "last_candle_time": 0, "trade_log": []}, f)

    server = HTTPServer(('0.0.0.0', 8080), DashboardHandler)
    print("=" * 60)
    print("✅  Dashboard BTC — WDO Master Didi + Supertrend (15m)")
    print("👉  Acesse: http://localhost:8080")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Dashboard encerrado.")
