# config.py
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY', '')
SECRET  = os.getenv('BINANCE_API_SECRET', '')

SYMBOL          = 'BTC/USDT'
TIMEFRAME       = '4h'    # ← SWING TRADE: Filtra o ruído e reduz taxas

# ── Gestão de Risco Sniper 4h ────────────────────────────────────────────────
RISK_PER_TRADE_PCT  = 0.02    # Arriscar 2% (temos menos trades no 4h)
FEES_PCT            = 0.001   
SLIPPAGE_PCT        = 0.0005  
ATR_STOP_MULT       = 2.5     # Stop técnico
ATR_TRAILING_MULT   = 2.0     # Persegue a tendência

STOP_LOSS           = 0.90    # -10% (piso de pânico raro)
TRAILING_PCT        = 0.950   # 5% de recuo do topo sai
TAKE_PROFIT         = 1.30    # +30% (Alvo de tendência real)
PARTIAL_PROFIT_PCT  = 1.03    # Alvo 1: Garante lucro rápido aos +3%
PARTIAL_SIZE_PCT    = 0.50    
TRADE_SIZE_PCT      = 0.40    # Aumenta a mão nos sinais raros
COOLDOWN_BARS       = 6       # 24h de descanso
MIN_HOLD_BARS       = 3       
TIME_STOP_BARS      = 6       # Se em 24h não subiu nada, cai fora
ADX_MIN             = 18      # ADX menor para pegar o início do pullback
BREAKEVEN_TRIGGER   = 1.015   # Travado no zero com +1.5% (segurança total)

STATE_FILE      = 'bot_state.json'
CONTROL_FILE    = 'bot_control.json'

# ── Notificações (Opcional) ──────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
