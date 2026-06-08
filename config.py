# config.py
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY', '')
SECRET  = os.getenv('BINANCE_API_SECRET', '')

SYMBOL          = 'BTC/USDT'
TIMEFRAME       = '15m'

STOP_LOSS       = 0.98    # -2%
TAKE_PROFIT     = 1.03    # +3%
TRADE_SIZE_PCT  = 0.30    # 30% do saldo USDT por operação (gestão de risco)
COOLDOWN_BARS   = 3       # mínimo 3 candles entre trades (~45min no 15m)

STATE_FILE      = 'bot_state.json'
CONTROL_FILE    = 'bot_control.json'
