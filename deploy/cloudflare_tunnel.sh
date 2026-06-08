#!/bin/bash
# ============================================================
#  Bot Bitcoin — Configura Cloudflare Tunnel Permanente
#  Execute no VPS após vps_setup.sh
#
#  Pré-requisito: ter um domínio gerenciado pela Cloudflare
#  Exemplo de URL final: https://bot.seudominio.com
# ============================================================

TUNNEL_NAME="bot-bitcoin"
DOMAIN="${1:-}"   # Passa como argumento: bash cloudflare_tunnel.sh bot.seudominio.com

if [ -z "$DOMAIN" ]; then
    echo ""
    echo "==================================================="
    echo " OPÇÃO A — URL TEMPORÁRIA (sem domínio, sem login)"
    echo "==================================================="
    echo ""
    echo " Execute e você receberá uma URL pública imediata:"
    echo " cloudflared tunnel --url http://localhost:8080"
    echo ""
    echo " A URL muda toda vez que reiniciar."
    echo ""
    echo "==================================================="
    echo " OPÇÃO B — URL PERMANENTE (requer domínio + conta)"
    echo "==================================================="
    echo ""
    echo " Uso: bash cloudflare_tunnel.sh bot.seudominio.com"
    echo ""
    exit 0
fi

echo "Configurando tunnel permanente para: $DOMAIN"
echo ""

# ── Login na conta Cloudflare (abre navegador) ───────────────
echo "[1/5] Fazendo login na Cloudflare..."
cloudflared tunnel login

# ── Cria o tunnel ────────────────────────────────────────────
echo "[2/5] Criando tunnel '$TUNNEL_NAME'..."
cloudflared tunnel create "$TUNNEL_NAME"

TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
echo "      Tunnel ID: $TUNNEL_ID"

# ── Cria configuração ────────────────────────────────────────
echo "[3/5] Criando configuração..."
mkdir -p /etc/cloudflared

cat > /etc/cloudflared/config.yml <<EOF
tunnel: $TUNNEL_ID
credentials-file: /root/.cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: $DOMAIN
    service: http://localhost:8080
  - service: http_status:404
EOF

# ── Cria rota DNS ────────────────────────────────────────────
echo "[4/5] Criando rota DNS $DOMAIN → tunnel..."
cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN"

# ── Instala como serviço systemd ────────────────────────────
echo "[5/5] Instalando serviço cloudflared..."
cloudflared service install

systemctl enable --now cloudflared

echo ""
echo "============================================"
echo " TUNNEL CONFIGURADO!"
echo " Dashboard disponível em: https://$DOMAIN"
echo "============================================"
echo ""
echo "Verifique: systemctl status cloudflared"
