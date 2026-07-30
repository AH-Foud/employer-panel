#!/bin/bash
# Employer Panel - Bale Bot + Web Dashboard Installer
# Run: bash <(curl -s https://raw.githubusercontent.com/AH-Foud/employer-panel/main/install.sh)

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/opt/employer-panel"
SERVICE_NAME="employer-panel"
KARPANEL_CMD="/usr/local/bin/karpanel"
GIT_REPO="https://github.com/AH-Foud/employer-panel.git"

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ═══════════════════════════════════════════════════════════
#  SETUP CONFIG
# ═══════════════════════════════════════════════════════════

write_config() {
    local token="$1" admin_id="$2" secret="$3"
    python3 /tmp/write_config.py "$token" "$admin_id" "$secret"
}

# ═══════════════════════════════════════════════════════════
#  VERIFY BOT TOKEN
# ═══════════════════════════════════════════════════════════

verify_bot() {
    local token="$1"
    local result
    result=$(curl -s "https://tapi.bale.ai/bot${token}/getMe" 2>/dev/null)
    local ok=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ok',''))" 2>/dev/null)
    if [ "$ok" = "True" ]; then
        local name=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'].get('first_name',''))" 2>/dev/null)
        local uname=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'].get('username',''))" 2>/dev/null)
        ok "Bot verified: $name (@$uname)"
        echo "$uname" > /tmp/bot_username.txt
        return 0
    else
        return 1
    fi
}

prompt_config() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║       Bot Configuration              ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
    echo ""
    echo -e "You need a Bale bot token and your admin ID."
    echo -e "Get token from ${YELLOW}@BotFather${NC} in Bale."
    echo -e "Your admin ID is your numeric user ID in Bale."
    echo ""

    while true; do
        read -rp $'\033[33mBOT_TOKEN (from BotFather): \033[0m' BOT_TOKEN
        BOT_TOKEN=$(echo "$BOT_TOKEN" | tr -d ' ')
        if [ -z "$BOT_TOKEN" ]; then
            err "Token cannot be empty"
            continue
        fi
        echo -e "${CYAN}Verifying token...${NC}"
        if verify_bot "$BOT_TOKEN"; then
            break
        else
            err "Invalid token. Check and try again."
            echo ""
        fi
    done

    while true; do
        read -rp $'\033[33mADMIN_ID (your numeric user ID): \033[0m' ADMIN_ID
        ADMIN_ID=$(echo "$ADMIN_ID" | tr -d ' ')
        if [ -z "$ADMIN_ID" ] || ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; then
            err "Admin ID must be a number"
            continue
        fi
        ok "Admin ID: $ADMIN_ID"
        break
    done

    echo ""
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(4))" 2>/dev/null || echo "admin")
    SECRET_PATH="/${SECRET}"
    write_config "$BOT_TOKEN" "$ADMIN_ID" "$SECRET_PATH"
}

# ═══════════════════════════════════════════════════════════
#  KARPANEL COMMAND
# ═══════════════════════════════════════════════════════════

create_karpanel_cmd() {
    cat > "$KARPANEL_CMD" <<'KARPANEL_SCRIPT'
#!/bin/bash
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
DIR="/opt/employer-panel"
SERVICE="employer-panel"
GIT_REPO="https://github.com/AH-Foud/employer-panel.git"

ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

show_menu() {
    clear
    echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║        Employer Panel Manager        ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC}  Show panel URL"
    echo -e "  ${GREEN}2)${NC}  Restart panel"
    echo -e "  ${GREEN}3)${NC}  Update panel (from GitHub)"
    echo -e "  ${GREEN}4)${NC}  Reinstall panel"
    echo -e "  ${GREEN}5)${NC}  Uninstall panel"
    echo -e "  ${GREEN}6)${NC}  View logs"
    echo -e "  ${GREEN}0)${NC}  Exit"
    echo ""
    read -rp "Enter choice: " ch
    case "$ch" in
        1) show_url ;;
        2) restart_panel ;;
        3) update_panel ;;
        4) reinstall_panel ;;
        5) uninstall_panel ;;
        6) view_logs ;;
        0) exit 0 ;;
        *) err "Invalid choice"; sleep 2; show_menu ;;
    esac
}

show_url() {
    echo ""
    if [ -f "$DIR/url.txt" ]; then echo -e "${GREEN}Panel URL:${NC} $(cat $DIR/url.txt)"
    else
        IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || curl -s --max-time 5 https://checkip.amazonaws.com 2>/dev/null || hostname -I | awk '{print $1}')
        SECRET=$(python3 -c "from config import SECRET_PATH; print(SECRET_PATH)" 2>/dev/null || echo "")
        echo -e "${YELLOW}Try: http://$IP:5000${SECRET}${NC}"
    fi
    echo ""; read -rp "Press Enter..." x; show_menu
}

restart_panel() {
    echo ""
    systemctl restart "$SERVICE" 2>/dev/null && ok "Panel restarted" || warn "Starting manually..."
    cd "$DIR" && nohup python3 run.py >/dev/null 2>&1 &
    echo ""; read -rp "Press Enter..." x; show_menu
}

update_panel() {
    echo ""
    echo -e "${YELLOW}Pulling latest code from GitHub...${NC}"
    cd "$DIR"
    git stash 2>/dev/null || true
    if ! git pull origin main 2>/dev/null; then
        warn "Git pull failed. Cloning fresh..."
        cd /tmp && rm -rf employer-panel 2>/dev/null
        git clone "$GIT_REPO" 2>/dev/null || { err "Failed to clone"; sleep 3; show_menu; }
        cp -r employer-panel/* "$DIR/" && rm -rf employer-panel
    fi
    pip3 install -r "$DIR/requirements.txt" --break-system-packages 2>/dev/null || pip3 install -r "$DIR/requirements.txt" 2>/dev/null || true
    systemctl restart "$SERVICE" 2>/dev/null || true
    ok "Panel updated and restarted"
    echo ""; read -rp "Press Enter..." x; show_menu
}

reinstall_panel() {
    echo ""
    echo -e "${YELLOW}Reinstalling panel...${NC}"
    cd /tmp && rm -rf employer-panel 2>/dev/null
    git clone "$GIT_REPO" 2>/dev/null || { err "Failed to clone"; sleep 3; show_menu; }
    cp -r employer-panel/* "$DIR/" 2>/dev/null && rm -rf employer-panel
    pip3 install -r "$DIR/requirements.txt" --break-system-packages 2>/dev/null || pip3 install -r "$DIR/requirements.txt" 2>/dev/null || true
    systemctl daemon-reload 2>/dev/null || true
    systemctl restart "$SERVICE" 2>/dev/null || true
    ok "Reinstall complete"
    echo ""; read -rp "Press Enter..." x; show_menu
}

uninstall_panel() {
    echo ""
    echo -e "${RED}Are you sure? This will remove the panel and ALL data.${NC}"
    read -rp "Type 'yes' to confirm: " confirm
    if [ "$confirm" != "yes" ]; then warn "Cancelled"; sleep 2; show_menu; return; fi
    systemctl stop "$SERVICE" 2>/dev/null || true
    systemctl disable "$SERVICE" 2>/dev/null || true
    rm -f "/etc/systemd/system/$SERVICE.service"
    rm -f /etc/nginx/sites-available/employer-panel /etc/nginx/sites-enabled/employer-panel 2>/dev/null
    systemctl reload nginx 2>/dev/null || true
    systemctl daemon-reload
    rm -rf "$DIR"
    rm -f /etc/ssl/employer-panel 2>/dev/null
    rm -f "$0"
    ok "Panel uninstalled"
    exit 0
}

view_logs() {
    echo ""
    journalctl -u "$SERVICE" -n 50 --no-pager 2>/dev/null || echo "No logs available"
    echo ""; read -rp "Press Enter..." x; show_menu
}

if [ "${1:-}" = "menu" ]; then show_menu; exit 0; fi
case "${1:-}" in url) show_url ;; restart) restart_panel ;; update) update_panel ;; uninstall) uninstall_panel ;; logs) view_logs ;; *) show_menu ;; esac
KARPANEL_SCRIPT
    chmod +x "$KARPANEL_CMD"
    ok "Type 'karpanel' anywhere for the management menu"
}

# ═══════════════════════════════════════════════════════════
#  INSTALLER
# ═══════════════════════════════════════════════════════════

main_install() {
    echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     Employer Panel - Installer       ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"

    if [[ $EUID -ne 0 ]]; then
        err "Please run as root: sudo bash install.sh"
        exit 1
    fi

    info "Installing required packages..."
    apt update -y && apt install -y python3 python3-pip python3-venv curl wget git nginx socat dnsutils 2>/dev/null || true

    mkdir -p "$INSTALL_DIR"
    cp -r "$DIR"/* "$INSTALL_DIR/" 2>/dev/null || true
    [ -d "$INSTALL_DIR/data" ] || mkdir -p "$INSTALL_DIR/data"

    # create config writer helper
    cat > /tmp/write_config.py << 'PYEOF'
import sys, os
token, admin_id, secret = sys.argv[1], sys.argv[2], sys.argv[3]
cfg = f'''# -*- coding: utf-8 -*-
BOT_TOKEN = "{token}"
ADMIN_ID = {admin_id}
BASE_URL = f"https://tapi.bale.ai/bot{{BOT_TOKEN}}"
DATA_DIR = "data"
DATABASE_PATH = f"{{DATA_DIR}}/database.db"
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
SECRET_PATH = "{secret}"
SYNC_BASE_URL = ""
SYNC_API_KEY = ""
AI_BASE_URL = ""
AI_API_KEY = ""
AI_MODEL = "gpt-4o-mini"
VOICE_DIR = f"{{DATA_DIR}}/voices"
AI_PROMPT = (
    "\u062a\u0648 \u06cc\u0647 \u062f\u0633\u062a\u06cc\u0627\u0631 \u0647\u0648\u0634\u0645\u0646\u062f\u06cc. \u0644\u06cc\u0633\u062a SOP\u0647\u0627\u06cc \u062a\u0639\u0631\u06cc\u0641 \u0634\u062f\u0647:\\n{{sops}}\\n\\n"
    "\u067e\u06cc\u0627\u0645 \u06a9\u0627\u0631\u0628\u0631:\\n{{message}}\\n\\n"
    "\u06a9\u062f\u0627\u0645 SOP \u0645\u0646\u0627\u0633\u0628 \u0627\u06cc\u0646 \u0633\u0648\u0627\u0644\u0647\u061f \u0641\u0642\u0637 \u0627\u0633\u0645 \u062f\u0642\u06cc\u0642 SOP \u0631\u0648 \u0628\u0646\u0648\u06cc\u0633. "
    "\u0627\u06af\u0631 \u0647\u06cc\u0686\u06a9\u062f\u0648\u0645 \u0645\u0646\u0627\u0633\u0628 \u0646\u0628\u0648\u062f\u060c \u0628\u0646\u0648\u06cc\u0633: none"
)
'''
with open('/opt/employer-panel/config.py', 'w', encoding='utf-8') as f:
    f.write(cfg)
PYEOF

    # prompt for config BEFORE install
    prompt_config

    info "Installing Python dependencies..."
    cd "$INSTALL_DIR"
    pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt 2>/dev/null || true

    # init database
    info "Initializing database..."
    python3 -c "import database; database.init_db()" 2>/dev/null || true

    echo -e "\n${BLUE}────────────────────────────────────────${NC}"
    echo -e "${BLUE}  Installation method:${NC}"
    echo -e "  ${GREEN}1)${NC} Direct IP (http://IP:5000${SECRET_PATH})"
    echo -e "  ${GREEN}2)${NC} Subdomain with SSL (https://domain${SECRET_PATH})"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    read -rp $'\033[33mChoice (1 or 2): \033[0m' choice

    if [[ "$choice" == "1" ]]; then
        install_direct_ip
    elif [[ "$choice" == "2" ]]; then
        install_subdomain
    else
        err "Invalid choice"
        exit 1
    fi

    create_karpanel_cmd

    echo -e "\n${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║      Installation Complete!           ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
    echo -e "${CYAN}  Type 'karpanel' anytime for the management menu${NC}"
    echo -e "${CYAN}  ─────────────────────────────${NC}"
    echo ""
    cat "$INSTALL_DIR/url.txt" 2>/dev/null
    echo ""
    BotUsername=$(cat /tmp/bot_username.txt 2>/dev/null || echo "your_bot")
    echo -e "${YELLOW}  Bot username: @${BotUsername}${NC}"
    echo -e "${YELLOW}  Employers must start this bot in Bale to receive messages${NC}"
}

install_direct_ip() {
    IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || curl -s --max-time 5 https://checkip.amazonaws.com 2>/dev/null || hostname -I | awk '{print $1}')
    FINAL_URL="http://$IP:5000$SECRET_PATH"
    echo "$FINAL_URL" > "$INSTALL_DIR/url.txt"
    ok "Server IP: $IP"

    info "Creating systemd service..."
    cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=Employer Panel - Bale Bot + Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$(which python3) $INSTALL_DIR/run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable $SERVICE_NAME
    systemctl restart $SERVICE_NAME

    ufw allow 5000 2>/dev/null || true

    echo -e "\n${GREEN}  Panel URL: $FINAL_URL${NC}"
    echo -e "${YELLOW}  Open port 5000 in your firewall if needed${NC}"
}

install_subdomain() {
    echo ""
    read -rp "Subdomain (e.g. bot.example.com): " DOMAIN
    IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || curl -s --max-time 5 https://checkip.amazonaws.com 2>/dev/null || hostname -I | awk '{print $1}')
    FINAL_URL="https://$DOMAIN$SECRET_PATH"
    echo "$FINAL_URL" > "$INSTALL_DIR/url.txt"

    # check DNS
    info "Checking DNS for $DOMAIN ..."
    DOMAIN_IP=$(dig +short "$DOMAIN" 2>/dev/null || host "$DOMAIN" 2>/dev/null | grep "has address" | awk '{print $NF}' || nslookup "$DOMAIN" 2>/dev/null | grep "Address" | tail -1 | awk '{print $2}')
    if [[ -z "$DOMAIN_IP" ]]; then
        warn "Could not resolve $DOMAIN. Make sure the A record points to $IP"
        read -rp "Continue anyway? (y/n): " confirm
        if [ "$confirm" != "y" ]; then exit 1; fi
    elif [[ "$DOMAIN_IP" != "$IP" ]]; then
        warn "$DOMAIN resolves to $DOMAIN_IP, not $IP"
        warn "Point your subdomain A record to $IP first, then re-run"
        read -rp "Continue anyway? (y/n): " confirm
        if [ "$confirm" != "y" ]; then exit 1; fi
    fi

    # stop anything on port 80
    systemctl stop nginx 2>/dev/null || true
    systemctl stop apache2 2>/dev/null || true
    fuser -k 80/tcp 2>/dev/null || true
    sleep 1

    apt install -y socat 2>/dev/null || true
    ufw allow 80/tcp 2>/dev/null || true
    firewall-cmd --add-port=80/tcp --permanent 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true

    # get SSL via acme.sh standalone
    info "Getting SSL certificate from Let's Encrypt..."
    if ! command -v acme.sh &>/dev/null; then
        curl -s https://get.acme.sh | sh
        source ~/.bashrc 2>/dev/null || true
    fi
    ~/.acme.sh/acme.sh --upgrade --auto-upgrade 2>/dev/null || true

    ACME_LISTEN=""
    if ! curl -s --max-time 3 https://api.ipify.org 2>/dev/null | grep -q '\.'; then
        ACME_LISTEN="--listen-v6"
    fi

    ~/.acme.sh/acme.sh --set-default-ca --server letsencrypt --force 2>/dev/null
    if ~/.acme.sh/acme.sh --issue -d "$DOMAIN" $ACME_LISTEN --standalone --httpport 80 --force --log 2>/dev/null; then
        ok "SSL certificate obtained"
    else
        warn "First attempt failed. Trying again..."
        sleep 2
        fuser -k 80/tcp 2>/dev/null || true
        sleep 1
        ~/.acme.sh/acme.sh --issue -d "$DOMAIN" $ACME_LISTEN --standalone --httpport 80 --force --log 2>/dev/null || {
            err "SSL certificate issuance failed."
            echo -e "${YELLOW}Check: 1) A record points here  2) Port 80 open  3) No other service on port 80${NC}"
            exit 1
        }
    fi

    mkdir -p /etc/ssl/employer-panel
    ~/.acme.sh/acme.sh --install-cert -d "$DOMAIN" \
        --key-file /etc/ssl/employer-panel/key.pem \
        --fullchain-file /etc/ssl/employer-panel/fullchain.pem \
        --reloadcmd "systemctl restart nginx"
    chmod 600 /etc/ssl/employer-panel/key.pem
    chmod 644 /etc/ssl/employer-panel/fullchain.pem
    ~/.acme.sh/acme.sh --install-cronjob 2>/dev/null || true
    ok "SSL certificate installed"

    # configure nginx with secret path
    info "Configuring Nginx reverse proxy..."
    cat > /etc/nginx/sites-available/employer-panel <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate /etc/ssl/employer-panel/fullchain.pem;
    ssl_certificate_key /etc/ssl/employer-panel/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    root /var/www/html;
    location / {
        return 404;
    }

    location $SECRET_PATH/ {
        proxy_pass http://$IP:5000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix $SECRET_PATH;
        proxy_read_timeout 120s;
        proxy_buffering off;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/employer-panel /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl start nginx || {
        err "Nginx error. Check /var/log/nginx/error.log"
        systemctl restart nginx 2>/dev/null || true
    }
    ok "Nginx configured"

    # systemd service
    info "Creating systemd service..."
    cat > /etc/systemd/system/$SERVICE_NAME.service <<EOF
[Unit]
Description=Employer Panel - Bale Bot + Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$(which python3) $INSTALL_DIR/run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable $SERVICE_NAME
    systemctl restart $SERVICE_NAME

    # auto renewal
    info "Setting up auto SSL renewal..."
    ~/.acme.sh/acme.sh --cron --home ~/.acme.sh >/dev/null 2>&1
    (crontab -l 2>/dev/null; echo "0 0 * * * ~/.acme.sh/acme.sh --cron --home ~/.acme.sh >/dev/null 2>&1") | crontab - 2>/dev/null || true
    ok "Auto SSL renewal configured"

    echo -e "\n${GREEN}  Panel URL: $FINAL_URL${NC}"
    echo -e "${YELLOW}  Keep this URL secret! Only you can access the panel.${NC}"
}

# ═══════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════

if [[ "$1" == "--menu" ]]; then
    create_karpanel_cmd
    bash "$KARPANEL_CMD" menu
    exit 0
fi

main_install
