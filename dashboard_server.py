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
            background: #0d1117;
            color: #c9d1d9;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* ── HEADER ─────────────────────────────────────────── */
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px 20px;
            background: #161b22;
            border-bottom: 1px solid #30363d;
            flex-shrink: 0;
        }
        .header-left { display: flex; align-items: center; gap: 10px; }
        .header h1   { font-size: .92rem; font-weight: 600; color: #f0f6fc; }
        .live-badge {
            display: flex; align-items: center; gap: 5px;
            background: rgba(126,231,135,.1);
            border: 1px solid rgba(126,231,135,.3);
            border-radius: 20px; padding: 3px 10px;
            font-size: .68rem; color: #7ee787; font-weight: 600;
        }
        .live-dot { width: 6px; height: 6px; border-radius: 50%; background: #7ee787; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.2} }
        .header-right { font-size: .7rem; color: #8b949e; }

        /* ── CARDS ──────────────────────────────────────────── */
        .cards {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px; padding: 8px 20px;
            flex-shrink: 0;
        }
        .card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 10px 13px;
            position: relative;
            overflow: hidden;
            transition: border-color .4s;
        }
        .card-glow { position: absolute; top: 0; left: 0; right: 0; height: 2px; border-radius: 8px 8px 0 0; transition: background .4s; }
        .card-label { font-size: .6rem; color: #8b949e; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 3px; }
        .card-value { font-size: 1.35rem; font-weight: 700; line-height: 1.1; }
        .card-sub   { font-size: .65rem; color: #8b949e; margin-top: 3px; }

        /* ── CHART ──────────────────────────────────────────── */
        .chart-wrap {
            flex: 1; padding: 0 20px;
            min-height: 0;
            display: flex; flex-direction: column;
        }
        #chart-box {
            flex: 1;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            overflow: hidden;
            position: relative;
        }
        #chart-inner  { width: 100%; height: 100%; }
        #chart-loading {
            position: absolute; top: 50%; left: 50%;
            transform: translate(-50%,-50%);
            color: #8b949e; font-size: .82rem; text-align: center;
        }

        /* ── BOTTOM ─────────────────────────────────────────── */
        .bottom-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px; padding: 8px 20px 12px;
            flex-shrink: 0;
        }
        .panel {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 10px 13px;
        }
        .panel-title {
            font-size: .62rem; color: #8b949e;
            text-transform: uppercase; letter-spacing: .08em;
            margin-bottom: 8px;
            display: flex; align-items: center; justify-content: space-between;
        }

        /* ── CONDITIONS ─────────────────────────────────────── */
        .cond-item {
            display: flex; align-items: center; gap: 7px;
            padding: 4px 0; border-bottom: 1px solid #1c2128;
            font-size: .75rem;
        }
        .cond-item:last-of-type { border-bottom: none; }
        .cond-icon  { font-size: .85rem; width: 18px; text-align: center; }
        .cond-text  { flex: 1; }
        .cond-value { font-size: .67rem; color: #8b949e; flex-shrink: 0; }

        /* Progress bars */
        .prog-wrap { margin: 5px 0 1px; }
        .prog-header { display: flex; justify-content: space-between; font-size: .65rem; color: #8b949e; margin-bottom: 3px; }
        .prog-track  { height: 4px; background: #21262d; border-radius: 2px; overflow: hidden; }
        .prog-fill   { height: 100%; border-radius: 2px; transition: width .8s ease, background .5s ease; }

        /* Signal active box */
        .signal-box {
            display: none; text-align: center; padding: 5px 8px;
            border-radius: 6px; font-weight: 700; font-size: .75rem;
            margin-top: 6px; animation: sig-pulse 1s infinite;
        }
        @keyframes sig-pulse { 0%,100%{opacity:1} 50%{opacity:.55} }

        /* ── TRADE LOG ──────────────────────────────────────── */
        .trade-item {
            display: flex; align-items: center; gap: 7px;
            padding: 4px 0; border-bottom: 1px solid #1c2128;
            font-size: .74rem;
        }
        .trade-item:last-child { border-bottom: none; }
        .trade-badge {
            padding: 1px 6px; border-radius: 4px;
            font-size: .62rem; font-weight: 700;
            text-transform: uppercase; flex-shrink: 0;
        }
        .badge-buy  { background: rgba(38,166,154,.15); color: #26a69a; border: 1px solid rgba(38,166,154,.3); }
        .badge-sell { background: rgba(239,83,80,.15);  color: #ef5350; border: 1px solid rgba(239,83,80,.3); }
        .trade-price { font-weight: 600; color: #f0f6fc; }
        .trade-pnl   { margin-left: auto; font-weight: 600; flex-shrink: 0; }
        .trade-time  { color: #8b949e; font-size: .63rem; flex-shrink: 0; }
        .no-trades   { color: #8b949e; font-size: .75rem; text-align: center; padding: 10px; line-height: 1.5; }

        /* ── COLORS ─────────────────────────────────────────── */
        .c-blue   { color: #58a6ff; }
        .c-green  { color: #7ee787; }
        .c-red    { color: #f85149; }
        .c-yellow { color: #f1e05a; }
        .c-gray   { color: #8b949e; }

        /* ── TOAST ──────────────────────────────────────────── */
        #toast {
            position: fixed; top: 52px; right: 18px; z-index: 9999;
            background: #1c2128; border: 1px solid #30363d;
            border-radius: 10px; padding: 10px 15px;
            font-size: .8rem; font-weight: 600;
            box-shadow: 0 8px 32px rgba(0,0,0,.65);
            transform: translateX(120%);
            transition: transform .35s cubic-bezier(.175,.885,.32,1.275);
            max-width: 260px; line-height: 1.55;
        }
        #toast.show { transform: translateX(0); }

        /* Card flash on new trade */
        @keyframes card-flash {
            0%  { background: rgba(126,231,135,.2); border-color: #7ee787; }
            100%{ background: #161b22; border-color: #30363d; }
        }
        .card.flash { animation: card-flash 1.8s ease; }
    </style>
</head>
<body>

<!-- ══ HEADER ══════════════════════════════════════════════════════════ -->
<div class="header">
    <div class="header-left">
        <h1>🤖 Robô BTC/USDT</h1>
        <div class="live-badge"><div class="live-dot"></div>AO VIVO</div>
    </div>
    <div class="header-right">
        Atualizado: <span id="last-update">--:--:--</span>
        &nbsp;·&nbsp; Timeframe: 5m
        &nbsp;·&nbsp; TP +3% / SL -2%
    </div>
</div>

<!-- ══ CARDS ════════════════════════════════════════════════════════════ -->
<div class="cards">

    <!-- Preço -->
    <div class="card">
        <div class="card-glow" style="background: linear-gradient(90deg,#58a6ff,#1f6feb)"></div>
        <div class="card-label">💰 Preço BTC</div>
        <div class="card-value c-blue" id="card-price">$0.00</div>
        <div class="card-sub"  id="card-price-sub">SMA50: –</div>
    </div>

    <!-- RSI -->
    <div class="card" id="card-rsi-el">
        <div class="card-glow" id="rsi-glow" style="background:#f1e05a"></div>
        <div class="card-label">📊 RSI (14)</div>
        <div class="card-value c-yellow" id="card-rsi">0.00</div>
        <div class="card-sub"  id="card-rsi-zone">Zona: –</div>
    </div>

    <!-- Status -->
    <div class="card" id="card-status-el">
        <div class="card-glow" id="status-glow" style="background:#8b949e"></div>
        <div class="card-label">🤖 Status do Robô</div>
        <div class="card-value c-gray" id="card-status">CONECTANDO</div>
        <div class="card-sub"  id="card-status-sub">Aguardando dados...</div>
    </div>

    <!-- P&L -->
    <div class="card">
        <div class="card-glow" id="pnl-glow" style="background:#30363d"></div>
        <div class="card-label">💼 P&amp;L da Posição</div>
        <div class="card-value c-gray" id="card-pnl">–</div>
        <div class="card-sub"  id="card-pnl-sub">Sem posição aberta</div>
    </div>

    <!-- Gatilho -->
    <div class="card">
        <div class="card-glow" id="sig-glow" style="background:#30363d"></div>
        <div class="card-label">🎯 Gatilho de Compra</div>
        <div class="card-value c-gray" id="card-sig">0/4</div>
        <div class="card-sub"  id="card-sig-sub">condições ativas</div>
    </div>

</div>

<!-- ══ CHART ═════════════════════════════════════════════════════════════ -->
<div class="chart-wrap">
    <div id="chart-box">
        <div id="chart-inner"></div>
        <div id="chart-loading">⏳ Carregando gráfico da Binance...</div>
    </div>
</div>

<!-- ══ BOTTOM ════════════════════════════════════════════════════════════ -->
<div class="bottom-row">

    <!-- Condições -->
    <div class="panel">
        <div class="panel-title">
            <span>🎯 Gatilhos de Entrada — BUY</span>
            <span id="cond-count">0/4 ativas</span>
        </div>

        <div class="cond-item">
            <span class="cond-icon" id="c1">⬜</span>
            <span class="cond-text">Preço acima da SMA50</span>
            <span class="cond-value" id="c1h">–</span>
        </div>
        <div class="cond-item">
            <span class="cond-icon" id="c2">⬜</span>
            <span class="cond-text">SMA50 em tendência de alta</span>
            <span class="cond-value" id="c2h">–</span>
        </div>
        <div class="cond-item">
            <span class="cond-icon" id="c3">⬜</span>
            <span class="cond-text">RSI &lt; 40 <small>(zona de sobrevenda)</small></span>
            <span class="cond-value" id="c3h">RSI: –</span>
        </div>
        <div class="cond-item">
            <span class="cond-icon" id="c4">⬜</span>
            <span class="cond-text">Volume acima da média 20</span>
            <span class="cond-value" id="c4h">–</span>
        </div>

        <!-- RSI bar -->
        <div class="prog-wrap" style="margin-top:8px">
            <div class="prog-header">
                <span>RSI atual: <strong id="rsi-bar-val">–</strong></span>
                <span id="rsi-bar-hint" style="color:#8b949e">–</span>
            </div>
            <div class="prog-track">
                <div class="prog-fill" id="rsi-bar" style="width:50%;background:#f1e05a"></div>
            </div>
        </div>

        <!-- Volume bar -->
        <div class="prog-wrap">
            <div class="prog-header">
                <span>Volume: <strong id="vol-bar-val">–</strong></span>
                <span id="vol-bar-hint">vs média 20 candles</span>
            </div>
            <div class="prog-track">
                <div class="prog-fill" id="vol-bar" style="width:30%;background:#58a6ff"></div>
            </div>
        </div>

        <!-- Sell trigger bar -->
        <div class="prog-wrap">
            <div class="prog-header">
                <span style="color:#f85149">⚡ Gatilho VENDA: RSI &gt; 65</span>
                <span id="sell-bar-hint" style="color:#8b949e">–</span>
            </div>
            <div class="prog-track">
                <div class="prog-fill" id="sell-bar" style="width:0%;background:#f85149"></div>
            </div>
        </div>

        <!-- All conditions met box -->
        <div class="signal-box" id="signal-box"></div>
    </div>

    <!-- Log de operações -->
    <div class="panel">
        <div class="panel-title">
            <span>📋 Log de Operações</span>
            <span id="trade-count" style="color:#8b949e">0 trades</span>
        </div>
        <div id="trade-log">
            <div class="no-trades">
                Nenhuma operação registrada ainda.<br>
                O robô entra quando as 4 condições estiverem ativas.
            </div>
        </div>
    </div>

</div>

<!-- Toast -->
<div id="toast"></div>

<!-- ══ SCRIPT ═══════════════════════════════════════════════════════════ -->
<script>
let chart, candleSeries, smaSeries, volSeries;
let prevPosition = null;
let prevTradeCount = 0;

// ── Init chart ──────────────────────────────────────────────────────────
function initChart() {
    const inner = document.getElementById('chart-inner');
    const box   = document.getElementById('chart-box');

    chart = LightweightCharts.createChart(inner, {
        width:  box.clientWidth,
        height: box.clientHeight,
        layout: { backgroundColor: '#161b22', textColor: '#c9d1d9' },
        grid:   { vertLines: { color: '#1c2128' }, horzLines: { color: '#1c2128' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { autoScale: true },
        timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#30363d' }
    });

    // Volume (fundo, escala independente)
    volSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: { type: 'volume' },
        overlay: true,
        scaleMargins: { top: 0.82, bottom: 0 }
    });

    // Candlesticks
    candleSeries = chart.addCandlestickSeries({
        upColor: '#26a69a', downColor: '#ef5350',
        borderVisible: false,
        wickUpColor: '#26a69a', wickDownColor: '#ef5350'
    });

    // SMA50
    smaSeries = chart.addLineSeries({
        color: '#f1e05a', lineWidth: 2, title: 'SMA50',
        priceLineVisible: false, lastValueVisible: false
    });

    window.addEventListener('resize', () => chart.resize(box.clientWidth, box.clientHeight));
}

// ── Toast ───────────────────────────────────────────────────────────────
function showToast(html, color) {
    const t = document.getElementById('toast');
    t.innerHTML = html;
    t.style.borderColor = color;
    t.style.color = color;
    t.classList.add('show');
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove('show'), 6000);
}

// ── Cards ───────────────────────────────────────────────────────────────
function updateCards(d) {
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString('pt-BR');

    const price = d.current_price || 0;
    document.getElementById('card-price').textContent =
        '$' + price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (d.sma50) {
        const diff = ((price - d.sma50) / d.sma50 * 100).toFixed(2);
        document.getElementById('card-price-sub').textContent =
            'SMA50: $' + Math.round(d.sma50).toLocaleString('en-US') +
            ' (' + (diff >= 0 ? '+' : '') + diff + '%)';
    }

    // RSI
    const rsi = d.rsi || 0;
    const rsiEl   = document.getElementById('card-rsi');
    const rsiZone = document.getElementById('card-rsi-zone');
    const rsiGlow = document.getElementById('rsi-glow');
    rsiEl.textContent = rsi.toFixed(2);
    if      (rsi < 30) { rsiEl.className='card-value c-green'; rsiZone.textContent='🟢 Sobrevenda extrema';    rsiGlow.style.background='#7ee787'; }
    else if (rsi < 40) { rsiEl.className='card-value c-green'; rsiZone.textContent='🟢 Zona de compra (BUY)'; rsiGlow.style.background='#7ee787'; }
    else if (rsi < 55) { rsiEl.className='card-value c-yellow'; rsiZone.textContent='🟡 Neutro';               rsiGlow.style.background='#f1e05a'; }
    else if (rsi < 65) { rsiEl.className='card-value c-yellow'; rsiZone.textContent='🟡 Aquecido';             rsiGlow.style.background='#e8a200'; }
    else               { rsiEl.className='card-value c-red';    rsiZone.textContent='🔴 Sobrecomprado (SELL)'; rsiGlow.style.background='#f85149'; }

    // Status
    const pos     = d.position;
    const statEl  = document.getElementById('card-status');
    const statSub = document.getElementById('card-status-sub');
    const statGlow= document.getElementById('status-glow');
    if (pos === 'buy') {
        statEl.textContent  = 'COMPRADO';
        statEl.className    = 'card-value c-green';
        statGlow.style.background = '#7ee787';
        statSub.textContent = '📡 Monitorando TP +3% / SL -2%';
    } else {
        statEl.textContent  = 'AGUARDANDO';
        statEl.className    = 'card-value c-gray';
        statGlow.style.background = '#8b949e';
        statSub.textContent = '🔍 Buscando sinal de entrada';
    }

    // Flash + toast ao mudar de posição
    if (prevPosition !== null && prevPosition !== pos) {
        const card = document.getElementById('card-status-el');
        card.classList.remove('flash');
        void card.offsetWidth;
        card.classList.add('flash');
        if (pos === 'buy') {
            showToast('🟢 ROBÔ ENTROU EM POSIÇÃO<br>Compra @ $' +
                price.toLocaleString('en-US', { minimumFractionDigits: 2 }), '#7ee787');
        } else {
            showToast('🔴 POSIÇÃO FECHADA<br>Venda @ $' +
                price.toLocaleString('en-US', { minimumFractionDigits: 2 }), '#f85149');
        }
    }
    prevPosition = pos;

    // P&L
    const entry  = d.entry_price || 0;
    const pnlEl  = document.getElementById('card-pnl');
    const pnlSub = document.getElementById('card-pnl-sub');
    const pnlGlow= document.getElementById('pnl-glow');
    if (pos === 'buy' && entry > 0) {
        const pct  = (price - entry) / entry * 100;
        const sign = pct >= 0 ? '+' : '';
        pnlEl.textContent = sign + pct.toFixed(2) + '%';
        pnlEl.className   = pct >= 0 ? 'card-value c-green' : 'card-value c-red';
        pnlGlow.style.background = pct >= 0 ? '#7ee787' : '#f85149';
        const tp  = entry * 1.03;
        const sl  = entry * 0.98;
        const dtp = ((tp - price) / price * 100).toFixed(2);
        const dsl = ((price - sl) / price * 100).toFixed(2);
        pnlSub.textContent = `TP falta +${dtp}% | SL falta -${dsl}%`;
    } else {
        pnlEl.textContent = '–';
        pnlEl.className   = 'card-value c-gray';
        pnlGlow.style.background = '#30363d';
        pnlSub.textContent = 'Sem posição aberta';
    }
}

// ── Conditions ──────────────────────────────────────────────────────────
function updateConditions(d) {
    const c   = d.conditions || {};
    const rsi = d.rsi || 50;
    const met = [c.price_above_sma50, c.sma50_rising, c.rsi_below_40, c.volume_above_mean]
                .filter(Boolean).length;

    document.getElementById('cond-count').textContent = met + '/4 ativas';
    document.getElementById('card-sig').textContent   = met + '/4';

    const condValues = [c.price_above_sma50, c.sma50_rising, c.rsi_below_40, c.volume_above_mean];
    ['c1','c2','c3','c4'].forEach((id, i) => {
        document.getElementById(id).textContent = condValues[i] ? '✅' : '❌';
    });

    // Hints
    if (d.sma50 && d.current_price) {
        const diff = ((d.current_price - d.sma50) / d.sma50 * 100).toFixed(2);
        const h = document.getElementById('c1h');
        h.textContent  = (diff >= 0 ? '+' : '') + diff + '%';
        h.style.color  = c.price_above_sma50 ? '#7ee787' : '#f85149';
    }
    const c2h = document.getElementById('c2h');
    c2h.textContent = c.sma50_rising ? '↗ Subindo' : '↘ Caindo';
    c2h.style.color = c.sma50_rising ? '#7ee787' : '#f85149';

    const c3h = document.getElementById('c3h');
    c3h.textContent = 'RSI: ' + rsi.toFixed(1);
    c3h.style.color = c.rsi_below_40 ? '#7ee787' : '#f85149';

    const vr  = c.volume_ratio || 0;
    const c4h = document.getElementById('c4h');
    c4h.textContent = vr.toFixed(2) + 'x média';
    c4h.style.color = c.volume_above_mean ? '#7ee787' : '#f85149';

    // RSI progress (0 → 80 range)
    const rsiPct = Math.min(100, Math.max(0, rsi / 80 * 100));
    const rsiColor = rsi < 40 ? '#7ee787' : rsi < 55 ? '#f1e05a' : '#f85149';
    document.getElementById('rsi-bar').style.width      = rsiPct + '%';
    document.getElementById('rsi-bar').style.background = rsiColor;
    document.getElementById('rsi-bar-val').textContent  = rsi.toFixed(2);
    const rsiHintEl = document.getElementById('rsi-bar-hint');
    if (rsi < 40) {
        rsiHintEl.textContent = '✅ Gatilho ativo!';
        rsiHintEl.style.color = '#7ee787';
    } else {
        rsiHintEl.textContent = 'Faltam ' + (rsi - 40).toFixed(1) + ' pts para ativar';
        rsiHintEl.style.color = '#8b949e';
    }

    // Volume progress (0 → 3x range)
    document.getElementById('vol-bar').style.width      = Math.min(100, vr / 3 * 100) + '%';
    document.getElementById('vol-bar').style.background = vr >= 1 ? '#7ee787' : '#58a6ff';
    document.getElementById('vol-bar-val').textContent  = vr.toFixed(2) + 'x';
    document.getElementById('vol-bar-hint').textContent = vr >= 1 ? '✅ Acima da média' : 'Abaixo da média';

    // Sell trigger bar
    document.getElementById('sell-bar').style.width = Math.min(100, rsi / 80 * 100) + '%';
    const sellHint = document.getElementById('sell-bar-hint');
    if (rsi >= 65) {
        sellHint.textContent = '⚠️ GATILHO DE VENDA ATIVO!';
        sellHint.style.color = '#f85149';
    } else {
        sellHint.textContent = 'Faltam ' + (65 - rsi).toFixed(1) + ' pts para venda';
        sellHint.style.color = '#8b949e';
    }

    // Signal card
    const sigGlow = document.getElementById('sig-glow');
    const sigSub  = document.getElementById('card-sig-sub');
    const sigBox  = document.getElementById('signal-box');
    if (met === 4) {
        document.getElementById('card-sig').className = 'card-value c-green';
        sigGlow.style.background = '#7ee787';
        sigSub.textContent       = '🚀 SINAL DE COMPRA ATIVO!';
        sigSub.style.color       = '#7ee787';
        sigBox.style.display     = 'block';
        sigBox.style.background  = 'rgba(126,231,135,.1)';
        sigBox.style.color       = '#7ee787';
        sigBox.style.border      = '1px solid rgba(126,231,135,.35)';
        sigBox.textContent       = '🚀 TODAS AS CONDIÇÕES ATIVAS — ROBÔ PODE COMPRAR!';
    } else {
        document.getElementById('card-sig').className = 'card-value c-gray';
        sigGlow.style.background = '#30363d';
        sigSub.textContent       = met + ' de 4 condições ativas';
        sigSub.style.color       = '#8b949e';
        sigBox.style.display     = 'none';
    }
}

// ── Trade Log ────────────────────────────────────────────────────────────
function updateTradeLog(d) {
    const trades = (d.trade_log || []).slice().reverse();   // mais recente primeiro
    const countEl = document.getElementById('trade-count');
    countEl.textContent = trades.length + ' trade' + (trades.length !== 1 ? 's' : '');

    // Notifica novo trade
    if (trades.length > prevTradeCount && prevTradeCount > 0) {
        const newest = trades[0];
        if (newest.type === 'buy') {
            showToast('📈 COMPRA EXECUTADA<br>$' +
                parseFloat(newest.price).toLocaleString('en-US', { minimumFractionDigits: 2 }), '#26a69a');
        } else {
            const sign = (newest.pnl_pct || 0) >= 0 ? '+' : '';
            showToast('📉 VENDA EXECUTADA<br>$' +
                parseFloat(newest.price).toLocaleString('en-US', { minimumFractionDigits: 2 }) +
                ' &nbsp;P&L: ' + sign + (newest.pnl_pct || 0).toFixed(2) + '%', '#ef5350');
        }
    }
    prevTradeCount = trades.length;

    const body = document.getElementById('trade-log');
    if (trades.length === 0) {
        body.innerHTML = `<div class="no-trades">Nenhuma operação registrada ainda.<br>
            O robô entra quando as 4 condições estiverem ativas.</div>`;
        return;
    }

    body.innerHTML = trades.slice(0, 8).map(t => {
        const pnlStr = (t.pnl_pct !== undefined)
            ? `<span class="trade-pnl ${t.pnl_pct >= 0 ? 'c-green' : 'c-red'}">
                   ${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%
               </span>`
            : '';
        return `<div class="trade-item">
            <span class="trade-badge ${t.type === 'buy' ? 'badge-buy' : 'badge-sell'}">
                ${t.type === 'buy' ? '▲ COMPRA' : '▼ VENDA'}
            </span>
            <span class="trade-price">$${parseFloat(t.price).toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            ${pnlStr}
            <span class="trade-time">${t.datetime || ''}</span>
        </div>`;
    }).join('');
}

// ── Chart ────────────────────────────────────────────────────────────────
function updateChart(d) {
    if (!d.history_candles || d.history_candles.length === 0) return;
    document.getElementById('chart-loading').style.display = 'none';

    // ── Correção de fuso horário ──────────────────────────────────────────
    // Binance entrega timestamps em UTC (segundos). O lightweight-charts v3
    // exibe UTC puro. Como o usuário está em BRT (UTC-3), subtraímos o
    // offset do próprio navegador para que o gráfico mostre a hora local.
    //   getTimezoneOffset() → minutos à frente do UTC (ex.: 180 para UTC-3)
    //   * 60 → converte para segundos
    const tzOffset = new Date().getTimezoneOffset() * 60;

    // Candles com tempo ajustado para fuso local
    const candles = d.history_candles.map(c => ({ ...c, time: c.time - tzOffset }));

    candleSeries.setData(candles);

    // Volume colorido (verde = candle alta, vermelho = candle baixa)
    volSeries.setData(candles.map(c => ({
        time:  c.time,
        value: c.volume || 0,
        color: c.close >= c.open ? 'rgba(38,166,154,.35)' : 'rgba(239,83,80,.35)'
    })));

    // SMA50
    const smaData = candles
        .filter(c => c.sma !== null && c.sma !== undefined)
        .map(c => ({ time: c.time, value: c.sma }));
    if (smaData.length > 0) smaSeries.setData(smaData);

    // Marcadores de compra/venda no gráfico (mesmo offset aplicado)
    const trades = (d.trade_log || []).filter(t => t.time);
    if (trades.length > 0) {
        const markers = trades
            .map(t => ({
                time:     t.time - tzOffset,
                position: t.type === 'buy' ? 'belowBar' : 'aboveBar',
                color:    t.type === 'buy' ? '#26a69a'  : '#ef5350',
                shape:    t.type === 'buy' ? 'arrowUp'  : 'arrowDown',
                text:     t.type === 'buy' ? '▲ COMPRA' : '▼ VENDA'
            }))
            .sort((a, b) => a.time - b.time);
        candleSeries.setMarkers(markers);
    }
}

// ── Main fetch loop ───────────────────────────────────────────────────────
async function fetchAndUpdate() {
    try {
        const res = await fetch('/api/data');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        if (!data || !data.current_price) return;

        updateCards(data);
        updateConditions(data);
        updateTradeLog(data);
        updateChart(data);
    } catch (e) {
        console.error('Erro ao buscar dados:', e);
        const loadEl = document.getElementById('chart-loading');
        loadEl.style.display = 'block';
        loadEl.textContent   = '❌ Erro de conexão: ' + e.message;
    }
}

initChart();
fetchAndUpdate();
setInterval(fetchAndUpdate, 2000);
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass   # silencia logs do servidor

    def handle_error(self, *_): pass  # ignora BrokenPipe silenciosamente

    def do_GET(self):

        # ── API de dados ──────────────────────────────────────────────────
        if self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            candles_list  = []
            current_price = 0
            rsi_val       = 50.0
            conditions    = {}
            sma50_val     = None

            try:
                ticker = exchange.fetch_ticker(SYMBOL)
                current_price = float(ticker['last'])

                ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=70)
                df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                df = apply_indicators(df)

                rsi_val = float(df['rsi'].iloc[-1]) if not pd.isna(df['rsi'].iloc[-1]) else 50.0

                last = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else last

                # ── Condições de entrada ──
                price_ok = bool(float(last['close']) > float(last['sma50'])) if not pd.isna(last['sma50']) else False
                trend_ok = bool(float(last['sma50']) > float(prev['sma50'])) if not pd.isna(prev['sma50']) else False
                rsi_ok   = bool(rsi_val < 40)
                vol_mean = float(last['vol_mean']) if not pd.isna(last['vol_mean']) else 0
                vol_cur  = float(last['volume'])
                vol_ok   = bool(vol_cur > vol_mean) if vol_mean > 0 else False
                vol_ratio = round(vol_cur / vol_mean, 3) if vol_mean > 0 else 0

                conditions = {
                    "price_above_sma50": price_ok,
                    "sma50_rising":      trend_ok,
                    "rsi_below_40":      rsi_ok,
                    "volume_above_mean": vol_ok,
                    "volume_ratio":      vol_ratio
                }
                sma50_val = float(last['sma50']) if not pd.isna(last['sma50']) else None

                # ── Candles para o gráfico ──
                for _, r in df.iterrows():
                    candles_list.append({
                        "time":   int(r['time'] / 1000),
                        "open":   float(r['open']),
                        "high":   float(r['high']),
                        "low":    float(r['low']),
                        "close":  float(r['close']),
                        "volume": float(r['volume']),
                        "sma":    float(r['sma50']) if not pd.isna(r['sma50']) else None
                    })

            except Exception as e:
                print(f"Aviso API: {e}")

            # ── Estado do bot ──────────────────────────────────────────────
            position_status = None
            entry_price     = 0.0
            trade_log       = []

            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, 'r') as f:
                        bot_json = json.load(f)
                        position_status = bot_json.get("position")
                        entry_price     = bot_json.get("entry_price", 0.0)
                        trade_log       = bot_json.get("trade_log", [])
                        # Preço sincronizado com o bot se disponível
                        if bot_json.get("current_price"):
                            current_price = bot_json["current_price"]
                except: pass

            payload = {
                "current_price":   current_price,
                "rsi":             rsi_val,
                "position":        position_status,
                "entry_price":     entry_price,
                "sma50":           sma50_val,
                "conditions":      conditions,
                "history_candles": candles_list,
                "trade_log":       trade_log
            }
            self.wfile.write(json.dumps(payload).encode())

        # ── Página principal ──────────────────────────────────────────────
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
    print("✅  Dashboard do Robô BTC ativado!")
    print("👉  Acesse: http://localhost:8080")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Dashboard encerrado.")
