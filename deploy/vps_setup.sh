#!/bin/bash
# ============================================================
#  Bot Bitcoin — Setup VPS (Ubuntu 22.04 / 24.04)
#  Execute como root: bash vps_setup.sh
# ============================================================
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC}  $1"; }
err()  { echo -e "${RED}[ERR]${NC} $1"; exit 1; }

echo ""
echo "============================================"
echo "  BOT BITCOIN — Instalação no VPS"
echo "============================================"
echo ""

# ── 1. Pacotes do sistema ────────────────────────────────────
ok "Atualizando pacotes..."
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl wget unzip

# ── 2. Usuário dedicado (segurança) ─────────────────────────
if ! id -u botuser &>/dev/null; then
    useradd -m -s /bin/bash botuser
    ok "Usuário 'botuser' criado"
else
    ok "Usuário 'botuser' já existe"
fi

# ── 3. Diretório do projeto ──────────────────────────────────
PROJECT_DIR="/opt/bot-bitcoin"
mkdir -p "$PROJECT_DIR"
chown -R botuser:botuser "$PROJECT_DIR"
ok "Diretório $PROJECT_DIR pronto"

# ── 4. Ambiente Python ───────────────────────────────────────
ok "Criando ambiente virtual Python..."
sudo -u botuser python3 -m venv "$PROJECT_DIR/.venv"
sudo -u botuser "$PROJECT_DIR/.venv/bin/pip" install --upgrade pip -q
sudo -u botuser "$PROJECT_DIR/.venv/bin/pip" install ccxt ta pandas python-dotenv -q
ok "Dependências Python instaladas"

# ── 5. cloudflared ───────────────────────────────────────────
if ! command -v cloudflared &>/dev/null; then
    ok "Instalando cloudflared..."
    curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
        gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg
    echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared jammy main' \
        > /etc/apt/sources.list.d/cloudflared.list
    apt-get update -qq && apt-get install -y -qq cloudflared
    ok "cloudflared instalado: $(cloudflared --version)"
else
    ok "cloudflared já instalado: $(cloudflared --version)"
fi

# ── 6. Serviços systemd ──────────────────────────────────────
ok "Instalando serviços systemd..."

cat > /etc/systemd/system/bot-bitcoin.service <<'EOF'
[Unit]
Description=Bot Bitcoin — Trading Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/bot-bitcoin
ExecStart=/opt/bot-bitcoin/.venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=bot-bitcoin

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/bot-dashboard.service <<'EOF'
[Unit]
Description=Bot Bitcoin — Dashboard Web Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/bot-bitcoin
ExecStart=/opt/bot-bitcoin/.venv/bin/python dashboard_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=bot-dashboard

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
ok "Serviços systemd registrados"

# ── 7. Resumo final ──────────────────────────────────────────
echo ""
echo "============================================"
echo "  SETUP CONCLUÍDO!"
echo "============================================"
echo ""
warn "PRÓXIMOS PASSOS:"
echo ""
echo "  1. Copie os arquivos do bot para /opt/bot-bitcoin/"
echo "     (use o script send_files.sh no seu Mac)"
echo ""
echo "  2. Crie o arquivo .env com suas chaves:"
echo "     nano /opt/bot-bitcoin/.env"
echo "     -> BINANCE_API_KEY=sua_chave"
echo "     -> BINANCE_API_SECRET=seu_secret"
echo ""
echo "  3. Inicie os serviços:"
echo "     systemctl enable --now bot-bitcoin bot-dashboard"
echo ""
echo "  4. Configure o Cloudflare Tunnel:"
echo "     cloudflared tunnel login"
echo "     cloudflared tunnel create bot-bitcoin"
echo "     (veja deploy/cloudflare_tunnel.sh)"
echo ""
echo "  5. Monitore os logs:"
echo "     journalctl -u bot-bitcoin -f"
echo "     journalctl -u bot-dashboard -f"
echo ""
