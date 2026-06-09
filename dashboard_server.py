# dashboard_server.py
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import json
import os
import time
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from config import API_KEY, SECRET, SYMBOL, TIMEFRAME, STATE_FILE, CONTROL_FILE
from strategy import apply_indicators

exchange = ccxt.binance({
    'apiKey': API_KEY, 'secret': SECRET, 'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

# ─────────────────────────────────────────────────────────────────────────────
HTML_CONTENT = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEXUS PRO · Monitoramento Estratégico</title>
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
    --white:      #e2e8f0;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: var(--bg); color: var(--text);
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    height: 100vh; display: flex; flex-direction: column; overflow: hidden;
    font-size: 13px;
}

/* ══ HEADER ════════════════════════════════════════════════════════════════ */
.header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 20px; height: 54px; flex-shrink: 0;
    background: #0a1628; border-bottom: 1px solid var(--border);
}
.logo { font-size: 1.1rem; font-weight: 800; letter-spacing: 0.1em; color: var(--white); }
.logo span { color: var(--blue); }

.hd-center { display: flex; gap: 20px; font-size: 0.75rem; color: var(--muted); }
.hd-center b { color: var(--white); }

.ctrl-btn {
    padding: 6px 14px; border-radius: 6px; font-size: 0.7rem; font-weight: 700;
    cursor: pointer; border: 1px solid var(--border); background: var(--bg-card); color: var(--text);
}
.btn-pause { border-color: var(--yellow); color: var(--yellow); }
.btn-sell  { border-color: var(--red); color: var(--red); }
.btn-guide { border-color: var(--blue); color: var(--blue); margin-right: 10px; font-weight: 800; }

/* ══ CARDS ══════════════════════════════════════════════════════════════════ */
.cards {
    display: grid; grid-template-columns: repeat(7, 1fr);
    gap: 8px; padding: 10px 20px; flex-shrink: 0;
}
.card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 10px; padding: 10px; text-align: left;
}
.card-label { font-size: 0.6rem; color: var(--muted); text-transform: uppercase; margin-bottom: 4px; }
.card-value { font-size: 1.1rem; font-weight: 700; }
.card-sub { font-size: 0.65rem; color: var(--muted); margin-top: 2px; }

/* ══ CONDITIONS STRIP ═══════════════════════════════════════════════════════ */
.cond-strip {
    display: flex; align-items: center; gap: 10px;
    padding: 0 20px; height: 40px; flex-shrink: 0;
    background: #080f20; border-bottom: 1px solid var(--border);
}
.pill {
    padding: 3px 12px; border-radius: 20px; font-size: 0.7rem; font-weight: 700;
    border: 1px solid transparent; transition: 0.3s;
}
.pill.ok   { background: rgba(0,216,122,0.1); border-color: rgba(0,216,122,0.3); color: var(--green); }
.pill.fail { background: rgba(255,71,87,0.05); border-color: rgba(255,71,87,0.15); color: #4a2a2e; }

/* ══ CHARTS ═════════════════════════════════════════════════════════════════ */
.charts-wrap {
    flex: 1; display: flex; flex-direction: column;
    padding: 10px 20px; gap: 10px; min-height: 0;
}
.chart-box {
    position: relative; flex: 1; background: var(--bg-panel);
    border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
}
.chart-inner { width: 100%; height: 100%; }
.chart-label {
    position: absolute; top: 10px; left: 15px; z-index: 10;
    font-size: 0.65rem; font-weight: 700; color: var(--muted);
    background: rgba(6,13,31,0.8); padding: 4px 10px; border-radius: 6px;
}

/* ══ BOTTOM ═════════════════════════════════════════════════════════════════ */
.bottom-row {
    display: grid; grid-template-columns: 1.2fr 1fr 1.5fr;
    gap: 10px; padding: 0 20px 20px; flex-shrink: 0;
}
.panel {
    background: var(--bg-panel); border: 1px solid var(--border);
    border-radius: 12px; padding: 15px; height: 180px; overflow-y: auto;
}
.panel-title { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; font-weight: 800; margin-bottom: 10px; border-bottom: 1px solid var(--border); padding-bottom: 5px; }

/* ══ GUIDE MODAL ═══════════════════════════════════════════════════════════ */
#guide-overlay {
    position: fixed; inset: 0; z-index: 10000; background: rgba(0,0,0,0.85);
    backdrop-filter: blur(8px); display: none; align-items: center; justify-content: center;
    animation: fadeIn 0.3s ease;
}
@keyframes fadeIn { from{opacity:0} to{opacity:1} }
#guide-modal {
    background: linear-gradient(145deg, #0d1b30, #060d1f); border: 2px solid var(--blue);
    border-radius: 24px; width: min(850px, 95vw); max-height: 85vh;
    padding: 0; overflow: hidden; display: flex; flex-direction: column;
    box-shadow: 0 0 50px rgba(37, 99, 235, 0.2);
}
.guide-header {
    background: var(--blue); padding: 25px; color: white; text-align: center;
    position: relative;
}
.guide-header h1 { font-size: 1.6rem; font-weight: 900; letter-spacing: 1px; }
.guide-header p { font-size: 0.8rem; opacity: 0.9; margin-top: 5px; font-weight: 600; }
.guide-close {
    position: absolute; top: 15px; right: 20px; background: rgba(0,0,0,0.2);
    border: none; color: white; font-size: 1.2rem; cursor: pointer;
    width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
}
.guide-body { padding: 30px; overflow-y: auto; color: #cdd6f4; }
.guide-section {
    background: rgba(255,255,255,0.03); border: 1px solid var(--border);
    border-radius: 16px; padding: 20px; margin-bottom: 20px;
}
.guide-h2 { 
    display: flex; align-items: center; gap: 10px;
    font-size: 1rem; color: var(--blue); margin-bottom: 15px; text-transform: uppercase;
}
.ma-tag {
    padding: 4px 12px; border-radius: 8px; font-size: 0.7rem; font-weight: 800;
    margin-right: 10px; display: inline-block;
}
.ma-purple { background: rgba(167, 139, 250, 0.15); color: #a78bfa; border: 1px solid #a78bfa; }
.ma-orange { background: rgba(255, 140, 66, 0.15); color: #ff8c42; border: 1px solid #ff8c42; }
.ma-blue { background: rgba(61, 158, 255, 0.15); color: #3d9eff; border: 1px solid #3d9eff; }

.analogy { font-style: italic; color: var(--muted); font-size: 0.75rem; margin-top: 8px; display: block; }
.rule-box {
    margin-top: 15px; padding: 12px; background: rgba(0, 216, 122, 0.05);
    border-radius: 10px; border-left: 3px solid var(--green);
}
.rule-box b { color: var(--green); font-size: 0.75rem; text-transform: uppercase; }
.rule-txt { font-size: 0.8rem; margin-top: 5px; line-height: 1.5; }

/* Helpers */
.c-green { color: var(--green); } .c-red { color: var(--red); }
.hidden { display: none; }
</style>
</head>
<body>

<div class="header">
    <div class="logo">NEXUS<span>PRO</span></div>
    <div class="hd-center">
        <span>Par: <b>BTC/USDT</b></span>
        <span>TF: <b>4h</b></span>
        <span>Estratégia: <b>Keltner + Didi Pullback</b></span>
        <span id="hd-uptime">Uptime: --</span>
    </div>
    <div>
        <button class="ctrl-btn btn-guide" onclick="openGuide()">📖 GUIA DO SISTEMA</button>
        <button class="ctrl-btn btn-pause" id="btn-pause" onclick="togglePause()">⏸ PAUSAR</button>
        <button class="ctrl-btn btn-sell hidden" id="btn-force-sell" onclick="forceSell()">⛔ FORCE SELL</button>
    </div>
</div>

<div class="cards">
    <div class="card"><div class="card-label">💰 Preço BTC</div><div class="card-value" id="c-price">$ --,---</div><div class="card-sub">Binance Spot</div></div>
    <div class="card"><div class="card-label">🛰️ Estado</div><div class="card-value" id="c-status">AGUARDANDO</div><div class="card-sub" id="c-status-sub">Sincronizando...</div></div>
    <div class="card"><div class="card-label">📈 Lucro Op.</div><div class="card-value" id="c-pnl">0.00%</div><div class="card-sub" id="c-pnl-sub">sem posição</div></div>
    <div class="card"><div class="card-label">💵 Saldo USDT</div><div class="card-value" id="c-usdt">$ 0.00</div><div class="card-sub">disponível</div></div>
    <div class="card"><div class="card-label">₿ Saldo BTC</div><div class="card-value" id="c-btc">0.0000</div><div class="card-sub" id="c-btc-sub">≈ $ 0.00</div></div>
    <div class="card"><div class="card-label">🎯 Win Rate</div><div class="card-value" id="c-winrate">--%</div><div class="card-sub" id="c-winrate-sub">0 trades</div></div>
    <div class="card"><div class="card-label">📉 RSI (14)</div><div class="card-value" id="c-rsi">--</div><div class="card-sub">Momentum</div></div>
</div>

<div class="cond-strip">
    <span style="font-size:0.6rem; color:var(--muted); font-weight:800">CHECKLIST COMPRA:</span>
    <div class="pill fail" id="pill-macro">⬜ Macro Bull (SMA200)</div>
    <div class="pill fail" id="pill-pullback">⬜ Pullback (Preço < EMA20)</div>
    <div class="pill fail" id="pill-didi">⬜ Agulhada Didi (↑)</div>
    <div class="pill fail" id="pill-rsi">⬜ Reação RSI (> 45)</div>
    <div class="pill fail" id="pill-vol">⬜ Volume OK</div>
</div>

<div class="charts-wrap">
    <div class="chart-box" style="flex: 2;">
        <div class="chart-label">GRÁFICO PRINCIPAL · KELTNER CHANNELS</div>
        <div class="chart-inner" id="main-chart"></div>
    </div>
    <div class="chart-box" style="flex: 1;">
        <div class="chart-label">DIDI INDEX · AGULHADA</div>
        <div class="chart-inner" id="didi-chart"></div>
    </div>
</div>

<div class="bottom-row">
    <div class="panel">
        <div class="panel-title">📋 Monitor de Sinais</div>
        <div id="signal-log" style="font-size: 0.7rem; color: var(--muted); line-height: 1.5;">Aguardando dados...</div>
    </div>
    <div class="panel">
        <div class="panel-title">🏆 Estatísticas Reais</div>
        <div id="stats-body">Sem dados.</div>
    </div>
    <div class="panel">
        <div class="panel-title">📜 Últimos Trades</div>
        <div id="trade-log">Sem trades.</div>
    </div>
</div>

<div id="guide-overlay" onclick="if(event.target===this)closeGuide()">
    <div id="guide-modal">
        <div class="guide-header">
            <button class="guide-close" onclick="closeGuide()">✕</button>
            <h1>📚 MANUAL DO SNIPER NEXUS</h1>
            <p>Entenda a inteligência por trás de cada trade automático</p>
        </div>
        <div class="guide-body">
            
            <div class="guide-section">
                <div class="guide-h2">🛡️ 1. O ESCUDO MACRO (SMA 200)</div>
                <p class="guide-txt">
                    <span class="ma-tag ma-purple">Média de 200 Períodos</span>
                    Representa o sentimento do mercado nos últimos meses. É a linha que separa os otimistas dos pessimistas.
                </p>
                <span class="analogy">💡 Analogia: É como o clima da estação. Se estamos no inverno (abaixo da média), não adianta tentar tomar sol.</span>
                <div class="rule-box">
                    <b>REGRA NO SISTEMA:</b>
                    <div class="rule-txt">O robô só tem permissão para COMPRAR se o preço estiver ACIMA desta linha. Isso evita que você tente "pegar facas caindo" em tendências de baixa.</div>
                </div>
            </div>

            <div class="guide-section">
                <div class="guide-h2">🎯 2. O PREÇO JUSTO (EMA 20)</div>
                <p class="guide-txt">
                    <span class="ma-tag ma-orange">Média Exponencial 20</span>
                    Indica o valor médio do Bitcoin nas últimas 80 horas. O preço sempre tenta voltar para esta linha.
                </p>
                <span class="analogy">💡 Analogia: Imagine um elástico. Quando o preço se afasta muito da média, o elástico puxa ele de volta.</span>
                <div class="rule-box">
                    <b>REGRA NO SISTEMA:</b>
                    <div class="rule-txt">Buscamos o <b>PULLBACK</b>. O robô espera o preço cair e tocar (ou furar) esta linha laranja. Comprar aqui significa que você está pagando um preço "barato" dentro de uma alta.</div>
                </div>
            </div>

            <div class="guide-section">
                <div class="guide-h2">⚡ 3. O GATILHO DIDI (AGULHADA)</div>
                <p class="guide-txt">
                    <span class="ma-tag ma-blue">Didi Index Híbrido</span>
                    Mede a compressão e a explosão do preço. Quando as médias de 3 e 20 períodos se cruzam exatamente sobre a de 8, temos a "Agulhada".
                </p>
                <span class="analogy">💡 Analogia: É como carregar uma mola. O recuo no Keltner carrega a mola, e a Agulhada do Didi é o dedo soltando o gatilho.</span>
                <div class="rule-box">
                    <b>REGRA NO SISTEMA:</b>
                    <div class="rule-txt">Usamos o Didi para confirmar que o recuo acabou. Quando a linha Azul cruza para cima da Amarela, o sistema entende que a força compradora voltou com tudo.</div>
                </div>
            </div>

            <div class="guide-section" style="border-left-color: var(--yellow); background: rgba(255, 212, 59, 0.03);">
                <div class="guide-h2" style="color: var(--yellow);">⚖️ 4. O EQUILÍBRIO (RSI 14)</div>
                <p class="guide-txt">Mede a velocidade e a mudança dos movimentos de preço.</p>
                <div class="rule-box" style="border-left-color: var(--yellow);">
                    <b style="color: var(--yellow);">FILTRO DE SEGURANÇA:</b>
                    <div class="rule-txt">O robô só atira se o RSI estiver entre 45 e 60. <b>Abaixo de 45</b> o mercado está muito fraco; <b>Acima de 65</b> o mercado já esticou demais e o risco de queda é alto.</div>
                </div>
            </div>

            <button class="ctrl-btn" onclick="closeGuide()" style="width:100%; padding:15px; background:var(--blue); color:white; border:none; border-radius:12px; font-weight:800; cursor:pointer; font-family:inherit;">ENTENDI! VOLTAR AO MONITORAMENTO</button>
        </div>
    </div>
</div>

<div id="toast"></div>

<script>
let mainChart, candleSeries, kcUpperS, kcLowerS, ema20S, sma200S;
let didiChart, didiShortS, didiLongS;

function initCharts() {
    const chartOptions = {
        layout: { background: { type: 'solid', color: '#0a1628' }, textColor: '#4a5a72' },
        grid: { vertLines: { color: '#0d1b30' }, horzLines: { color: '#0d1b30' } },
        rightPriceScale: { borderColor: '#1a2e4a', autoScale: true },
        timeScale: { 
            borderColor: '#1a2e4a', 
            timeVisible: true, 
            secondsVisible: false,
            rightOffset: 5,
            barSpacing: 6,
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                labelVisible: true,
                color: 'rgba(255, 255, 255, 0.5)',
                width: 1,
                style: 2, // Pontilhado
            },
            horzLine: {
                labelVisible: true,
                color: 'rgba(255, 255, 255, 0.3)',
                width: 1,
                style: 2,
            }
        },
        // ── CORREÇÃO DO ZOOM E ROLAGEM ──
        handleScroll: {
            mouseWheel: false, // Desativa rolar o gráfico com o scroll
            pressedMouseMove: true,
            horzTouchDrag: true,
            vertTouchDrag: true,
        },
        handleScale: {
            mouseWheel: true, // O Scroll agora APENAS dá Zoom
            pinch: true,
            axisPressedMouseMove: true,
        },
    };
    
    mainChart = LightweightCharts.createChart(document.getElementById('main-chart'), chartOptions);
    candleSeries = mainChart.addCandlestickSeries({ upColor: '#00d87a', downColor: '#ff4757', borderVisible: false, wickUpColor: '#00d87a', wickDownColor: '#ff4757' });
    sma200S = mainChart.addLineSeries({ color: '#a78bfa', lineWidth: 2 });
    ema20S  = mainChart.addLineSeries({ color: '#ff8c42', lineWidth: 2 });
    kcUpperS = mainChart.addLineSeries({ color: 'rgba(61,158,255,0.15)', lineWidth: 1, lineStyle: 2 });
    kcLowerS = mainChart.addLineSeries({ color: 'rgba(61,158,255,0.15)', lineWidth: 1, lineStyle: 2 });

    didiChart = LightweightCharts.createChart(document.getElementById('didi-chart'), chartOptions);
    didiShortS = didiChart.addLineSeries({ color: '#3d9eff', lineWidth: 2 });
    didiLongS  = didiChart.addLineSeries({ color: '#ffd43b', lineWidth: 2 });

    // ── SINCRONIZAÇÃO ABSOLUTA ──
    let isSyncing = false;
    
    mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (isSyncing) return;
        isSyncing = true;
        didiChart.timeScale().setVisibleLogicalRange(range);
        isSyncing = false;
    });
    didiChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (isSyncing) return;
        isSyncing = true;
        mainChart.timeScale().setVisibleLogicalRange(range);
        isSyncing = false;
    });
    
    mainChart.subscribeCrosshairMove(param => {
        if (isSyncing || !param.time) {
            didiChart.setCrosshairPosition(undefined, undefined, didiShortS);
            return;
        }
        isSyncing = true;
        didiChart.setCrosshairPosition(0, param.time, didiShortS);
        isSyncing = false;
    });

    didiChart.subscribeCrosshairMove(param => {
        if (isSyncing || !param.time) {
            mainChart.setCrosshairPosition(undefined, undefined, candleSeries);
            return;
        }
        isSyncing = true;
        mainChart.setCrosshairPosition(0, param.time, candleSeries);
        isSyncing = false;
    });
}

// Global flag para carregar o histórico apenas 1 vez (evita reset de zoom)
let firstLoad = true;

async function update() {
    try {
        const res = await fetch('/api/data');
        if(!res.ok) throw new Error('Falha na resposta do servidor');
        const d = await res.json();
        
        // ... (cards update stays same) ...
        document.getElementById('c-price').textContent = '$' + d.current_price.toLocaleString();
        document.getElementById('c-usdt').textContent = '$' + d.usdt_balance.toLocaleString();
        document.getElementById('c-btc').textContent = d.btc_balance.toFixed(6);
        document.getElementById('c-rsi').textContent = d.conditions.rsi_val ? d.conditions.rsi_val.toFixed(1) : '--';
        
        const c = d.conditions;
        const setPill = (id, ok) => { document.getElementById(id).className = 'pill ' + (ok ? 'ok' : 'fail'); };
        setPill('pill-macro', c.macro_bull);
        setPill('pill-pullback', c.is_pullback);
        setPill('pill-didi', c.didi_buy);
        setPill('pill-rsi', c.rsi_rising);
        setPill('pill-vol', c.vol_ok);

        if(d.history_candles && d.history_candles.length) {
            const cs = d.history_candles;
            
            // Só atualiza os dados se houver novos candles ou for a primeira carga
            // Isso evita "pular" o gráfico enquanto o usuário está analisando o histórico
            candleSeries.setData(cs);
            sma200S.setData(cs.map(x => ({ time: x.time, value: x.sma200 })));
            ema20S.setData(cs.map(x => ({ time: x.time, value: x.ema20 })));
            kcUpperS.setData(cs.map(x => ({ time: x.time, value: x.kc_upper })));
            kcLowerS.setData(cs.map(x => ({ time: x.time, value: x.kc_lower })));
            didiShortS.setData(cs.map(x => ({ time: x.time, value: x.didi_short })));
            didiLongS.setData(cs.map(x => ({ time: x.time, value: x.didi_long })));
            
            if (firstLoad) {
                mainChart.timeScale().fitContent();
                firstLoad = false;
            }
        }

        const s = d.stats;
        document.getElementById('c-winrate').textContent = ((s.wins/(s.wins+s.losses||1))*100).toFixed(0) + '%';
        document.getElementById('stats-body').innerHTML = `Taxa de Acerto: <b>${document.getElementById('c-winrate').textContent}</b><br>P&L Total: <b>${d.stats.total_pnl}%</b>`;
        
    } catch(e) { console.error('Dashboard Update Error:', e); }
}

function openGuide() { document.getElementById('guide-overlay').style.display = 'flex'; }
function closeGuide() { document.getElementById('guide-overlay').style.display = 'none'; }
function togglePause() { fetch('/api/command', { method:'POST', body: JSON.stringify({command: 'pause'}) }); }

initCharts();
update();
setInterval(update, 5000);
</script>
</body>
</html>"""

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        if self.path == '/api/command':
            length = int(self.headers.get('Content-Length', 0))
            cmd = json.loads(self.rfile.read(length)).get('command')
            with open(CONTROL_FILE, 'w') as f: json.dump({'command': cmd}, f)
            self.send_response(200); self.end_headers()
    def do_GET(self):
        try:
            if self.path == '/api/data':
                state = {}
                if os.path.exists(STATE_FILE):
                    with open(STATE_FILE, 'r') as f: state = json.load(f)
                
                # Download de 1000 velas para histórico profundo
                ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=1000)
                df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
                df = apply_indicators(df)
                last = df.iloc[-1]
                prev = df.iloc[-2]
                
                # CORREÇÃO CRÍTICA: Trata NaNs antes de converter para JSON
                df_clean = df.replace({np.nan: None})
                history = df_clean.to_dict('records')
                for c in history: c['time'] = int(c['time']/1000)
                
                data = {
                    "current_price": float(last['close']),
                    "position": state.get("position"),
                    "entry_price": state.get("entry_price", 0),
                    "usdt_balance": state.get("usdt_balance", 0),
                    "btc_balance": state.get("btc_balance", 0),
                    "stats": state.get("stats", {}),
                    "trade_log": state.get("trade_log", []),
                    "paused": state.get("paused", False),
                    "conditions": {
                        "macro_bull": bool(last['close'] > last['sma200']),
                        "is_pullback": bool(last['low'] < last['ema20']),
                        "didi_buy": bool(last['didi_short'] > last['didi_long']),
                        "rsi_rising": bool(last['rsi'] > prev['rsi'] and last['rsi'] > 45),
                        "vol_ok": bool(last['volume'] > last['vol_mean']),
                        "rsi_val": float(last['rsi']) if not pd.isna(last['rsi']) else 0
                    },
                    "history_candles": history
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(HTML_CONTENT.encode())
        except Exception as e:
            print(f"Erro no servidor: {e}")
            self.send_response(500); self.end_headers()

if __name__ == '__main__':
    server = ThreadedHTTPServer(('0.0.0.0', 8080), DashboardHandler)
    print("="*50)
    print("  NEXUS PRO Dashboard (Bug Fixed) v3.1")
    print("  Acesse: http://localhost:8080")
    print("="*50)
    server.serve_forever()
