# dashboard_server.py
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import json
import os
import time
import ccxt
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from config import API_KEY, SECRET, SYMBOL, TIMEFRAME, STATE_FILE, CONTROL_FILE
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
<title>NEXUS · BTC/USDT Robô Automático</title>
<script src="https://unpkg.com/lightweight-charts@3.8.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
:root {
    --bg:         #060d1f;
    --bg-panel:   #0a1628;
    --bg-card:    #0d1b30;
    --border:     #1a2e4a;
    --border-hi:  #2563eb;
    --text:       #cdd6f4;
    --muted:      #4a5a72;
    --green:      #00d87a;
    --red:        #ff4757;
    --blue:       #3d9eff;
    --yellow:     #ffd43b;
    --orange:     #ff8c42;
    --purple:     #a78bfa;
    --pink:       #f472b6;
    --cyan:       #22d3ee;
    --white:      #e2e8f0;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: var(--bg); color: var(--text);
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'Segoe UI', monospace;
    height: 100vh; display: flex; flex-direction: column; overflow: hidden;
    font-size: 13px;
}

/* ══ HEADER ════════════════════════════════════════════════════════════════ */
.header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 16px; height: 48px; flex-shrink: 0;
    background: linear-gradient(180deg, #0f1e38 0%, #0a1628 100%);
    border-bottom: 1px solid var(--border);
    position: relative;
}
.header::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, var(--border-hi), transparent);
    opacity: 0.4;
}
.hd-left { display: flex; align-items: center; gap: 12px; }
.logo {
    font-size: .95rem; font-weight: 800; letter-spacing: .15em;
    color: var(--white); text-transform: uppercase;
    background: linear-gradient(135deg, #60a5fa, #818cf8);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.live-badge {
    display: flex; align-items: center; gap: 5px;
    background: rgba(0,216,122,.08); border: 1px solid rgba(0,216,122,.25);
    border-radius: 20px; padding: 3px 10px; font-size: .68rem;
    color: var(--green); font-weight: 700; letter-spacing: .04em;
}
.live-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); animation: blink 1.4s infinite; }
@keyframes blink { 0%,100%{opacity:1;box-shadow:0 0 4px var(--green)} 50%{opacity:.2;box-shadow:none} }

.hd-center { display: flex; align-items: center; gap: 14px; font-size: .7rem; color: var(--muted); }
.hd-center strong { color: var(--white); }
.hd-sep { color: #1a2e4a; }
#bot-status-badge {
    padding: 3px 10px; border-radius: 20px; font-size: .68rem; font-weight: 700;
    letter-spacing: .04em; transition: all .4s;
}
.bs-active  { background: rgba(0,216,122,.1);  border: 1px solid rgba(0,216,122,.3);  color: var(--green); }
.bs-paused  { background: rgba(255,212,59,.1); border: 1px solid rgba(255,212,59,.3); color: var(--yellow); }
.bs-offline { background: rgba(255,71,87,.1);  border: 1px solid rgba(255,71,87,.3);  color: var(--red); }

.hd-right { display: flex; align-items: center; gap: 8px; }
.ctrl-btn {
    padding: 5px 13px; border-radius: 6px; font-size: .7rem; font-weight: 700;
    cursor: pointer; border: 1px solid; transition: all .2s; letter-spacing: .04em;
    font-family: inherit;
}
.btn-pause  { background: rgba(255,212,59,.08); border-color: rgba(255,212,59,.3); color: var(--yellow); }
.btn-pause:hover  { background: rgba(255,212,59,.18); border-color: var(--yellow); }
.btn-sell   { background: rgba(255,71,87,.08);  border-color: rgba(255,71,87,.3);  color: var(--red); }
.btn-sell:hover   { background: rgba(255,71,87,.2);  border-color: var(--red); }
.btn-sell.hidden  { opacity: .3; pointer-events: none; }
#hd-clock { font-size: .75rem; color: var(--white); font-weight: 600; letter-spacing: .05em; min-width: 64px; text-align: right; }

/* ══ CARDS ══════════════════════════════════════════════════════════════════ */
.cards {
    display: grid; grid-template-columns: repeat(7, 1fr);
    gap: 6px; padding: 6px 16px; flex-shrink: 0;
}
.card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 8px; padding: 8px 11px; position: relative; overflow: hidden;
    transition: border-color .4s;
}
.card:hover { border-color: #2a3e5a; }
.card-glow { position: absolute; top: 0; left: 0; right: 0; height: 2px; border-radius: 8px 8px 0 0; transition: background .4s; }
.card-label { font-size: .58rem; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 3px; }
.card-value { font-size: 1.05rem; font-weight: 700; line-height: 1.1; letter-spacing: -.01em; }
.card-sub   { font-size: .6rem; color: var(--muted); margin-top: 2px; }
.card-sub b { color: var(--text); font-weight: 600; }

/* ══ CONDITIONS STRIP ═══════════════════════════════════════════════════════ */
.cond-strip {
    display: flex; align-items: center; gap: 6px;
    padding: 0 16px; height: 36px; flex-shrink: 0;
    background: #080f20; border-bottom: 1px solid var(--border);
    overflow-x: auto;
}
.cond-strip::-webkit-scrollbar { display: none; }
.strip-lbl {
    font-size: .6rem; color: var(--muted); text-transform: uppercase;
    letter-spacing: .08em; font-weight: 700; flex-shrink: 0; white-space: nowrap;
}
.pill {
    display: flex; align-items: center; gap: 4px; padding: 3px 10px;
    border-radius: 20px; font-size: .66rem; font-weight: 700;
    transition: all .35s; flex-shrink: 0; white-space: nowrap;
}
.pill.ok   { background: rgba(0,216,122,.1);  border: 1px solid rgba(0,216,122,.3);  color: var(--green); }
.pill.fail { background: rgba(26,46,74,.5);   border: 1px solid rgba(26,46,74,.8);   color: #2a3e5a; }
.pill-sell.ok   { background: rgba(255,71,87,.1);  border: 1px solid rgba(255,71,87,.3);  color: var(--red); }
.pill-sell.fail { background: rgba(26,46,74,.5);   border: 1px solid rgba(26,46,74,.8);   color: #2a3e5a; }
.strip-sep { color: #1a2e4a; font-size: 1rem; flex-shrink: 0; }
#strip-cnt {
    margin-left: auto; padding: 3px 10px; border-radius: 20px;
    font-size: .7rem; font-weight: 800; flex-shrink: 0; letter-spacing: .04em;
}
.sc-ok  { background: rgba(0,216,122,.15);  color: var(--green); border: 1px solid rgba(0,216,122,.3); }
.sc-mid { background: rgba(255,212,59,.1);  color: var(--yellow);border: 1px solid rgba(255,212,59,.25); }
.sc-low { background: rgba(26,46,74,.5);    color: var(--muted); border: 1px solid rgba(26,46,74,.8); }

/* ══ CHARTS ═════════════════════════════════════════════════════════════════ */
.charts-wrap {
    flex: 1; min-height: 0; display: flex; flex-direction: column;
    padding: 4px 16px; gap: 3px;
}
.chart-box {
    position: relative; background: var(--bg-panel);
    border: 1px solid var(--border); border-radius: 8px; overflow: hidden;
}
.chart-inner { width: 100%; height: 100%; }
#main-box { flex: 5; }
#didi-box { flex: 2; }
.chart-label {
    position: absolute; top: 6px; left: 10px; z-index: 10;
    font-size: .58rem; font-weight: 600; color: var(--muted);
    letter-spacing: .05em; pointer-events: none;
    background: rgba(6,13,31,.7); padding: 2px 6px; border-radius: 4px;
}
.leg { font-size: .57rem; }
#main-loading {
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%,-50%);
    color: var(--muted); font-size: .8rem; z-index: 5;
}

/* Nav buttons */
#chart-nav {
    position: absolute; right: 66px; top: 50%;
    transform: translateY(-50%); z-index: 20;
    display: flex; flex-direction: column; gap: 3px;
}
#chart-nav button {
    width: 28px; height: 28px;
    background: rgba(6,13,31,.9); border: 1px solid var(--border);
    border-radius: 6px; color: var(--muted); font-size: .75rem;
    cursor: pointer; transition: all .2s; padding: 0; line-height: 1;
    font-family: inherit;
}
#chart-nav button:hover  { border-color: var(--blue); color: var(--blue); }
#chart-nav .btn-tip {
    font-size: .52rem; color: #2a3e5a; text-align: center;
    margin-top: 2px; line-height: 1.2;
}

/* ══ BOTTOM ═════════════════════════════════════════════════════════════════ */
.bottom-row {
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 6px; padding: 3px 16px 10px; flex-shrink: 0;
}
.panel {
    background: var(--bg-panel); border: 1px solid var(--border);
    border-radius: 8px; padding: 8px 12px; overflow: hidden;
}
.panel-title {
    font-size: .6rem; color: var(--muted); text-transform: uppercase;
    letter-spacing: .09em; margin-bottom: 6px; font-weight: 700;
    display: flex; align-items: center; justify-content: space-between;
    border-bottom: 1px solid var(--border); padding-bottom: 5px;
}
.panel-badge {
    font-size: .64rem; font-weight: 700; padding: 1px 7px;
    border-radius: 10px; letter-spacing: .03em;
}

/* Indicadores */
.ind-section { margin-bottom: 5px; }
.ind-hdr {
    font-size: .56rem; color: #2a3e5a; text-transform: uppercase;
    letter-spacing: .07em; margin-bottom: 3px; padding-bottom: 2px;
    border-bottom: 1px solid #0d1b30;
}
.ind-row {
    display: grid; grid-template-columns: 72px 1fr auto;
    align-items: center; gap: 4px;
    padding: 2px 0; font-size: .7rem;
}
.ind-name { color: var(--muted); font-size: .62rem; font-weight: 600; }
.ind-val  { font-weight: 700; color: var(--white); }
.ind-tag  {
    font-size: .6rem; padding: 1px 6px; border-radius: 4px;
    font-weight: 700; text-align: center; white-space: nowrap;
}
.tag-up  { background: rgba(0,216,122,.12); color: var(--green); }
.tag-dn  { background: rgba(255,71,87,.12); color: var(--red); }
.tag-neu { background: rgba(74,90,114,.15); color: var(--muted); }
.tag-warn{ background: rgba(255,212,59,.12);color: var(--yellow); }

/* RSI gauge */
.rsi-bar-wrap {
    background: #0d1b30; border-radius: 4px; height: 5px;
    overflow: hidden; margin-top: 2px; position: relative;
}
.rsi-bar { height: 100%; border-radius: 4px; transition: width .5s, background .5s; }
.rsi-zones { position: relative; font-size: .5rem; color: #2a3e5a; display: flex; justify-content: space-between; margin-top: 1px; }

/* Faixa Branca */
.faixa-badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 8px; border-radius: 5px; font-size: .65rem; font-weight: 700;
    margin-bottom: 3px; width: 100%;
}
.fb-setup  { background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.2); color: var(--white); }
.fb-normal { background: rgba(26,46,74,.4);     border: 1px solid rgba(26,46,74,.8);   color: #2a3e5a; }

/* Estatísticas */
.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; }
.stat-box {
    background: #080f20; border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 8px; text-align: center;
}
.stat-lbl { font-size: .56rem; color: var(--muted); text-transform: uppercase; letter-spacing: .07em; margin-bottom: 2px; }
.stat-val { font-size: .95rem; font-weight: 700; }
.stat-sub { font-size: .55rem; color: var(--muted); margin-top: 1px; }
.progress-wrap { margin-top: 5px; }
.progress-lbl { display: flex; justify-content: space-between; font-size: .58rem; color: var(--muted); margin-bottom: 3px; }
.progress-bar { background: #0d1b30; border-radius: 4px; height: 6px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 4px; transition: width .5s, background .5s; }

/* Trade log */
.trade-row {
    display: flex; align-items: center; gap: 6px;
    padding: 3px 0; border-bottom: 1px solid #0d1b30; font-size: .7rem;
}
.trade-row:last-child { border-bottom: none; }
.trade-badge {
    padding: 2px 6px; border-radius: 4px; font-size: .59rem;
    font-weight: 700; text-transform: uppercase; flex-shrink: 0;
    letter-spacing: .04em;
}
.b-buy  { background: rgba(61,158,255,.12); color: var(--blue);   border: 1px solid rgba(61,158,255,.25); }
.b-sell { background: rgba(255,212,59,.1);  color: var(--yellow); border: 1px solid rgba(255,212,59,.25); }
.t-price{ font-weight: 700; color: var(--white); }
.t-pnl  { margin-left: auto; font-weight: 700; flex-shrink: 0; }
.t-reason { font-size: .57rem; color: var(--muted); flex-shrink: 0; }
.t-time { color: var(--muted); font-size: .61rem; flex-shrink: 0; }
.no-trades { color: var(--muted); font-size: .72rem; text-align: center; padding: 10px 0; line-height: 1.7; }

/* Colors */
.c-green { color: var(--green); } .c-red   { color: var(--red);    }
.c-blue  { color: var(--blue);  } .c-yellow{ color: var(--yellow); }
.c-gray  { color: var(--muted); } .c-white { color: var(--white);  }
.c-orange{ color: var(--orange);} .c-purple{ color: var(--purple); }
.c-pink  { color: var(--pink);  } .c-cyan  { color: var(--cyan);   }

/* Toast */
#toast {
    position: fixed; top: 54px; right: 16px; z-index: 9999;
    background: var(--bg-panel); border: 1px solid var(--border);
    border-radius: 10px; padding: 10px 15px; font-size: .78rem; font-weight: 600;
    box-shadow: 0 8px 40px rgba(0,0,0,.8);
    transform: translateX(120%); transition: transform .3s cubic-bezier(.175,.885,.32,1.275);
    max-width: 240px; line-height: 1.5;
}
#toast.show { transform: translateX(0); }

/* Animations */
@keyframes card-flash { 0%{background:rgba(61,158,255,.15);border-color:var(--blue)} 100%{background:var(--bg-card);border-color:var(--border)} }
.card.flash { animation: card-flash 2s ease; }
@keyframes pulse-anim { 0%,100%{opacity:1} 50%{opacity:.35} }
.blink { animation: pulse-anim 1s infinite; }

/* Scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
</style>
</head>
<body>

<!-- ══ HEADER ════════════════════════════════════════════════════════════════ -->
<div class="header">
    <div class="hd-left">
        <span class="logo">NEXUS</span>
        <div class="live-badge"><div class="live-dot"></div>AO VIVO</div>
        <div id="bot-status-badge" class="bs-offline">OFFLINE</div>
    </div>
    <div class="hd-center">
        <span>Par: <strong>BTC/USDT</strong></span>
        <span class="hd-sep">│</span>
        <span>TF: <strong>15m</strong></span>
        <span class="hd-sep">│</span>
        <span>Estratégia: <strong>Supertrend + EMA50 + Didi WDO + RSI</strong></span>
        <span class="hd-sep">│</span>
        <span>SL: <strong style="color:var(--red)">-2%</strong> &nbsp; TP: <strong style="color:var(--green)">+3%</strong></span>
        <span class="hd-sep">│</span>
        <span id="hd-uptime" style="color:var(--cyan)">--</span>
    </div>
    <div class="hd-right">
        <button class="ctrl-btn btn-pause" id="btn-pause" onclick="togglePause()">⏸ PAUSAR</button>
        <button class="ctrl-btn btn-sell hidden" id="btn-force-sell" onclick="forceSell()">⛔ FORCE SELL</button>
        <span id="hd-clock">--:--:--</span>
    </div>
</div>

<!-- ══ CARDS ══════════════════════════════════════════════════════════════════ -->
<div class="cards">
    <!-- Preço BTC -->
    <div class="card">
        <div class="card-glow" style="background:linear-gradient(90deg,#3d9eff,#1d4ed8)"></div>
        <div class="card-label">💰 Preço BTC</div>
        <div class="card-value c-blue" id="c-price">$0.00</div>
        <div class="card-sub" id="c-price-sub">–</div>
    </div>
    <!-- Saldo USDT -->
    <div class="card">
        <div class="card-glow" id="usdt-glow" style="background:#1a2e4a"></div>
        <div class="card-label">💵 Saldo USDT</div>
        <div class="card-value c-white" id="c-usdt">$0.00</div>
        <div class="card-sub" id="c-usdt-sub">disponível</div>
    </div>
    <!-- BTC em carteira -->
    <div class="card">
        <div class="card-glow" id="btc-glow" style="background:#1a2e4a"></div>
        <div class="card-label">₿ Carteira BTC</div>
        <div class="card-value c-orange" id="c-btc">0.000000</div>
        <div class="card-sub" id="c-btc-sub">≈ $0.00</div>
    </div>
    <!-- Status posição -->
    <div class="card" id="card-status-el">
        <div class="card-glow" id="status-glow" style="background:#1a2e4a"></div>
        <div class="card-label">🤖 Posição</div>
        <div class="card-value c-gray" id="c-status">AGUARDANDO</div>
        <div class="card-sub" id="c-status-sub">–</div>
    </div>
    <!-- P&L live -->
    <div class="card">
        <div class="card-glow" id="pnl-glow" style="background:#1a2e4a"></div>
        <div class="card-label">📊 P&amp;L / Sinal</div>
        <div class="card-value c-gray" id="c-pnl">–</div>
        <div class="card-sub" id="c-pnl-sub">Sem posição</div>
    </div>
    <!-- Win Rate -->
    <div class="card">
        <div class="card-glow" id="wr-glow" style="background:#1a2e4a"></div>
        <div class="card-label">🎯 Win Rate</div>
        <div class="card-value c-gray" id="c-winrate">–</div>
        <div class="card-sub" id="c-winrate-sub">0 trades</div>
    </div>
    <!-- RSI -->
    <div class="card">
        <div class="card-glow" id="rsi-glow" style="background:#1a2e4a"></div>
        <div class="card-label">📉 RSI (14)</div>
        <div class="card-value c-gray" id="c-rsi">–</div>
        <div class="card-sub" id="c-rsi-sub">Momentum</div>
    </div>
</div>

<!-- ══ CONDITIONS STRIP ════════════════════════════════════════════════════════ -->
<div class="cond-strip">
    <span class="strip-lbl">COMPRA:</span>
    <div class="pill fail" id="pill1">⬜ ST Bullish</div>
    <div class="pill fail" id="pill2">⬜ Preço &gt; EMA50</div>
    <div class="pill fail" id="pill3">⬜ Didi ↑</div>
    <div class="pill fail" id="pill4">⬜ Volume OK</div>
    <div class="pill fail" id="pill5">⬜ RSI &lt; 70</div>
    <span class="strip-sep">│</span>
    <span class="strip-lbl" style="color:var(--red)">VENDA:</span>
    <div class="pill pill-sell fail" id="pills1">⬜ ST Bearish</div>
    <div class="pill pill-sell fail" id="pills2">⬜ Didi ↓</div>
    <div class="pill pill-sell fail" id="pills3">⬜ RSI &gt; 80</div>
    <div id="strip-cnt" class="sc-low">0/5</div>
</div>

<!-- ══ CHARTS ════════════════════════════════════════════════════════════════ -->
<div class="charts-wrap">
    <div class="chart-box" id="main-box">
        <div id="main-loading">⏳ Carregando gráfico...</div>
        <div id="chart-nav">
            <button onclick="scrollPrice(-1)" title="Rolar para cima (Shift+Scroll)">▲</button>
            <button onclick="fitChart()" title="Ajustar tela (F)">⊙</button>
            <button onclick="scrollPrice(1)"  title="Rolar para baixo">▼</button>
            <div class="btn-tip">Shift<br>+Scroll</div>
        </div>
        <div class="chart-label">
            BTC/USDT · 15m &nbsp;
            <span class="leg">
                <span style="color:var(--orange)">■</span> EMA50 &nbsp;
                <span style="color:var(--purple)">■</span> SMA200 &nbsp;
                <span style="color:var(--pink)">■</span> VWAP &nbsp;
                <span style="color:var(--green)">■</span>/<span style="color:var(--red)">■</span> Supertrend
            </span>
        </div>
        <div class="chart-inner" id="main-inner"></div>
    </div>
    <div class="chart-box" id="didi-box">
        <div class="chart-label">
            DIDI INDEX · Welles Wilder (3/8/20) &nbsp;
            <span class="leg">
                <span style="color:var(--blue)">■</span> L3 Curta &nbsp;
                <span style="color:var(--yellow)">─</span> L20 Longa &nbsp;
                <span style="color:rgba(255,255,255,.5)">▓</span> Faixa Branca ±0.02%
            </span>
        </div>
        <div class="chart-inner" id="didi-inner"></div>
    </div>
</div>

<!-- ══ BOTTOM ════════════════════════════════════════════════════════════════ -->
<div class="bottom-row">

    <!-- Indicadores ao Vivo -->
    <div class="panel">
        <div class="panel-title">
            <span>📊 Indicadores ao Vivo</span>
            <span id="ind-sig" class="panel-badge"></span>
        </div>
        <div id="ind-body"><div class="no-trades">Aguardando dados...</div></div>
    </div>

    <!-- Estatísticas -->
    <div class="panel">
        <div class="panel-title">
            <span>🏆 Estatísticas</span>
            <span id="stats-badge" class="panel-badge"></span>
        </div>
        <div id="stats-body"><div class="no-trades">Sem trades ainda.</div></div>
    </div>

    <!-- Log de Operações -->
    <div class="panel">
        <div class="panel-title">
            <span>📋 Log de Operações</span>
            <span id="trade-count" style="color:var(--muted);font-size:.65rem">0 trades</span>
        </div>
        <div id="trade-log">
            <div class="no-trades">Nenhuma operação ainda.<br>Aguardando as 5 condições simultâneas.</div>
        </div>
    </div>
</div>
<div id="toast"></div>

<!-- ══ SCRIPT ═════════════════════════════════════════════════════════════════ -->
<script>
let mainChart, candleSeries, stBullS, stBearS, ema50S, sma200S, vwapS, volS;
let didiChart, didiShortS, didiLongS;
let syncing = false;
let prevPosition = null, prevTradeCount = 0, isPaused = false;
const TZ = new Date().getTimezoneOffset() * 60;
const lt  = t => t - TZ;

// ── Utilities ──────────────────────────────────────────────────────────────
function fmt$(v) { return '$' + (v || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
function fmtPct(v) { return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'; }
function pdist(price, val) {
    if (!val || !price) return { t: '–', c: 'tag-neu' };
    const p = (price - val) / val * 100;
    return { t: fmtPct(p), c: p >= 0 ? 'tag-up' : 'tag-dn' };
}
function setEl(id, text, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    if (text !== undefined) el.textContent = text;
    if (cls !== undefined) el.className = cls;
}

// ── Toast ──────────────────────────────────────────────────────────────────
function showToast(html, color) {
    const t = document.getElementById('toast');
    t.innerHTML = html; t.style.borderColor = color; t.style.color = color;
    t.classList.add('show'); clearTimeout(t._t);
    t._t = setTimeout(() => t.classList.remove('show'), 7000);
}

// ── Clock + Uptime ─────────────────────────────────────────────────────────
setInterval(() => {
    document.getElementById('hd-clock').textContent = new Date().toLocaleTimeString('pt-BR');
}, 1000);

function fmtUptime(secs) {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}

// ── Init Charts ────────────────────────────────────────────────────────────
function initCharts() {
    const mBox = document.getElementById('main-box');
    const dBox = document.getElementById('didi-box');
    const base = {
        layout:    { backgroundColor: '#0a1628', textColor: '#4a5a72' },
        grid:      { vertLines: { color: '#0d1b30' }, horzLines: { color: '#0d1b30' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { autoScale: true, borderColor: '#1a2e4a' },
        handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true },
        handleScale:  { mouseWheel: true, pinch: true, axisPressedMouseMove: { time: true, price: true } }
    };

    mainChart = LightweightCharts.createChart(document.getElementById('main-inner'), {
        ...base, width: mBox.clientWidth, height: mBox.clientHeight,
        timeScale: { visible: false }
    });
    volS = mainChart.addHistogramSeries({
        color: '#1a2e4a', priceFormat: { type: 'volume' }, overlay: true,
        scaleMargins: { top: 0.82, bottom: 0 }
    });
    candleSeries = mainChart.addCandlestickSeries({
        upColor: '#00d87a', downColor: '#ff4757',
        borderVisible: false, wickUpColor: '#00d87a', wickDownColor: '#ff4757'
    });
    sma200S = mainChart.addLineSeries({ color: '#a78bfa', lineWidth: 2, title: 'SMA200', priceLineVisible: false, lastValueVisible: true });
    ema50S  = mainChart.addLineSeries({ color: '#ff8c42', lineWidth: 2, title: 'EMA50',  priceLineVisible: false, lastValueVisible: true });
    vwapS   = mainChart.addLineSeries({ color: '#f472b6', lineWidth: 2, title: 'VWAP',   priceLineVisible: false, lastValueVisible: true });
    stBullS = mainChart.addLineSeries({ color: '#00d87a', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    stBearS = mainChart.addLineSeries({ color: '#ff4757', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });

    didiChart = LightweightCharts.createChart(document.getElementById('didi-inner'), {
        ...base, width: dBox.clientWidth, height: dBox.clientHeight,
        timeScale: { visible: true, timeVisible: true, secondsVisible: false, borderColor: '#1a2e4a' }
    });
    didiShortS = didiChart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: true });
    didiLongS  = didiChart.addLineSeries({ color: '#ffd43b', lineWidth: 2, title: 'L20', priceLineVisible: false, lastValueVisible: true });
    didiShortS.createPriceLine({ price:  0.02, color: 'rgba(255,255,255,.3)', lineWidth: 1, lineStyle: 0, axisLabelVisible: true, title: 'FB+' });
    didiShortS.createPriceLine({ price: -0.02, color: 'rgba(255,255,255,.3)', lineWidth: 1, lineStyle: 0, axisLabelVisible: true, title: 'FB-' });
    didiShortS.createPriceLine({ price:  0,    color: '#1a2e4a',              lineWidth: 1, lineStyle: 2, axisLabelVisible: false });

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

// ── Cards ──────────────────────────────────────────────────────────────────
function updateCards(d) {
    const price = d.current_price || 0;
    const c     = d.conditions   || {};
    const stats = d.stats        || {};

    // Preço
    setEl('c-price', fmt$(price));
    if (c.vwap_val != null) {
        const vd = ((price - c.vwap_val) / c.vwap_val * 100).toFixed(2);
        setEl('c-price-sub', 'VWAP $' + Math.round(c.vwap_val).toLocaleString('en-US') + ' (' + (vd >= 0 ? '+' : '') + vd + '%)');
    }

    // Saldo USDT
    const usdt = d.usdt_balance || 0;
    const btc  = d.btc_balance  || 0;
    document.getElementById('c-usdt').textContent = fmt$(usdt);
    document.getElementById('c-usdt-sub').textContent = usdt > 0 ? 'disponível para trade' : 'sem saldo USDT';
    document.getElementById('usdt-glow').style.background = usdt > 10 ? '#00d87a' : '#ff4757';

    // BTC
    const btcVal = btc * price;
    document.getElementById('c-btc').textContent = btc.toFixed(6) + ' BTC';
    document.getElementById('c-btc-sub').textContent = '≈ ' + fmt$(btcVal);
    document.getElementById('btc-glow').style.background = btc > 0.000001 ? '#ff8c42' : '#1a2e4a';

    // Status posição
    const pos = d.position;
    const sEl = document.getElementById('c-status');
    const sGl = document.getElementById('status-glow');
    if (pos === 'buy') {
        sEl.textContent = '▲ COMPRADO'; sEl.className = 'card-value c-green';
        sGl.style.background = 'var(--green)';
        setEl('c-status-sub', '@ ' + fmt$(d.entry_price));
    } else if (d.paused) {
        sEl.textContent = '⏸ PAUSADO'; sEl.className = 'card-value c-yellow';
        sGl.style.background = 'var(--yellow)';
        setEl('c-status-sub', 'aguardando retomada');
    } else {
        sEl.textContent = '◉ AGUARDANDO'; sEl.className = 'card-value c-gray';
        sGl.style.background = '#1a2e4a';
        setEl('c-status-sub', 'buscando sinal');
    }
    if (prevPosition !== null && prevPosition !== pos) {
        const card = document.getElementById('card-status-el');
        card.classList.remove('flash'); void card.offsetWidth; card.classList.add('flash');
        if (pos === 'buy') showToast('▲ ROBÔ ENTROU EM POSIÇÃO<br>Compra @ ' + fmt$(price), 'var(--blue)');
        else               showToast('▼ POSIÇÃO FECHADA<br>Venda @ ' + fmt$(price), 'var(--yellow)');
    }
    prevPosition = pos;

    // Botão Force Sell
    document.getElementById('btn-force-sell').classList.toggle('hidden', pos !== 'buy');

    // P&L live
    const pEl = document.getElementById('c-pnl');
    const pGl = document.getElementById('pnl-glow');
    if (pos === 'buy' && d.entry_price > 0) {
        const pct = (price - d.entry_price) / d.entry_price * 100;
        pEl.textContent = fmtPct(pct);
        pEl.className   = pct >= 0 ? 'card-value c-green' : 'card-value c-red';
        pGl.style.background = pct >= 0 ? 'var(--green)' : 'var(--red)';
        const tp = d.entry_price * 1.03, sl = d.entry_price * 0.98;
        setEl('c-pnl-sub', 'TP ' + fmtPct((tp-price)/price*100) + ' · SL ' + fmtPct((sl-price)/price*100));
    } else {
        const met = [c.st_bullish, c.ema50_bull, c.didi_agulhada_buy, c.volume_ok, c.rsi_ok].filter(Boolean).length;
        pEl.textContent = met + '/5';
        pEl.className   = met === 5 ? 'card-value c-green' : met >= 3 ? 'card-value c-yellow' : 'card-value c-gray';
        pGl.style.background = met === 5 ? 'var(--green)' : '#1a2e4a';
        setEl('c-pnl-sub', met === 5 ? '🚀 Sinal ativo!' : met + ' de 5 condições');
    }

    // Win Rate
    const wins   = stats.wins   || 0;
    const losses = stats.losses || 0;
    const total  = wins + losses;
    const wr     = total > 0 ? (wins / total * 100) : null;
    const wrEl   = document.getElementById('c-winrate');
    const wrGl   = document.getElementById('wr-glow');
    if (wr !== null) {
        wrEl.textContent = wr.toFixed(0) + '%';
        wrEl.className   = wr >= 60 ? 'card-value c-green' : wr >= 40 ? 'card-value c-yellow' : 'card-value c-red';
        wrGl.style.background = wr >= 60 ? 'var(--green)' : wr >= 40 ? 'var(--yellow)' : 'var(--red)';
        setEl('c-winrate-sub', wins + 'W · ' + losses + 'L · ' + total + ' total');
    } else {
        wrEl.textContent = '–'; wrEl.className = 'card-value c-gray';
        setEl('c-winrate-sub', 'sem histórico');
    }

    // RSI
    const rsi   = c.rsi_val;
    const rsiEl = document.getElementById('c-rsi');
    const rsiGl = document.getElementById('rsi-glow');
    if (rsi != null) {
        rsiEl.textContent = rsi.toFixed(1);
        if (rsi > 70) {
            rsiEl.className = 'card-value c-red blink';
            rsiGl.style.background = 'var(--red)';
            setEl('c-rsi-sub', '⚠ Sobrecomprado');
        } else if (rsi < 30) {
            rsiEl.className = 'card-value c-green blink';
            rsiGl.style.background = 'var(--green)';
            setEl('c-rsi-sub', '⚡ Sobrevendido');
        } else if (rsi > 60) {
            rsiEl.className = 'card-value c-yellow';
            rsiGl.style.background = 'var(--yellow)';
            setEl('c-rsi-sub', 'Zona de atenção');
        } else {
            rsiEl.className = 'card-value c-white';
            rsiGl.style.background = 'var(--blue)';
            setEl('c-rsi-sub', 'Zona neutra');
        }
    }

    // Bot status badge + uptime
    const now   = Math.floor(Date.now() / 1000);
    const badge = document.getElementById('bot-status-badge');
    if (d.last_update_ts && now - d.last_update_ts < 20) {
        if (d.paused) { badge.textContent = '⏸ PAUSADO'; badge.className = 'bs-paused'; }
        else          { badge.textContent = '▶ ATIVO';   badge.className = 'bs-active'; }
    } else {
        badge.textContent = '◉ OFFLINE'; badge.className = 'bs-offline';
    }
    if (d.uptime_start) {
        document.getElementById('hd-uptime').textContent = 'Uptime: ' + fmtUptime(now - d.uptime_start);
    }
    isPaused = d.paused || false;
    const pb = document.getElementById('btn-pause');
    pb.textContent = isPaused ? '▶ RETOMAR' : '⏸ PAUSAR';
    pb.className   = isPaused ? 'ctrl-btn btn-pause' : 'ctrl-btn btn-pause';
}

// ── Conditions Strip ────────────────────────────────────────────────────────
function updateStrip(d) {
    const c   = d.conditions || {};
    const met = [c.st_bullish, c.ema50_bull, c.didi_agulhada_buy, c.volume_ok, c.rsi_ok].filter(Boolean).length;
    const pills = [
        { id: 'pill1', ok: c.st_bullish,        label: 'ST Bullish' },
        { id: 'pill2', ok: c.ema50_bull,         label: 'Preço > EMA50' },
        { id: 'pill3', ok: c.didi_agulhada_buy,  label: 'Didi ↑' },
        { id: 'pill4', ok: c.volume_ok,          label: 'Volume OK' },
        { id: 'pill5', ok: c.rsi_ok,             label: 'RSI < 70' },
    ];
    pills.forEach(p => {
        const el = document.getElementById(p.id);
        el.textContent = (p.ok ? '✅' : '⬜') + ' ' + p.label;
        el.className   = 'pill ' + (p.ok ? 'ok' : 'fail');
    });
    const sp1 = !c.st_bullish, sp2 = c.didi_agulhada_sell, sp3 = c.rsi_extreme;
    document.getElementById('pills1').textContent = (sp1 ? '🔴' : '⬜') + ' ST Bearish';
    document.getElementById('pills2').textContent = (sp2 ? '🔴' : '⬜') + ' Didi ↓';
    document.getElementById('pills3').textContent = (sp3 ? '🔴' : '⬜') + ' RSI > 80';
    document.getElementById('pills1').className = 'pill pill-sell ' + (sp1 ? 'ok' : 'fail');
    document.getElementById('pills2').className = 'pill pill-sell ' + (sp2 ? 'ok' : 'fail');
    document.getElementById('pills3').className = 'pill pill-sell ' + (sp3 ? 'ok' : 'fail');
    const cnt = document.getElementById('strip-cnt');
    cnt.textContent = met + '/5';
    cnt.className   = met === 5 ? 'sc-ok' : met >= 3 ? 'sc-mid' : 'sc-low';
}

// ── Indicators Panel ────────────────────────────────────────────────────────
function updateIndicators(d) {
    const c     = d.conditions || {};
    const price = d.current_price || 0;
    const met   = [c.st_bullish, c.ema50_bull, c.didi_agulhada_buy, c.volume_ok, c.rsi_ok].filter(Boolean).length;
    const sigEl = document.getElementById('ind-sig');
    if (met === 5) { sigEl.textContent = '🚀 COMPRA PRONTA'; sigEl.style.cssText = 'background:rgba(0,216,122,.15);color:var(--green);padding:2px 8px;border-radius:8px;font-size:.63rem;font-weight:800'; }
    else if (c.didi_agulhada_sell || (!c.st_bullish && !c.ema50_bull)) { sigEl.textContent = '⚠ VENDA ATIVA'; sigEl.style.cssText = 'background:rgba(255,71,87,.12);color:var(--red);padding:2px 8px;border-radius:8px;font-size:.63rem;font-weight:800'; }
    else if (c.faixa_branca) { sigEl.textContent = '⚡ Faixa Branca'; sigEl.style.cssText = 'background:rgba(255,255,255,.08);color:var(--white);padding:2px 8px;border-radius:8px;font-size:.63rem;font-weight:800'; }
    else { sigEl.textContent = met + '/5 condições'; sigEl.style.cssText = 'color:var(--muted);font-size:.63rem'; }

    const fmt = v => v != null ? '$' + Math.round(v).toLocaleString('en-US') : '–';
    const e50  = pdist(price, c.ema50_val);
    const s200 = pdist(price, c.sma200_val);
    const vwp  = pdist(price, c.vwap_val);
    const ds = c.didi_short_val, dl = c.didi_long_val, vr = c.volume_ratio || 0;
    const rsi = c.rsi_val;
    const rsiPct  = rsi != null ? Math.min(100, rsi) : 0;
    const rsiColor = rsi > 70 ? 'var(--red)' : rsi < 30 ? 'var(--green)' : rsi > 60 ? 'var(--yellow)' : 'var(--blue)';
    const rsiTag  = rsi > 80 ? 'tag-dn' : rsi > 70 ? 'tag-warn' : rsi < 30 ? 'tag-up' : rsi < 40 ? 'tag-up' : 'tag-neu';
    const rsiLbl  = rsi > 80 ? '⚠ Extremo' : rsi > 70 ? '↑ Sobrecomprado' : rsi < 30 ? '↓ Sobrevendido' : rsi < 40 ? '↑ Ótimo' : '✅ Neutro';
    const fb = c.faixa_branca;

    document.getElementById('ind-body').innerHTML = `
    <div class="ind-section">
        <div class="ind-hdr">📈 Médias Móveis</div>
        <div class="ind-row">
            <span class="ind-name" style="color:var(--orange)">EMA 50</span>
            <span class="ind-val">${fmt(c.ema50_val)}</span>
            <span class="ind-tag ${e50.c}">${e50.t}</span>
        </div>
        <div class="ind-row">
            <span class="ind-name" style="color:var(--purple)">SMA 200</span>
            <span class="ind-val">${c.sma200_val != null ? fmt(c.sma200_val) : '– (insuf.)'}</span>
            <span class="ind-tag ${s200.c}">${s200.t}</span>
        </div>
        <div class="ind-row">
            <span class="ind-name" style="color:var(--pink)">VWAP</span>
            <span class="ind-val">${fmt(c.vwap_val)}</span>
            <span class="ind-tag ${vwp.c}">${vwp.t}</span>
        </div>
    </div>
    <div class="ind-section">
        <div class="ind-hdr">📉 RSI (14) — Momentum</div>
        <div class="ind-row">
            <span class="ind-name" style="color:${rsiColor}">RSI(14)</span>
            <span class="ind-val" style="color:${rsiColor}">${rsi != null ? rsi.toFixed(2) : '–'}</span>
            <span class="ind-tag ${rsiTag}">${rsiLbl}</span>
        </div>
        <div class="rsi-bar-wrap">
            <div class="rsi-bar" style="width:${rsiPct}%;background:${rsiColor}"></div>
        </div>
        <div class="rsi-zones"><span>0</span><span>Venda→30</span><span>50</span><span>70←Compra</span><span>100</span></div>
    </div>
    <div class="ind-section">
        <div class="ind-hdr">🎯 Didi Index WDO Master</div>
        <div class="faixa-badge ${fb ? 'fb-setup' : 'fb-normal'}">
            ${fb ? '⚡ FAIXA BRANCA — Agulhada iminente!' : '▓ Faixa Branca ±0.02%: aguardando compressão'}
        </div>
        <div class="ind-row" style="margin-top:2px">
            <span class="ind-name" style="color:var(--blue)">L3 Curta</span>
            <span class="ind-val ${ds != null && ds > 0 ? 'c-green' : 'c-red'}">${ds != null ? (ds >= 0 ? '+' : '') + ds.toFixed(4) + '%' : '–'}</span>
            <span class="ind-tag ${ds != null && ds > dl ? 'tag-up' : 'tag-dn'}">${ds != null && dl != null ? (ds > dl ? 'Acima L20' : 'Abaixo L20') : '–'}</span>
        </div>
        <div class="ind-row">
            <span class="ind-name" style="color:var(--yellow)">L20 Longa</span>
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

// ── Statistics Panel ────────────────────────────────────────────────────────
function updateStats(d) {
    const stats = d.stats || {};
    const wins  = stats.wins   || 0;
    const loss  = stats.losses || 0;
    const total = wins + loss;
    const wr    = total > 0 ? (wins / total * 100) : 0;
    const tpnl  = stats.total_pnl || 0;
    const best  = stats.best  || 0;
    const worst = stats.worst || 0;
    const badge = document.getElementById('stats-badge');
    badge.textContent = total > 0 ? (wr >= 50 ? '✅ Lucrativo' : '⚠ Atenção') : '–';
    badge.style.cssText = total > 0 ? (wr >= 50 ? 'background:rgba(0,216,122,.12);color:var(--green);padding:1px 7px;border-radius:8px' : 'background:rgba(255,212,59,.1);color:var(--yellow);padding:1px 7px;border-radius:8px') : 'color:var(--muted)';
    if (total === 0) {
        document.getElementById('stats-body').innerHTML = '<div class="no-trades">Nenhum trade completado.<br>O robô registra automaticamente cada operação.</div>';
        return;
    }
    const wrColor = wr >= 60 ? 'var(--green)' : wr >= 40 ? 'var(--yellow)' : 'var(--red)';
    const pnlColor = tpnl >= 0 ? 'var(--green)' : 'var(--red)';
    document.getElementById('stats-body').innerHTML = `
    <div class="stats-grid">
        <div class="stat-box">
            <div class="stat-lbl">Win Rate</div>
            <div class="stat-val" style="color:${wrColor}">${wr.toFixed(0)}%</div>
            <div class="stat-sub">${wins}W / ${loss}L</div>
        </div>
        <div class="stat-box">
            <div class="stat-lbl">P&L Total</div>
            <div class="stat-val" style="color:${pnlColor}">${fmtPct(tpnl)}</div>
            <div class="stat-sub">${total} operações</div>
        </div>
        <div class="stat-box">
            <div class="stat-lbl">Melhor Trade</div>
            <div class="stat-val c-green">+${best.toFixed(2)}%</div>
            <div class="stat-sub">maior ganho</div>
        </div>
        <div class="stat-box">
            <div class="stat-lbl">Pior Trade</div>
            <div class="stat-val c-red">${worst.toFixed(2)}%</div>
            <div class="stat-sub">maior perda</div>
        </div>
    </div>
    <div class="progress-wrap">
        <div class="progress-lbl"><span>Taxa de Acerto</span><span style="color:${wrColor}">${wr.toFixed(1)}%</span></div>
        <div class="progress-bar">
            <div class="progress-fill" style="width:${wr}%;background:${wrColor}"></div>
        </div>
    </div>
    <div class="progress-wrap" style="margin-top:4px">
        <div class="progress-lbl"><span>P&L Acumulado</span><span style="color:${pnlColor}">${fmtPct(tpnl)}</span></div>
        <div class="progress-bar">
            <div class="progress-fill" style="width:${Math.min(100, Math.abs(tpnl) * 5)}%;background:${pnlColor}"></div>
        </div>
    </div>`;
}

// ── Trade Log ───────────────────────────────────────────────────────────────
function updateTradeLog(d) {
    const trades = (d.trade_log || []).slice().reverse();
    setEl('trade-count', trades.length + ' trade' + (trades.length !== 1 ? 's' : ''));
    if (trades.length > prevTradeCount && prevTradeCount > 0) {
        const t = trades[0];
        const p = parseFloat(t.price).toLocaleString('en-US', { minimumFractionDigits: 2 });
        if (t.type === 'buy') showToast('▲ COMPRA EXECUTADA!<br>@ $' + p, 'var(--blue)');
        else {
            const s = (t.pnl_pct || 0) >= 0 ? '+' : '';
            showToast('▼ VENDA EXECUTADA<br>$' + p + '&nbsp; P&L: ' + s + (t.pnl_pct || 0).toFixed(2) + '%', t.pnl_pct >= 0 ? 'var(--green)' : 'var(--red)');
        }
    }
    prevTradeCount = trades.length;
    const body = document.getElementById('trade-log');
    if (!trades.length) {
        body.innerHTML = '<div class="no-trades">Nenhuma operação ainda.<br>Aguardando as 5 condições simultâneas.</div>';
        return;
    }
    const reasonLabel = { stop_loss: 'SL', take_profit: 'TP', sinal: 'sinal', manual: 'manual' };
    body.innerHTML = trades.slice(0, 10).map(t => {
        const pnl = t.pnl_pct !== undefined
            ? `<span class="t-pnl ${t.pnl_pct >= 0 ? 'c-green' : 'c-red'}">${fmtPct(t.pnl_pct)}</span>` : '';
        const reason = t.reason ? `<span class="t-reason">[${reasonLabel[t.reason] || t.reason}]</span>` : '';
        return `<div class="trade-row">
            <span class="trade-badge ${t.type === 'buy' ? 'b-buy' : 'b-sell'}">${t.type === 'buy' ? '▲ COMPRA' : '▼ VENDA'}</span>
            <span class="t-price">$${parseFloat(t.price).toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
            ${reason}${pnl}<span class="t-time">${t.datetime || ''}</span>
        </div>`;
    }).join('');
}

// ── Chart Update ─────────────────────────────────────────────────────────────
let _chartInitialized = false;
function updateChart(d) {
    if (!d.history_candles || !d.history_candles.length) return;
    document.getElementById('main-loading').style.display = 'none';

    // Corrige dimensões: o flex layout pode não estar calculado no initCharts()
    const mBox = document.getElementById('main-box');
    const dBox = document.getElementById('didi-box');
    if (mBox.clientHeight > 0) {
        mainChart.resize(mBox.clientWidth, mBox.clientHeight);
        didiChart.resize(dBox.clientWidth, dBox.clientHeight);
    }

    const cs  = d.history_candles.map(c => ({ ...c, time: lt(c.time) }));
    const flt = key => cs.filter(c => c[key] != null).map(c => ({ time: c.time, value: c[key] }));

    candleSeries.setData(cs);
    volS.setData(cs.map(c => ({
        time: c.time, value: c.volume || 0,
        color: c.close >= c.open ? 'rgba(0,216,122,.2)' : 'rgba(255,71,87,.2)'
    })));
    if (flt('sma200').length) sma200S.setData(flt('sma200'));
    if (flt('ema50').length)  ema50S.setData(flt('ema50'));
    if (flt('vwap').length)   vwapS.setData(flt('vwap'));

    const stBull = cs.filter(c => c.st_dir === 1  && c.st_line != null).map(c => ({ time: c.time, value: c.st_line }));
    const stBear = cs.filter(c => c.st_dir === -1 && c.st_line != null).map(c => ({ time: c.time, value: c.st_line }));
    if (stBull.length) stBullS.setData(stBull);
    if (stBear.length) stBearS.setData(stBear);

    const didiShort = cs.filter(c => c.didi_short != null).map(c => ({
        time: c.time, value: c.didi_short,
        color: c.didi_short >= 0 ? 'rgba(61,158,255,.85)' : 'rgba(255,71,87,.75)'
    }));
    const didiLong = cs.filter(c => c.didi_long != null).map(c => ({ time: c.time, value: c.didi_long }));
    if (didiShort.length) didiShortS.setData(didiShort);
    if (didiLong.length)  didiLongS.setData(didiLong);

    const didiMarkers = cs
        .filter(c => c.didi_signal && c.didi_signal !== 0)
        .map(c => ({
            time: c.time,
            position: c.didi_signal === 1 ? 'belowBar' : 'aboveBar',
            color:    c.didi_signal === 1 ? '#3d9eff' : '#ffd43b',
            shape:    c.didi_signal === 1 ? 'arrowUp' : 'arrowDown',
            text:     c.didi_signal === 1 ? '▲' : '▼'
        })).sort((a, b) => a.time - b.time);
    if (didiMarkers.length) didiShortS.setMarkers(didiMarkers);

    const markers = (d.trade_log || []).filter(t => t.time).map(t => ({
        time:     lt(t.time),
        position: t.type === 'buy' ? 'belowBar' : 'aboveBar',
        color:    t.type === 'buy' ? '#3d9eff' : '#ffd43b',
        shape:    t.type === 'buy' ? 'arrowUp' : 'arrowDown',
        text:     t.type === 'buy' ? '▲ COMPRA' : '▼ VENDA'
    })).sort((a, b) => a.time - b.time);
    if (markers.length) candleSeries.setMarkers(markers);

    // Ajusta zoom para mostrar todos os candles na primeira carga
    if (!_chartInitialized) {
        _chartInitialized = true;
        mainChart.timeScale().fitContent();
        didiChart.timeScale().fitContent();
    }
}

// ── Fetch & Update ──────────────────────────────────────────────────────────
async function fetchAndUpdate() {
    try {
        const res  = await fetch('/api/data');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        if (!data) return;
        updateCards(data);
        updateStrip(data);
        updateIndicators(data);
        updateStats(data);
        updateTradeLog(data);
        updateChart(data);
    } catch (e) {
        console.error('Fetch error:', e);
        const el = document.getElementById('main-loading');
        if (el) { el.style.display = 'block'; el.textContent = '❌ ' + e.message; }
    }
}

// ── Manual Controls ─────────────────────────────────────────────────────────
async function sendCommand(cmd) {
    try {
        await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: cmd })
        });
    } catch(e) { console.error('Command error:', e); }
}

function togglePause() {
    const cmd = isPaused ? 'resume' : 'pause';
    sendCommand(cmd).then(() => showToast(isPaused ? '▶ Robô RETOMADO' : '⏸ Robô PAUSADO', 'var(--yellow)'));
}

function forceSell() {
    if (!confirm('⛔ Confirmar FORCE SELL?\\nIsso irá VENDER toda sua posição imediatamente ao preço de mercado.')) return;
    sendCommand('force_sell').then(() => showToast('⛔ FORCE SELL enviado!', 'var(--red)'));
}

// ── Chart Navigation ─────────────────────────────────────────────────────────
function fitChart() {
    mainChart.applyOptions({ rightPriceScale: { autoScale: true } });
    mainChart.timeScale().fitContent();
    didiChart.applyOptions({ rightPriceScale: { autoScale: true } });
    didiChart.timeScale().fitContent();
}
function scrollPrice(direction) {
    mainChart.applyOptions({ rightPriceScale: { autoScale: false } });
    const el = document.getElementById('main-inner');
    const canvas = el.querySelector('canvas');
    if (!canvas) return;
    const rect   = canvas.getBoundingClientRect();
    const axisX  = rect.right - 38;
    const cenY   = rect.top + rect.height / 2;
    const pixels = 55 * direction;
    const opts   = y => ({ bubbles: true, cancelable: true, button: 0, clientX: axisX, clientY: y });
    canvas.dispatchEvent(new MouseEvent('mousedown', opts(cenY)));
    [0.25, 0.5, 0.75, 1].forEach(f => canvas.dispatchEvent(new MouseEvent('mousemove', opts(cenY + pixels * f))));
    canvas.dispatchEvent(new MouseEvent('mouseup', opts(cenY + pixels)));
}
document.getElementById('main-box').addEventListener('wheel', e => {
    if (e.shiftKey) { e.preventDefault(); e.stopPropagation(); scrollPrice(e.deltaY > 0 ? 1 : -1); }
}, { passive: false });
let _oc = false;
document.getElementById('main-box').addEventListener('mouseenter', () => _oc = true);
document.getElementById('main-box').addEventListener('mouseleave', () => _oc = false);
document.addEventListener('keydown', e => {
    if (!_oc) return;
    if (e.key === 'ArrowUp')            { e.preventDefault(); scrollPrice(-1); }
    if (e.key === 'ArrowDown')          { e.preventDefault(); scrollPrice(1); }
    if (e.key === 'f' || e.key === 'F') { e.preventDefault(); fitChart(); }
});

// ── Boot — aguarda browser calcular layout flex antes de criar gráficos ──────
requestAnimationFrame(function() {
    initCharts();
    fetchAndUpdate();
    setInterval(fetchAndUpdate, 3000);
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
    protocol_version = "HTTP/1.1"

    def log_message(self, *args): pass
    def handle_error(self, *_): pass

    def _respond(self, code, content_type, body):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/command':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body   = json.loads(self.rfile.read(length))
                cmd    = body.get('command', '')
                with open(CONTROL_FILE, 'w') as f:
                    json.dump({'command': cmd}, f)
                self._respond(200, 'application/json', json.dumps({'ok': True}))
            except Exception as e:
                self._respond(500, 'application/json', json.dumps({'error': str(e)}))

    def do_GET(self):

        if self.path in ('/api/data', '/api/state'):

            # ── 1. Estado do bot (fonte primária: atualizado pelo bot a cada 4s) ──
            current_price   = 0.0
            position_status = None
            entry_price     = 0.0
            trade_log       = []
            stats           = {}
            usdt_balance    = 0.0
            btc_balance     = 0.0
            paused          = False
            last_update_ts  = 0
            uptime_start    = 0

            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, 'r') as f:
                        raw = f.read()
                    bj = json.loads(raw)
                    current_price   = float(bj.get("current_price") or 0)
                    position_status = bj.get("position")
                    entry_price     = float(bj.get("entry_price") or 0)
                    trade_log       = bj.get("trade_log", [])
                    stats           = bj.get("stats", {})
                    usdt_balance    = float(bj.get("usdt_balance") or 0)
                    btc_balance     = float(bj.get("btc_balance") or 0)
                    paused          = bool(bj.get("paused", False))
                    uptime_start    = int(bj.get("uptime_start") or 0)
                    last_update_ts  = int(bj.get("last_update_ts") or 0)
                except Exception as e:
                    print(f"[API] Erro lendo state: {e}")

            # ── 2. Candles da exchange (única chamada — sem fetch_ticker separado) ──
            candles_list = []
            conditions   = {}

            try:
                ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=250)
                df    = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                df    = apply_indicators(df)

                # Usa close do último candle se bot ainda não atualizou o preço
                close_last = float(df.iloc[-1]['close'])
                if current_price == 0:
                    current_price = close_last

                last = df.iloc[-1]

                ema50_v   = _f(last['ema50'])
                sma200_v  = _f(last['sma200'])
                vwap_v    = _f(last['vwap'])
                ds_v      = _f(last['didi_short'])
                dl_v      = _f(last['didi_long'])
                st_dir_v  = _f(last['st_dir'])
                st_line_v = _f(last['st_line'])
                rsi_v     = _f(last['rsi'])
                vol_mean  = _f(last['vol_mean']) or 0
                vol_cur   = float(last['volume'])
                price_ref = current_price or close_last

                st_bull      = st_dir_v == 1.0 if st_dir_v is not None else False
                ema_bull     = (price_ref > ema50_v) if ema50_v else False
                didi_buy     = (ds_v > dl_v and ds_v > 0) if (ds_v is not None and dl_v is not None) else False
                didi_sell    = (ds_v < dl_v and ds_v < 0) if (ds_v is not None and dl_v is not None) else False
                vol_ok       = (vol_cur >= vol_mean * 1.2) if vol_mean > 0 else False
                vol_ratio    = round(vol_cur / vol_mean, 3) if vol_mean > 0 else 0
                rsi_ok       = (rsi_v < 70) if rsi_v is not None else False
                rsi_extreme  = (rsi_v > 80) if rsi_v is not None else False
                faixa_branca = (abs(ds_v) <= 0.02 and abs(dl_v) <= 0.02) if (ds_v is not None and dl_v is not None) else False

                conditions = {
                    "st_bullish":         st_bull,
                    "ema50_bull":         ema_bull,
                    "didi_agulhada_buy":  didi_buy,
                    "didi_agulhada_sell": didi_sell,
                    "volume_ok":          vol_ok,
                    "rsi_ok":             rsi_ok,
                    "rsi_extreme":        rsi_extreme,
                    "faixa_branca":       faixa_branca,
                    "volume_ratio":       vol_ratio,
                    "didi_short_val":     ds_v,
                    "didi_long_val":      dl_v,
                    "ema50_val":          ema50_v,
                    "sma200_val":         sma200_v,
                    "vwap_val":           vwap_v,
                    "rsi_val":            rsi_v,
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
                        "rsi":         _f(r['rsi']),
                    })

            except Exception as e:
                print(f"[API] Erro candles: {e}")

            self._respond(200, 'application/json', json.dumps({
                "current_price":   current_price,
                "position":        position_status,
                "entry_price":     entry_price,
                "conditions":      conditions,
                "history_candles": candles_list,
                "trade_log":       trade_log,
                "stats":           stats,
                "usdt_balance":    usdt_balance,
                "btc_balance":     btc_balance,
                "paused":          paused,
                "last_update_ts":  last_update_ts,
                "uptime_start":    uptime_start,
            }))

        elif self.path in ('/', '/index.html'):
            self._respond(200, 'text/html; charset=utf-8', HTML_CONTENT)

        else:
            self._respond(404, 'text/plain', 'Not Found')


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'w') as f:
            json.dump({
                "position": None, "entry_price": 0.0,
                "last_candle_time": 0, "trade_log": [],
                "stats": {"wins": 0, "losses": 0, "total_pnl": 0.0, "best": 0.0, "worst": 0.0},
                "paused": False, "usdt_balance": 0.0, "btc_balance": 0.0
            }, f)

    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadedHTTPServer(('0.0.0.0', 8080), DashboardHandler)
    print("=" * 60)
    print("  NEXUS BTC — Dashboard v2.0")
    print("  Acesse: http://localhost:8080")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard encerrado.")
