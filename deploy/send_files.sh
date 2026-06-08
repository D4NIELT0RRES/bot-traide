#!/bin/bash
# ============================================================
#  Bot Bitcoin — Envia arquivos para o VPS
#  Execute no seu Mac: bash deploy/send_files.sh SEU_IP_VPS
# ============================================================

VPS_IP="${1:-}"
VPS_USER="${2:-root}"

if [ -z "$VPS_IP" ]; then
    echo "Uso: bash deploy/send_files.sh IP_DO_VPS [usuario]"
    echo "Exemplo: bash deploy/send_files.sh 123.45.67.89"
    exit 1
fi

echo "Enviando arquivos para $VPS_USER@$VPS_IP:/opt/bot-bitcoin/ ..."

# Cria o diretório remoto se não existir
ssh "$VPS_USER@$VPS_IP" "mkdir -p /opt/bot-bitcoin"

# Envia os arquivos do bot (exclui venv, cache, estado, segredos)
rsync -avz --progress \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='bot_state.json' \
    --exclude='bot_control.json' \
    --exclude='.env' \
    --exclude='cloudflared' \
    --exclude='deploy' \
    --exclude='.DS_Store' \
    /Users/danieltorres/Documents/bot-bitcoin/ \
    "$VPS_USER@$VPS_IP:/opt/bot-bitcoin/"

echo ""
echo "Arquivos enviados!"
echo ""
echo "Agora no VPS, crie o .env:"
echo "  ssh $VPS_USER@$VPS_IP"
echo "  nano /opt/bot-bitcoin/.env"
echo ""
echo "Cole:"
echo "  BINANCE_API_KEY=SUA_CHAVE"
echo "  BINANCE_API_SECRET=SEU_SECRET"
