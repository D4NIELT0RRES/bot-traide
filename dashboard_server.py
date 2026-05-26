"""
Dashboard em tempo real para monitorar o bot de Bitcoin.
Rode em paralelo com o bot.py:
  python dashboard_server.py
Acesse: http://localhost:8080
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import json
import threading
import time
import os
from datetime import datetime
import ccxt
import pandas as pd
from config import API_KEY, SECRET, SYMBOL, TIMEFRAME, STOP_LOSS, TAKE_PROFIT, TRADE_AMOUNT_USDT
from strategy import apply_indicators, generate_signal

# ─────────────────────────────────────────────
# EXCHANGE (somente leitura — sem criar ordens)
# ─────────────────────────────────────────────
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

BASE_ASSET = SYMBOL.split('/')[0]   # BTC
QUOTE_ASSET = SYMBOL.split('/')[1]  # USDT

# ─────────────────────────────────────────────
# ESTADO GLOBAL (thread-safe)
# ─────────────────────────────────────────────
state = {
    "price": 0,
    "rsi": 0,
    "sma50": 0,
    "signal": "hold",
    "position": False,
    "entry_price": 0,
    "pnl_pct": 0,
    "pnl_usdt": 0,
    "stop_loss_price": 0,
    "take_profit_price": 0,
    "usdt_balance": 0,
    "btc_balance": 0,
    "last_update": "",
    "log": [],
    "status": "🔄 Iniciando...",
    "volume": 0,
    "vol_mean": 0,
    "trade_amount_usdt": TRADE_AMOUNT_USDT,
    "stop_loss_pct": (1 - STOP_LOSS) * 100,
    "take_profit_pct": (TAKE_PROFIT - 1) * 100,
}
state_lock = threading.Lock()

# Rastreamento interno
_last_position_state = None   # True / False
_entry_price_cache = 0        # Preço de entrada rastreado


def log_event(msg: str):
    """Adiciona evento ao log com timestamp."""
    ts = datetime.now().strftime("%H:%M:%S")
    entry = {"time": ts, "msg": msg}
    with state_lock:
        state["log"].insert(0, entry)   # mais recente no topo
        if len(state["log"]) > 50:      # mantém só os últimos 50
            state["log"].pop()


def get_entry_price_from_orders() -> float:
    """Busca o preço médio da última ordem de compra executada."""
    try:
        orders = exchange.fetch_my_trades(SYMBOL, limit=20)
        # Procura a compra mais recente
        for trade in reversed(orders):
            if trade['side'] == 'buy':
                return float(trade['price'])
    except Exception:
        pass
    return 0


def fetch_state():
    """Atualiza o estado global com dados frescos da exchange."""
    global _last_position_state, _entry_price_cache

    try:
        # ── Preço atual ──────────────────────────────
        ticker = exchange.fetch_ticker(SYMBOL)
        price = float(ticker['last'])

        # ── Saldo ────────────────────────────────────
        balance = exchange.fetch_balance()
        btc_bal  = float(balance[BASE_ASSET]['free'])
        usdt_bal = float(balance[QUOTE_ASSET]['free'])

        has_pos = btc_bal > 0.00001

        # ── Detecta mudança de posição ────────────────
        if _last_position_state is False and has_pos:
            # Acabou de comprar
            _entry_price_cache = get_entry_price_from_orders() or price
            log_event(f"🟢 COMPRA detectada @ ${_entry_price_cache:,.2f}")

        elif _last_position_state is True and not has_pos:
            # Acabou de vender
            if _entry_price_cache > 0:
                pnl = (price - _entry_price_cache) / _entry_price_cache * 100
                emoji = "🎯" if pnl >= 0 else "🛑"
                log_event(f"{emoji} VENDA detectada @ ${price:,.2f} | P&L: {pnl:+.2f}%")
            else:
                log_event(f"🔴 VENDA detectada @ ${price:,.2f}")
            _entry_price_cache = 0

        _last_position_state = has_pos

        # Garante entry price ao iniciar com posição aberta
        if has_pos and _entry_price_cache == 0:
            _entry_price_cache = get_entry_price_from_orders() or price
            log_event(f"📌 Posição existente detectada @ ${_entry_price_cache:,.2f}")

        # ── Indicadores ──────────────────────────────
        ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        df = apply_indicators(df)
        signal = generate_signal(df)
        last   = df.iloc[-1]
        rsi    = float(last['rsi'])    if not pd.isna(last['rsi'])    else 0
        sma50  = float(last['sma50'])  if not pd.isna(last['sma50'])  else 0
        vol    = float(last['volume'])
        vm     = float(last['vol_mean']) if not pd.isna(last['vol_mean']) else 0

        # ── P&L ──────────────────────────────────────
        entry  = _entry_price_cache
        pnl_pct  = ((price - entry) / entry * 100) if (has_pos and entry > 0) else 0
        pnl_usdt = (price - entry) * btc_bal        if (has_pos and entry > 0) else 0
        sl_price = entry * STOP_LOSS    if (has_pos and entry > 0) else 0
        tp_price = entry * TAKE_PROFIT  if (has_pos and entry > 0) else 0

        # ── Grava estado ─────────────────────────────
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with state_lock:
            state.update({
                "price": price,
                "rsi": rsi,
                "sma50": sma50,
                "signal": signal,
                "position": has_pos,
                "entry_price": entry,
                "pnl_pct": pnl_pct,
                "pnl_usdt": pnl_usdt,
                "stop_loss_price": sl_price,
                "take_profit_price": tp_price,
                "usdt_balance": usdt_bal,
                "btc_balance": btc_bal,
                "last_update": now,
                "volume": vol,
                "vol_mean": vm,
                "status": "✅ Online",
            })

    except Exception as e:
        with state_lock:
            state["status"] = f"⚠️ Erro: {e}"
        log_event(f"⚠️ Erro ao atualizar: {e}")


# ─────────────────────────────────────────────
# ORDENS MANUAIS
# ─────────────────────────────────────────────
def manual_buy() -> dict:
    """Executa uma compra de mercado manual."""
    global _entry_price_cache
    try:
        price      = float(exchange.fetch_ticker(SYMBOL)['last'])
        balance    = exchange.fetch_balance()
        usdt_bal   = float(balance[QUOTE_ASSET]['free'])

        if usdt_bal < TRADE_AMOUNT_USDT:
            msg = f"❌ Saldo USDT insuficiente ({usdt_bal:.2f} USDT disponível)"
            log_event(msg)
            return {"ok": False, "msg": msg}

        amount = (TRADE_AMOUNT_USDT * 0.999) / price
        amount = float(exchange.amount_to_precision(SYMBOL, amount))

        order = exchange.create_market_buy_order(SYMBOL, amount)
        _entry_price_cache = price
        msg = f"🟢 COMPRA MANUAL executada @ ${price:,.2f} | {amount:.6f} BTC"
        log_event(msg)
        # Atualiza estado em background para não bloquear a resposta HTTP
        threading.Thread(target=fetch_state, daemon=True).start()
        return {"ok": True, "msg": msg}

    except Exception as e:
        msg = f"❌ Erro na compra manual: {e}"
        log_event(msg)
        return {"ok": False, "msg": msg}


def manual_sell() -> dict:
    """Executa uma venda de mercado manual (vende tudo)."""
    global _entry_price_cache
    try:
        balance   = exchange.fetch_balance()
        btc_bal   = float(balance[BASE_ASSET]['free'])

        if btc_bal <= 0.00001:
            msg = "❌ Sem BTC para vender"
            log_event(msg)
            return {"ok": False, "msg": msg}

        amount = float(exchange.amount_to_precision(SYMBOL, btc_bal))
        price  = float(exchange.fetch_ticker(SYMBOL)['last'])
        order  = exchange.create_market_sell_order(SYMBOL, amount)

        pnl_pct = ((price - _entry_price_cache) / _entry_price_cache * 100) if _entry_price_cache > 0 else 0
        msg = f"🔴 VENDA MANUAL executada @ ${price:,.2f} | P&L: {pnl_pct:+.2f}%"
        log_event(msg)
        _entry_price_cache = 0
        # Atualiza estado em background para não bloquear a resposta HTTP
        threading.Thread(target=fetch_state, daemon=True).start()
        return {"ok": True, "msg": msg}

    except Exception as e:
        msg = f"❌ Erro na venda manual: {e}"
        log_event(msg)
        return {"ok": False, "msg": msg}


# ─────────────────────────────────────────────
# THREAD DE ATUALIZAÇÃO
# ─────────────────────────────────────────────
def updater_loop():
    while True:
        fetch_state()
        time.sleep(15)   # atualiza a cada 15 segundos


# ─────────────────────────────────────────────
# HTML DASHBOARD (embutido)
# ─────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ BTC Bot — Live Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

:root{
  --bg:#060d18;
  --surface:#0b1422;
  --surface2:#101d30;
  --border:#16263d;
  --border2:#1e3350;
  --green:#00e5b0;
  --green-dim:rgba(0,229,176,.10);
  --green-glow:rgba(0,229,176,.25);
  --red:#ff4d6d;
  --red-dim:rgba(255,77,109,.10);
  --red-glow:rgba(255,77,109,.25);
  --yellow:#ffcb30;
  --yellow-dim:rgba(255,203,48,.10);
  --blue:#38bdf8;
  --blue-dim:rgba(56,189,248,.08);
  --purple:#a78bfa;
  --text:#ddeeff;
  --text2:#8baabb;
  --text3:#4a6a88;
  --radius:14px;
  --shadow:0 4px 24px rgba(0,0,0,.4);
}

html,body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;font-size:14px;line-height:1.5}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}

/* ── HEADER ── */
.header{
  position:sticky;top:0;z-index:60;
  background:rgba(6,13,24,.85);
  backdrop-filter:blur(14px);
  border-bottom:1px solid var(--border);
  padding:0 28px;
  height:58px;
  display:flex;align-items:center;justify-content:space-between;
}
.h-brand{display:flex;align-items:center;gap:10px}
.h-logo{font-size:1.1rem;font-weight:800;color:var(--blue);letter-spacing:-.3px}
.h-tag{
  font-size:.65rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
  color:var(--text3);background:var(--surface2);
  border:1px solid var(--border2);border-radius:6px;padding:3px 8px;
}
.h-right{display:flex;align-items:center;gap:16px}
.h-clock{font-size:.85rem;color:var(--text2);font-variant-numeric:tabular-nums;letter-spacing:.5px}
.pill{
  display:flex;align-items:center;gap:6px;
  padding:5px 13px;border-radius:30px;
  font-size:.72rem;font-weight:700;letter-spacing:.8px;text-transform:uppercase;
}
.pill-online{background:var(--green-dim);border:1px solid rgba(0,229,176,.25);color:var(--green)}
.pill-error{background:var(--red-dim);border:1px solid rgba(255,77,109,.25);color:var(--red)}
.pill-dot{width:7px;height:7px;border-radius:50%}
.dot-pulse{animation:dpulse 2s ease-in-out infinite}
@keyframes dpulse{0%,100%{opacity:1;box-shadow:0 0 0 0 currentColor}60%{opacity:.6;box-shadow:0 0 0 5px transparent}}

/* ── PAGE ── */
.page{max-width:1300px;margin:0 auto;padding:22px 20px 110px}

/* ── SECTION LABEL ── */
.slabel{font-size:.65rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--text3);margin-bottom:10px;padding-left:2px}

/* ── GRIDS ── */
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:14px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.mb{margin-bottom:14px}
@media(max-width:960px){.g3,.g2{grid-template-columns:1fr}}

/* ── CARD ── */
.card{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:20px 22px;
  position:relative;overflow:hidden;
  transition:border-color .3s,box-shadow .3s;
}
.card:hover{border-color:var(--border2)}
.card-lbl{
  font-size:.65rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
  color:var(--text3);margin-bottom:14px;display:flex;align-items:center;gap:6px;
}

/* top accent line */
.card::before{content:'';position:absolute;top:0;left:20%;right:20%;height:1px;transition:all .4s}
.accent-blue::before{background:linear-gradient(90deg,transparent,var(--blue),transparent);left:10%;right:10%}
.accent-green::before{background:linear-gradient(90deg,transparent,var(--green),transparent);left:10%;right:10%}
.accent-red::before{background:linear-gradient(90deg,transparent,var(--red),transparent);left:10%;right:10%}
.accent-yellow::before{background:linear-gradient(90deg,transparent,var(--yellow),transparent);left:10%;right:10%}
.accent-purple::before{background:linear-gradient(90deg,transparent,var(--purple),transparent);left:10%;right:10%}

/* ── PRICE CARD ── */
.price-big{
  font-size:2.8rem;font-weight:800;letter-spacing:-2px;
  font-variant-numeric:tabular-nums;line-height:1;
  margin-bottom:8px;transition:color .35s;
}
.price-vs{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:8px;font-size:.82rem;font-weight:700;margin-bottom:12px}
.up{background:var(--green-dim);color:var(--green)}
.dn{background:var(--red-dim);color:var(--red)}
.price-sma{font-size:.82rem;color:var(--text2)}
.price-sma span{color:var(--text);font-weight:600}

/* ── SIGNAL CARD ── */
.sig-badge{
  display:inline-flex;align-items:center;gap:8px;
  padding:10px 22px;border-radius:30px;
  font-size:.95rem;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;
  margin-bottom:14px;
}
.sig-buy{background:var(--green-dim);color:var(--green);border:1.5px solid rgba(0,229,176,.3)}
.sig-sell{background:var(--red-dim);color:var(--red);border:1.5px solid rgba(255,77,109,.3)}
.sig-hold{background:var(--yellow-dim);color:var(--yellow);border:1.5px solid rgba(255,203,48,.3)}
.sig-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.sig-buy .sig-dot,.sig-sell .sig-dot{animation:dpulse 1.5s infinite}
.sig-info{font-size:.82rem;color:var(--text2);line-height:1.65}

/* ── RSI GAUGE ── */
.rsi-wrap{display:flex;flex-direction:column;align-items:center;padding-top:4px}
.rsi-svg{width:190px;height:105px;overflow:visible}
.rsi-num{font-size:2rem;font-weight:800;text-align:center;margin-top:-4px;font-variant-numeric:tabular-nums;transition:color .4s}
.rsi-zone-txt{font-size:.75rem;text-align:center;color:var(--text2);margin-top:5px}
.rsi-legend{display:flex;justify-content:space-between;width:190px;font-size:.62rem;color:var(--text3);margin-top:8px}

/* ── CHART ── */
.chart-wrap{position:relative;height:230px}

/* ── PNL CARD ── */
.pnl-num{font-size:2.4rem;font-weight:800;letter-spacing:-1.5px;line-height:1;margin-bottom:4px;transition:color .4s}
.pnl-sub{font-size:.9rem;margin-bottom:18px}
.row-item{
  display:flex;justify-content:space-between;align-items:center;
  padding:9px 0;border-bottom:1px solid var(--border);font-size:.84rem;
}
.row-item:last-child{border-bottom:none}
.row-lbl{color:var(--text2)}
.row-val{font-weight:700;font-variant-numeric:tabular-nums}
.val-green{color:var(--green)}
.val-red{color:var(--red)}
.val-blue{color:var(--blue)}

/* no position */
.nopos{text-align:center;padding:28px 0}
.nopos-icon{font-size:2.2rem;margin-bottom:10px;opacity:.6}
.nopos-txt{color:var(--text3);font-size:.88rem}

/* ── BALANCE ── */
.vol-bar-wrap{margin-top:4px;height:5px;background:var(--border2);border-radius:3px;overflow:hidden}
.vol-bar-fill{height:100%;border-radius:3px;transition:width .6s ease}

/* ── LOG ── */
.log-wrap{max-height:300px;overflow-y:auto}
.log-entry{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--border);font-size:.81rem;animation:fadein .35s ease}
.log-entry:last-child{border-bottom:none}
@keyframes fadein{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
.log-ts{color:var(--text3);white-space:nowrap;font-variant-numeric:tabular-nums;font-size:.74rem;padding-top:1px;flex-shrink:0}
.log-msg{line-height:1.55;color:var(--text2)}
.log-empty{text-align:center;padding:36px;color:var(--text3);font-size:.85rem}

/* ── FOOTER BAR ── */
.fbar{
  position:fixed;bottom:68px;left:50%;transform:translateX(-50%);
  background:var(--surface);border:1px solid var(--border2);
  padding:6px 18px;border-radius:20px;
  font-size:.72rem;color:var(--text2);white-space:nowrap;
  display:flex;align-items:center;gap:12px;
}
.fsep{color:var(--border2)}

/* ── TRADE FLOAT BAR ── */
.trade-bar{
  position:fixed;bottom:0;left:0;right:0;
  background:rgba(11,20,34,.92);backdrop-filter:blur(14px);
  border-top:1px solid var(--border);
  padding:10px 24px;
  display:flex;justify-content:center;gap:14px;z-index:50;
}
.btn-t{
  padding:12px 44px;border-radius:12px;
  font-size:.95rem;font-weight:800;letter-spacing:.5px;
  cursor:pointer;border:none;transition:all .18s;
  display:flex;align-items:center;gap:8px;
}
.btn-t:disabled{opacity:.28;cursor:not-allowed}
.btn-buy-t{background:var(--green-dim);color:var(--green);border:1.5px solid rgba(0,229,176,.3)}
.btn-buy-t:not(:disabled):hover{background:var(--green);color:#000;box-shadow:0 0 24px var(--green-glow);transform:translateY(-2px)}
.btn-sell-t{background:var(--red-dim);color:var(--red);border:1.5px solid rgba(255,77,109,.3)}
.btn-sell-t:not(:disabled):hover{background:var(--red);color:#fff;box-shadow:0 0 24px var(--red-glow);transform:translateY(-2px)}

/* ── MODAL ── */
.overlay{display:none;position:fixed;inset:0;background:rgba(4,9,18,.82);backdrop-filter:blur(8px);z-index:100;align-items:center;justify-content:center}
.overlay.open{display:flex}
.modal{background:var(--surface2);border:1px solid var(--border2);border-radius:18px;padding:30px 34px;max-width:390px;width:93%;animation:popin .2s ease}
@keyframes popin{from{opacity:0;transform:scale(.93)}to{opacity:1;transform:scale(1)}}
.modal h3{font-size:1.1rem;margin-bottom:8px}
.modal p{color:var(--text2);font-size:.88rem;line-height:1.7;margin-bottom:24px}
.modal-btns{display:flex;gap:10px}
.btn-confirm{flex:1;padding:13px;border-radius:10px;font-size:.93rem;font-weight:700;cursor:pointer;border:none;transition:opacity .15s}
.btn-confirm:hover{opacity:.88}
.btn-cancel{padding:13px 18px;border-radius:10px;font-size:.93rem;font-weight:600;cursor:pointer;background:transparent;border:1px solid var(--border2);color:var(--text2)}
.btn-cancel:hover{background:var(--border)}

/* ── TOAST ── */
.toast{position:fixed;bottom:88px;left:50%;transform:translateX(-50%) translateY(8px);padding:12px 22px;border-radius:12px;font-size:.87rem;font-weight:600;z-index:200;opacity:0;transition:all .28s;pointer-events:none;background:var(--surface2);border:1px solid var(--border2);white-space:nowrap}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}

/* ── FLASH ── */
@keyframes fgreen{0%,100%{color:inherit}35%{color:var(--green)}}
@keyframes fred{0%,100%{color:inherit}35%{color:var(--red)}}
.flash-up{animation:fgreen .65s ease}
.flash-dn{animation:fred .65s ease}

/* ── MINI STAT ROW (3 cols inside balance) ── */
.mini-row{display:flex;gap:10px;margin-top:14px}
.mini-stat{flex:1;background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:10px 12px;text-align:center}
.mini-label{font-size:.62rem;color:var(--text3);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
.mini-val{font-size:.95rem;font-weight:700;font-variant-numeric:tabular-nums}
</style>
</head>
<body>

<!-- HEADER -->
<header class="header">
  <div class="h-brand">
    <div class="h-logo">⚡ BTC/USDT Bot</div>
    <div class="h-tag">Binance Spot · Auto Trading</div>
  </div>
  <div class="h-right">
    <div class="h-clock" id="clock">--:--:--</div>
    <div class="pill pill-online" id="status-pill">
      <div class="pill-dot dot-pulse" id="status-dot" style="background:var(--green)"></div>
      <span id="status-text">Conectando</span>
    </div>
  </div>
</header>

<main class="page">

  <!-- ROW 1 ─ PRICE / SIGNAL / RSI -->
  <div class="slabel">Mercado em Tempo Real</div>
  <div class="g3">

    <!-- PREÇO -->
    <div class="card accent-blue" id="price-card">
      <div class="card-lbl">💰 Preço BTC/USDT</div>
      <div class="price-big" id="pval">—</div>
      <div id="pvs" class="price-vs up" style="display:none">—</div>
      <div class="price-sma">SMA 50: <span id="sma-val">—</span></div>
    </div>

    <!-- SINAL -->
    <div class="card" id="sig-card">
      <div class="card-lbl">📡 Sinal Atual</div>
      <div id="sig-badge" class="sig-badge sig-hold">
        <span class="sig-dot" style="background:var(--yellow)"></span>
        <span id="sig-txt">HOLD</span>
      </div>
      <div class="sig-info" id="sig-info">Aguardando dados do mercado...</div>
    </div>

    <!-- RSI -->
    <div class="card" id="rsi-card">
      <div class="card-lbl">📊 RSI (14 períodos)</div>
      <div class="rsi-wrap">
        <svg class="rsi-svg" viewBox="0 0 200 110">
          <!-- track -->
          <path d="M15,100 A90,90 0 0,1 185,100" fill="none" stroke="#16263d" stroke-width="13" stroke-linecap="round"/>
          <!-- zones: red 0-30, yellow 30-70, green 70-100 -->
          <path d="M15,100 A90,90 0 0,1 68,17"   fill="none" stroke="rgba(255,77,109,.3)"  stroke-width="13" stroke-linecap="round"/>
          <path d="M68,17  A90,90 0 0,1 132,17"  fill="none" stroke="rgba(255,203,48,.3)"  stroke-width="13" stroke-linecap="round"/>
          <path d="M132,17 A90,90 0 0,1 185,100" fill="none" stroke="rgba(0,229,176,.3)"   stroke-width="13" stroke-linecap="round"/>
          <!-- needle -->
          <line id="rsi-needle" x1="100" y1="100" x2="15" y2="100" stroke="var(--yellow)" stroke-width="2.5" stroke-linecap="round"/>
          <circle cx="100" cy="100" r="5" fill="var(--yellow)" id="rsi-hub"/>
        </svg>
        <div class="rsi-num" id="rsi-num" style="color:var(--yellow)">—</div>
        <div class="rsi-zone-txt" id="rsi-zone">—</div>
        <div class="rsi-legend"><span>0 Sobrev.</span><span>50</span><span>Sobrec. 100</span></div>
      </div>
    </div>

  </div>

  <!-- ROW 2 ─ CHART -->
  <div class="slabel">Histórico de Preço — Sessão Atual</div>
  <div class="mb">
    <div class="card accent-blue">
      <div class="card-lbl">📈 Preço em Tempo Real &nbsp;<span style="color:var(--yellow);font-weight:600" id="chart-pts">0 pontos</span></div>
      <div class="chart-wrap">
        <canvas id="pchart"></canvas>
      </div>
    </div>
  </div>

  <!-- ROW 3 ─ POSITION / BALANCE -->
  <div class="slabel">Posição &amp; Saldo</div>
  <div class="g2">

    <!-- POSIÇÃO -->
    <div class="card" id="pos-card">
      <div class="card-lbl">📈 Posição Aberta</div>
      <div id="pos-body">
        <div class="nopos">
          <div class="nopos-icon">💤</div>
          <div class="nopos-txt">Sem posição aberta<br>Aguardando sinal de compra...</div>
        </div>
      </div>
    </div>

    <!-- SALDO -->
    <div class="card accent-blue">
      <div class="card-lbl">💼 Saldo da Conta</div>
      <div class="row-item">
        <span class="row-lbl">💵 USDT disponível</span>
        <span class="row-val val-blue" id="usdt-v">—</span>
      </div>
      <div class="row-item">
        <span class="row-lbl">₿ BTC disponível</span>
        <span class="row-val" id="btc-v">—</span>
      </div>
      <div class="row-item">
        <span class="row-lbl">💸 Valor por trade</span>
        <span class="row-val val-blue" id="trade-v">—</span>
      </div>

      <div class="mini-row">
        <div class="mini-stat">
          <div class="mini-label">Volume Atual</div>
          <div class="mini-val" id="vol-v" style="color:var(--text)">—</div>
        </div>
        <div class="mini-stat">
          <div class="mini-label">Média (20)</div>
          <div class="mini-val" id="volm-v" style="color:var(--text2)">—</div>
        </div>
        <div class="mini-stat">
          <div class="mini-label">Vol. vs Média</div>
          <div class="mini-val" id="vol-ratio" style="color:var(--text2)">—</div>
        </div>
      </div>

      <!-- volume bar -->
      <div class="vol-bar-wrap" style="margin-top:12px">
        <div class="vol-bar-fill" id="vol-bar" style="width:50%;background:var(--text3)"></div>
      </div>
    </div>

  </div>

  <!-- ROW 4 ─ LOG -->
  <div class="slabel">Histórico de Operações</div>
  <div class="mb">
    <div class="card">
      <div class="card-lbl">📋 Log de Eventos &nbsp;<span style="color:var(--text3)" id="log-count"></span></div>
      <div class="log-wrap" id="log-wrap">
        <div class="log-empty">Nenhum evento registrado ainda...</div>
      </div>
    </div>
  </div>

</main>

<!-- FOOTER -->
<div class="fbar">
  <span>Última atualização: <strong id="last-upd">—</strong></span>
  <span class="fsep">·</span>
  <span>Próxima em <strong id="cd">15</strong>s</span>
  <span class="fsep">·</span>
  <span>5min candles · Stop <strong style="color:var(--red)" id="sl-pct">—</strong> · Take <strong style="color:var(--green)" id="tp-pct">—</strong></span>
</div>

<!-- TRADE BAR -->
<div class="trade-bar">
  <button class="btn-t btn-buy-t" id="btn-buy" onclick="openModal('buy')">▲&nbsp; COMPRAR AGORA</button>
  <button class="btn-t btn-sell-t" id="btn-sell" onclick="openModal('sell')">▼&nbsp; VENDER AGORA</button>
</div>

<!-- MODAL -->
<div class="overlay" id="modal">
  <div class="modal">
    <h3 id="m-title">Confirmar</h3>
    <p id="m-body"></p>
    <div class="modal-btns">
      <button class="btn-confirm" id="m-confirm" onclick="confirmTrade()">✅ Confirmar</button>
      <button class="btn-cancel" onclick="closeModal()">Cancelar</button>
    </div>
  </div>
</div>

<!-- TOAST -->
<div class="toast" id="toast"></div>

<script>
// ── CHART ───────────────────────────────────────────────────────────────────
const MAX_PTS = 80;
const hist = { labels:[], prices:[], smas:[] };

const chartCtx = document.getElementById('pchart').getContext('2d');
const priceChart = new Chart(chartCtx, {
  type: 'line',
  data: {
    labels: hist.labels,
    datasets: [
      {
        label: 'BTC/USDT',
        data: hist.prices,
        borderColor: '#38bdf8',
        backgroundColor: ctx => {
          const g = ctx.chart.ctx.createLinearGradient(0,0,0,230);
          g.addColorStop(0,'rgba(56,189,248,.18)');
          g.addColorStop(1,'rgba(56,189,248,.01)');
          return g;
        },
        borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, tension: 0.4, fill: true,
      },
      {
        label: 'SMA 50',
        data: hist.smas,
        borderColor: 'rgba(255,203,48,.65)',
        borderDash: [6,4], borderWidth: 1.5,
        pointRadius: 0, tension: 0.4, fill: false,
      }
    ]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode:'index', intersect:false },
    animation: { duration: 0 },
    plugins: {
      legend:{ labels:{ color:'#4a6a88', font:{ size:11 }, boxWidth:18, padding:14 } },
      tooltip:{
        backgroundColor:'#101d30', borderColor:'#1e3350', borderWidth:1,
        titleColor:'#ddeeff', bodyColor:'#8baabb',
        callbacks:{
          label: c => ` ${c.dataset.label}: $${Number(c.parsed.y).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})}`
        }
      }
    },
    scales:{
      x:{ ticks:{ color:'#4a6a88', font:{ size:10 }, maxTicksLimit:8 }, grid:{ color:'rgba(22,38,61,.8)' }, border:{ display:false } },
      y:{ position:'right', ticks:{ color:'#4a6a88', font:{ size:10 }, callback: v=>'$'+Number(v).toLocaleString('pt-BR',{maximumFractionDigits:0}) }, grid:{ color:'rgba(22,38,61,.8)' }, border:{ display:false } }
    }
  }
});

function pushChart(label, price, sma) {
  hist.labels.push(label);
  hist.prices.push(price);
  hist.smas.push(sma || null);
  if (hist.labels.length > MAX_PTS) { hist.labels.shift(); hist.prices.shift(); hist.smas.shift(); }
  priceChart.update('none');
  document.getElementById('chart-pts').textContent = hist.labels.length + ' pontos';
}

// ── RSI GAUGE ──────────────────────────────────────────────────────────────
function setRSI(v) {
  const pct = Math.min(Math.max(v, 0), 100) / 100;
  // arc center (100,100) radius 90, from 180° to 0°
  const angle = Math.PI - pct * Math.PI;
  const cx=100, cy=100, r=90;
  const nx = cx + r * Math.cos(angle);
  const ny = cy - r * Math.sin(angle);

  const needle = document.getElementById('rsi-needle');
  needle.setAttribute('x2', nx.toFixed(1));
  needle.setAttribute('y2', ny.toFixed(1));

  const numEl  = document.getElementById('rsi-num');
  const zoneEl = document.getElementById('rsi-zone');
  const hub    = document.getElementById('rsi-hub');
  const card   = document.getElementById('rsi-card');

  let color, zone, accentClass;
  if (v < 30) {
    color = 'var(--red)'; zone = '🔴 Sobrevenda — possível reversão de alta'; accentClass = 'card accent-red';
  } else if (v > 70) {
    color = 'var(--green)'; zone = '🟢 Sobrecompra — possível reversão de baixa'; accentClass = 'card accent-green';
  } else {
    color = 'var(--yellow)'; zone = '🟡 Zona neutra'; accentClass = 'card accent-yellow';
  }

  needle.setAttribute('stroke', color);
  hub.setAttribute('fill', color);
  numEl.style.color = color;
  numEl.textContent = v.toFixed(1);
  zoneEl.textContent = zone;
  card.className = accentClass;
}

// ── UTILS ──────────────────────────────────────────────────────────────────
function fmt(n, d=2) { return Number(n).toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d}); }
function usd(n) { return '$' + fmt(n); }
function now8() { return new Date().toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'}); }

// clock
setInterval(() => document.getElementById('clock').textContent = now8(), 1000);
document.getElementById('clock').textContent = now8();

// ── STATE ──────────────────────────────────────────────────────────────────
let D = {};
let prevP = 0;
let cd = 15;

// ── RENDER ─────────────────────────────────────────────────────────────────
function render(d) {
  const price = d.price || 0;

  // price card
  const pEl = document.getElementById('pval');
  if (prevP && price !== prevP) {
    pEl.classList.remove('flash-up','flash-dn');
    void pEl.offsetWidth;
    pEl.classList.add(price > prevP ? 'flash-up' : 'flash-dn');
  }
  pEl.textContent = usd(price);
  document.getElementById('sma-val').textContent = usd(d.sma50 || 0);

  const vsEl = document.getElementById('pvs');
  if (d.sma50 > 0) {
    const diff = price - d.sma50;
    const pct  = diff / d.sma50 * 100;
    vsEl.style.display = 'inline-flex';
    vsEl.className = 'price-vs ' + (diff >= 0 ? 'up' : 'dn');
    vsEl.textContent = (diff >= 0 ? '▲ +' : '▼ ') + fmt(pct) + '% vs SMA50';
  }

  // signal
  const sig = d.signal || 'hold';
  const badge = document.getElementById('sig-badge');
  const sigDot = badge.querySelector('.sig-dot');
  badge.className = 'sig-badge sig-' + sig;
  document.getElementById('sig-txt').textContent = sig.toUpperCase();

  const sigColors = { buy: 'var(--green)', sell: 'var(--red)', hold: 'var(--yellow)' };
  sigDot.style.background = sigColors[sig] || 'var(--yellow)';

  const infoEl = document.getElementById('sig-info');
  const sigCard = document.getElementById('sig-card');
  if (sig === 'buy') {
    infoEl.innerHTML = '🟢 <strong>Condições ativas:</strong> Tendência de alta + RSI abaixo de 40 + volume confirmado';
    sigCard.className = 'card accent-green';
  } else if (sig === 'sell') {
    infoEl.innerHTML = '🔴 <strong>Venda sinalizada:</strong> RSI acima de 65 — ativo sobrecomprado';
    sigCard.className = 'card accent-red';
  } else {
    infoEl.innerHTML = d.position
      ? '🔵 Em posição — monitorando Stop Loss e Take Profit automaticamente'
      : '⚪ Aguardando condições ideais de compra (RSI + tendência + volume)';
    sigCard.className = 'card';
  }

  // RSI
  if (d.rsi > 0) setRSI(d.rsi);

  // position
  const posBody = document.getElementById('pos-body');
  const posCard = document.getElementById('pos-card');
  if (d.position && d.entry_price > 0) {
    const pnl   = d.pnl_pct || 0;
    const color = pnl > 0 ? 'var(--green)' : pnl < 0 ? 'var(--red)' : 'var(--text2)';
    posCard.className = pnl >= 0 ? 'card accent-green' : 'card accent-red';
    posBody.innerHTML = `
      <div class="pnl-num" style="color:${color}">${pnl>=0?'+':''}${fmt(pnl)}%</div>
      <div class="pnl-sub" style="color:${color}">${pnl>=0?'+':''}${usd(d.pnl_usdt)} USDT</div>
      <div class="row-item">
        <span class="row-lbl">🎯 Preço de entrada</span>
        <span class="row-val">${usd(d.entry_price)}</span>
      </div>
      <div class="row-item">
        <span class="row-lbl">🟢 Take Profit (+${fmt(d.take_profit_pct)}%)</span>
        <span class="row-val val-green">${usd(d.take_profit_price)}</span>
      </div>
      <div class="row-item">
        <span class="row-lbl">🔴 Stop Loss (-${fmt(d.stop_loss_pct)}%)</span>
        <span class="row-val val-red">${usd(d.stop_loss_price)}</span>
      </div>
      <div class="row-item">
        <span class="row-lbl">₿ BTC em carteira</span>
        <span class="row-val">${fmt(d.btc_balance,6)} BTC</span>
      </div>`;
  } else {
    posCard.className = 'card';
    posBody.innerHTML = `<div class="nopos"><div class="nopos-icon">💤</div><div class="nopos-txt">Sem posição aberta<br>Aguardando sinal de compra...</div></div>`;
  }

  // balance
  document.getElementById('usdt-v').textContent  = usd(d.usdt_balance);
  document.getElementById('btc-v').textContent   = fmt(d.btc_balance,6) + ' BTC';
  document.getElementById('trade-v').textContent = usd(d.trade_amount_usdt);
  document.getElementById('vol-v').textContent   = fmt(d.volume,2);
  document.getElementById('volm-v').textContent  = fmt(d.vol_mean,2);

  const ratio = d.vol_mean > 0 ? d.volume / d.vol_mean : 0;
  const volRatioEl = document.getElementById('vol-ratio');
  volRatioEl.textContent = fmt(ratio,2) + 'x';
  volRatioEl.style.color = ratio >= 1 ? 'var(--green)' : 'var(--text3)';

  document.getElementById('vol-v').style.color = ratio >= 1 ? 'var(--green)' : 'var(--text)';

  const barPct = Math.min(ratio * 50, 100);
  const bar = document.getElementById('vol-bar');
  bar.style.width = barPct + '%';
  bar.style.background = ratio >= 1 ? 'var(--green)' : 'var(--text3)';

  // footer
  document.getElementById('sl-pct').textContent = '-' + fmt(d.stop_loss_pct) + '%';
  document.getElementById('tp-pct').textContent = '+' + fmt(d.take_profit_pct) + '%';
  document.getElementById('last-upd').textContent = d.last_update || '—';

  // log
  const logWrap = document.getElementById('log-wrap');
  if (d.log && d.log.length > 0) {
    document.getElementById('log-count').textContent = d.log.length + ' eventos';
    logWrap.innerHTML = d.log.map(e =>
      `<div class="log-entry"><span class="log-ts">${e.time}</span><span class="log-msg">${e.msg}</span></div>`
    ).join('');
  } else {
    document.getElementById('log-count').textContent = '';
    logWrap.innerHTML = '<div class="log-empty">Nenhum evento ainda. Operações serão registradas aqui automaticamente.</div>';
  }

  // status pill
  const pill = document.getElementById('status-pill');
  const dot  = document.getElementById('status-dot');
  const stxt = document.getElementById('status-text');
  const ok   = !String(d.status||'').includes('⚠️');
  pill.className = 'pill ' + (ok ? 'pill-online' : 'pill-error');
  dot.style.background = ok ? 'var(--green)' : 'var(--red)';
  stxt.textContent = ok ? 'Online' : 'Erro';

  // chart
  pushChart(now8(), price, d.sma50 || null);

  prevP = price;
}

// ── FETCH ──────────────────────────────────────────────────────────────────
async function fetchData() {
  try {
    const r = await fetch('/api/data');
    D = await r.json();
    render(D);
    cd = 15;
  } catch(e) {
    document.getElementById('status-text').textContent = 'Sem conexão';
  }
}

setInterval(() => {
  cd = Math.max(0, cd - 1);
  document.getElementById('cd').textContent = cd;
  if (cd <= 0) fetchData();
}, 1000);

fetchData();

// ── MODAL ──────────────────────────────────────────────────────────────────
let pendingAction = null;

function openModal(action) {
  pendingAction = action;
  const isBuy = action === 'buy';
  document.getElementById('m-title').textContent = isBuy ? '🟢 Confirmar COMPRA' : '🔴 Confirmar VENDA';
  const price = usd(D.price || 0);
  if (isBuy) {
    document.getElementById('m-body').innerHTML =
      `Executar <strong>compra a mercado</strong> de <strong>$${D.trade_amount_usdt} USDT</strong> em BTC.<br><br>
       Preço atual: <strong>${price}</strong><br>
       Stop Loss: <strong style="color:var(--red)">−${fmt(D.stop_loss_pct)}%</strong>
       &nbsp;·&nbsp;
       Take Profit: <strong style="color:var(--green)">+${fmt(D.take_profit_pct)}%</strong>`;
    const btn = document.getElementById('m-confirm');
    btn.style.background = 'var(--green)'; btn.style.color = '#000';
  } else {
    const btc = fmt(D.btc_balance || 0, 6);
    const pnl = D.pnl_pct || 0;
    document.getElementById('m-body').innerHTML =
      `Vender <strong>todo o BTC disponível</strong> agora.<br><br>
       Quantidade: <strong>${btc} BTC</strong><br>
       Preço atual: <strong>${price}</strong><br>
       P&L estimado: <strong style="color:${pnl>=0?'var(--green)':'var(--red)'}">${pnl>=0?'+':''}${fmt(pnl)}%</strong>`;
    const btn = document.getElementById('m-confirm');
    btn.style.background = 'var(--red)'; btn.style.color = '#fff';
  }
  document.getElementById('modal').classList.add('open');
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
  pendingAction = null;
}

async function confirmTrade() {
  if (!pendingAction) return;
  const action = pendingAction;
  closeModal();
  setBtns(true);
  showToast('⏳ Enviando ordem...');
  try {
    const r   = await fetch('/api/' + action, { method:'POST' });
    const res = await r.json();
    showToast(res.msg, res.ok ? 4000 : 6000);
    await fetchData();
  } catch(e) {
    showToast('❌ Erro de comunicação com o servidor', 5000);
  } finally {
    setBtns(false);
  }
}

function setBtns(v) {
  document.getElementById('btn-buy').disabled  = v;
  document.getElementById('btn-sell').disabled = v;
}

function showToast(msg, ms=3500) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), ms);
}

document.getElementById('modal').addEventListener('click', e => {
  if (e.target.id === 'modal') closeModal();
});
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────
# SERVIDOR HTTP
# ─────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass   # silencia logs do servidor no terminal

    def do_POST(self):
        # Consome o body da requisição (evita travamento)
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            self.rfile.read(content_length)

        try:
            if self.path == '/api/buy':
                result = manual_buy()
            elif self.path == '/api/sell':
                result = manual_sell()
            else:
                self.send_response(404)
                self.end_headers()
                return
        except Exception as e:
            result = {"ok": False, "msg": f"❌ Erro interno: {e}"}

        payload = json.dumps(result, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == '/api/data':
            with state_lock:
                payload = json.dumps(state, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(payload)

        elif self.path in ('/', '/index.html'):
            body = HTML.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    PORT = 8080

    # Busca inicial antes de abrir o servidor
    print("🔄 Buscando dados iniciais...")
    fetch_state()
    log_event("🚀 Dashboard iniciado")

    # Thread de atualização
    t = threading.Thread(target=updater_loop, daemon=True)
    t.start()

    # Servidor HTTP multi-thread (não trava ao chamar a Binance)
    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadedHTTPServer(('0.0.0.0', PORT), Handler)
    print(f"✅ Dashboard rodando em → http://localhost:{PORT}")
    print("   (Ctrl+C para parar)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⛔ Dashboard encerrado.")
