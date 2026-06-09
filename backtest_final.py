import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime, timezone
import os

from strategy import apply_indicators, generate_signal
import config

# Configurações do Backtest
SYMBOL          = config.SYMBOL
TIMEFRAME       = config.TIMEFRAME
START_DATE      = "2023-01-01"
END_DATE        = "2024-06-01"  # Data atual aproximada
INITIAL_CAPITAL = 1000.0

# Custos Reais
FEES            = config.FEES_PCT
SLIPPAGE        = config.SLIPPAGE_PCT

# Cores para o terminal
BUY  = '\033[92m'
SELL = '\033[91m'
RST  = '\033[0m'
BOLD = '\033[1m'

def to_ms(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def fetch_range(symbol, timeframe, start_ms, end_ms):
    days = (end_ms - start_ms) // (24 * 3600 * 1000)
    print(f"\n📥 Baixando dados para backtest profissional...")
    exchange  = ccxt.binance({'enableRateLimit': True})
    all_ohlcv = []
    since     = start_ms

    while since < end_ms:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            if not ohlcv: break
            ohlcv = [c for c in ohlcv if c[0] <= end_ms]
            all_ohlcv.extend(ohlcv)
            if len(ohlcv) < 1000: break
            since = ohlcv[-1][0] + 1
        except Exception as e:
            print(f"Erro API: {e}")
            time.sleep(5)

    df = pd.DataFrame(all_ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df.drop_duplicates('time', inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

def ts(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime('%d/%m %H:%M')

def run_backtest():
    start_ms = to_ms(START_DATE)
    end_ms   = to_ms(END_DATE)
    df       = fetch_range(SYMBOL, TIMEFRAME, start_ms, end_ms)

    if df is None or len(df) < 200:
        print("❌ Dados insuficientes para backtest.")
        return

    print("⚙️  Calculando indicadores e estratégia...")
    df = apply_indicators(df)

    capital        = INITIAL_CAPITAL
    position       = 0.0
    entry_price    = 0.0
    entry_atr      = 0.0
    highest_price  = 0.0
    candles_in_pos = 0
    cooldown       = 0
    partial_taken  = False
    trades         = []
    equity_curve   = [INITIAL_CAPITAL]

    print(f"\n{'─'*85}")
    print(f"  {'DATA':<14} {'EVENTO':<10} {'PREÇO':>9}  {'PnL':>7}  {'CAPITAL':>10}  DETALHE")
    print(f"{'─'*85}")

    for i in range(200, len(df)):
        row   = df.iloc[i]
        prev  = df.iloc[i - 1]
        pprev = df.iloc[i - 2]

        if cooldown > 0:
            cooldown -= 1

        # ── LOGICA DE SAÍDA ────────────────────────────────────────────────
        if position > 0:
            candles_in_pos += 1
            highest_price   = max(highest_price, row['high'])
            
            # --- NOVO: GESTÃO DE RISCO DE ELITE ---
            # 1. Breakeven Precoce (aos +2% movemos stop pro zero)
            has_reached_breakeven = highest_price >= entry_price * config.BREAKEVEN_TRIGGER
            
            # 2. Stop Baseado em Volatilidade (ATR)
            if partial_taken:
                # Se já fez parcial, trailing stop fica MAIS JUSTO (1.5x ATR em vez de 3x)
                stop_loss_price = entry_price  # Nunca perde mais que o breakeven
                trailing_price  = highest_price - (1.5 * entry_atr) 
            elif has_reached_breakeven:
                stop_loss_price = entry_price
                trailing_price  = highest_price - (config.ATR_TRAILING_MULT * entry_atr)
            else:
                stop_loss_price = entry_price - (config.ATR_STOP_MULT * entry_atr)
                trailing_price  = highest_price - (config.ATR_TRAILING_MULT * entry_atr)

            current_stop = max(stop_loss_price, trailing_price)
            # ---------------------------------------

            exit_price = 0.0
            reason     = ""

            # 1. Realização Parcial (aos +5%)
            if not partial_taken and row['high'] >= entry_price * config.PARTIAL_PROFIT_PCT:
                exec_price = entry_price * config.PARTIAL_PROFIT_PCT
                # Aplica slippage e taxas na parcial
                exec_price_real = exec_price * (1 - SLIPPAGE)
                profit = (position * config.PARTIAL_SIZE_PCT) * (exec_price_real - entry_price)
                fee_cost = (position * config.PARTIAL_SIZE_PCT) * exec_price_real * FEES
                capital += (profit - fee_cost)
                position *= (1 - config.PARTIAL_SIZE_PCT)
                partial_taken = True
                print(f"  {ts(row['time']):<14} {BUY}{'PARCIAL':<10}{RST} ${exec_price:>9,.0f}  {BUY}+2.00%{RST}  ${capital:>9,.2f}  🎯 Parcial OK!")

            # 2. Stop Loss / Trailing / Breakeven
            if row['low'] <= current_stop:
                exit_price = current_stop
                if partial_taken and current_stop == entry_price:
                    reason = "Breakeven"
                elif current_stop > entry_price:
                    reason = "Trailing Stop"
                else:
                    reason = "Stop Loss"
            
            # 3. Take Profit Final
            elif row['high'] >= entry_price * config.TAKE_PROFIT:
                exit_price = entry_price * config.TAKE_PROFIT
                reason = "Take Profit Final"
            
            # 4. NOVO: Time Stop (Se em X barras não andou nada, sai fora)
            elif candles_in_pos >= config.TIME_STOP_BARS and not has_reached_breakeven:
                exit_price = row['open']
                reason = "Time Stop"

            # 5. Sinal de Venda Técnico
            elif candles_in_pos >= config.MIN_HOLD_BARS:
                signal = generate_signal(df.iloc[:i+1])

                if signal == "sell":
                    exit_price = row['open']
                    reason = "Sinal Venda"

            # Executa Saída Final
            if exit_price > 0:
                # Aplica Slippage e Taxas
                exit_price_real = exit_price * (1 - SLIPPAGE)
                gross_profit = position * (exit_price_real - entry_price)
                fees_paid    = (position * exit_price_real * FEES)
                net_profit   = gross_profit - fees_paid
                
                capital += net_profit
                pnl_pct = (exit_price_real - entry_price) / entry_price * 100
                
                win     = pnl_pct > 0
                color   = BUY if win else SELL
                emoji   = '✅' if win else '❌'
                if reason == "Breakeven": 
                    color = RST
                    emoji = '🛡️'

                print(f"  {ts(row['time']):<14} {color}{'VENDA':<10}{RST} ${exit_price:>9,.0f}  {color}{pnl_pct:>+6.2f}%{RST}  ${capital:>9,.2f}  {emoji} {reason}")

                trades.append({
                    'pnl_val': net_profit,
                    'pnl_pct': pnl_pct,
                    'win': win
                })

                position = 0.0
                cooldown = config.COOLDOWN_BARS
                equity_curve.append(capital)

        # ── LOGICA DE ENTRADA ──────────────────────────────────────────────
        elif cooldown == 0:
            signal = generate_signal(df.iloc[:i+1])

            if signal == "buy":
                # Entrada com Slippage e Taxas
                entry_price_raw = row['open']
                entry_price     = entry_price_raw * (1 + SLIPPAGE)
                entry_atr       = prev['atr']
                
                # Cálculo de Mão (ATR Based Risk)
                risk_amount = capital * config.RISK_PER_TRADE_PCT
                stop_dist   = entry_atr * config.ATR_STOP_MULT
                
                if stop_dist > 0:
                    pos_size_btc = risk_amount / stop_dist
                    # Limite de capital
                    max_size_btc = (capital * config.TRADE_SIZE_PCT) / entry_price
                    position = min(pos_size_btc, max_size_btc)
                else:
                    position = (capital * config.TRADE_SIZE_PCT) / entry_price

                # Paga taxa de entrada
                entry_fee = position * entry_price * FEES
                capital -= entry_fee
                
                entry_time     = row['time']
                highest_price  = entry_price
                candles_in_pos = 0
                partial_taken  = False
                
                print(f"  {ts(row['time']):<14} {BUY}{'COMPRA':<10}{RST} ${entry_price:>9,.0f}  {'':>7}  ${capital:>9,.2f}  🟢 Mão ATR: {position:.4f} BTC")

    # ── MÉTRICAS FINAIS ────────────────────────────────────────────────────
    print(f"{'─'*85}\n")
    
    if not trades:
        print("Nenhuma operação realizada no período.")
        return

    df_trades = pd.DataFrame(trades)
    win_rate = (df_trades['win'].sum() / len(df_trades)) * 100
    
    gross_profits = df_trades[df_trades['pnl_val'] > 0]['pnl_val'].sum()
    gross_losses  = abs(df_trades[df_trades['pnl_val'] < 0]['pnl_val'].sum())
    profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')
    
    # Drawdown
    equity_series = pd.Series(equity_curve)
    rolling_max   = equity_series.cummax()
    drawdowns     = (equity_series - rolling_max) / rolling_max * 100
    max_drawdown  = drawdowns.min()

    total_return = (capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    
    print(f"{BOLD}{'═'*50}{RST}")
    print(f"{BOLD}   RELATÓRIO DE PERFORMANCE PROFISSIONAL{RST}")
    print(f"{BOLD}{'═'*50}{RST}")
    print(f"  Retorno Total:         {total_return:>+10.2f}%")
    print(f"  Capital Final:         ${capital:>10.2f}")
    print(f"  Win Rate:              {win_rate:>10.2f}%")
    print(f"  Profit Factor:         {profit_factor:>10.2f}")
    print(f"  Max Drawdown:          {max_drawdown:>10.2f}%")
    print(f"  Total de Trades:       {len(df_trades):>10}")
    print(f"{BOLD}{'═'*50}{RST}\n")

if __name__ == "__main__":
    run_backtest()
