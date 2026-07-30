#!/bin/bash
# ============================================================
# Employer Panel - Bale Bot + Web Dashboard Installer
# Run: sudo bash install.sh
# ============================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/opt/employer-panel"
SERVICE_NAME="employer-panel"
KARPANEL_CMD="/usr/local/bin/karpanel"
GIT_REPO="https://github.com/AH-Foud/employer-panel.git"

# ─── Color helpers ───
info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ═══════════════════════════════════════════════════════════
#  KARPANEL COMMAND (management menu)
# ═══════════════════════════════════════════════════════════

create_karpanel_cmd() {
    cat > "$KARPANEL_CMD" <<'KARPANEL_SCRIPT'
#!/bin/bash
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
DIR="/opt/employer-panel"
SERVICE="employer-panel"
GIT_REPO="https://github.com/AH-Foud/employer-panel.git"

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
        *) echo -e "${RED}Invalid choice${NC}"; sleep 2; show_menu ;;
    esac
}

show_url() {
    echo ""
    if [ -f "$DIR/url.txt" ]; then
        echo -e "${GREEN}Panel URL:${NC} $(cat $DIR/url.txt)"
    else
        echo -e "${YELLOW}Panel URL file not found.${NC}"
        IP=$(curl -s ifconfig.me || curl -s icanhazip.com)
        echo -e "${YELLOW}Try: http://$IP:5000${NC}"
    fi
    echo ""
    read -rp "Press Enter to return..." x
    show_menu
}

restart_panel() {
    echo ""
    systemctl restart "$SERVICE" 2>/dev/null && ok "Panel restarted" || warn "Service not found, starting manually..."
    cd "$DIR" && nohup python3 run.py >/dev/null 2>&1 &
    echo ""
    read -rp "Press Enter to return..." x
    show_menu
}

update_panel() {
    echo ""
    echo -e "${YELLOW}Pulling latest code from GitHub...${NC}"
    cd "$DIR"
    git stash 2>/dev/null || true
    git pull origin main 2>/dev/null || {
        warn "Git pull failed. Cloning fresh..."
        cd /tmp
        rm -rf employer-panel 2>/dev/null
        git clone "$GIT_REPO" 2>/dev/null || { err "Failed to clone repo"; sleep 3; show_menu; }
        cp -r employer-panel/* "$DIR/"
        rm -rf employer-panel
    }
    pip3 install -r "$DIR/requirements.txt" --break-system-packages 2>/dev/null || pip3 install -r "$DIR/requirements.txt" 2>/dev/null || true
    systemctl restart "$SERVICE" 2>/dev/null || true
    ok "Panel updated and restarted"
    echo ""
    read -rp "Press Enter to return..." x
    show_menu
}

reinstall_panel() {
    echo ""
    echo -e "${YELLOW}Reinstalling panel...${NC}"
    cd /tmp
    rm -rf employer-panel 2>/dev/null
    git clone "$GIT_REPO" 2>/dev/null || { err "Failed to clone repo"; sleep 3; show_menu; }
    cp -r employer-panel/* "$DIR/" 2>/dev/null
    rm -rf employer-panel
    pip3 install -r "$DIR/requirements.txt" --break-system-packages 2>/dev/null || pip3 install -r "$DIR/requirements.txt" 2>/dev/null || true
    systemctl daemon-reload 2>/dev/null || true
    systemctl restart "$SERVICE" 2>/dev/null || true
    ok "Reinstall complete"
    echo ""
    read -rp "Press Enter to return..." x
    show_menu
}

uninstall_panel() {
    echo ""
    echo -e "${RED}Are you sure? This will remove the panel and all data.${NC}"
    read -rp "Type 'yes' to confirm: " confirm
    if [ "$confirm" != "yes" ]; then
        warn "Cancelled"
        sleep 2
        show_menu
        return
    fi
    systemctl stop "$SERVICE" 2>/dev/null || true
    systemctl disable "$SERVICE" 2>/dev/null || true
    rm -f "/etc/systemd/system/$SERVICE.service"
    rm -f /etc/nginx/sites-available/employer-panel 2>/dev/null
    rm -f /etc/nginx/sites-enabled/employer-panel 2>/dev/null
    systemctl reload nginx 2>/dev/null || true
    systemctl daemon-reload
    rm -rf "$DIR"
    rm -f "$0"
    ok "Panel uninstalled"
    exit 0
}

view_logs() {
    echo ""
    journalctl -u "$SERVICE" -n 50 --no-pager 2>/dev/null || echo "No logs available"
    echo ""
    read -rp "Press Enter to return..." x
    show_menu
}

# ─── Run ───
if [ "$1" = "menu" ]; then show_menu; exit 0; fi
case "${1:-}" in
    url)    show_url ;;
    restart) restart_panel ;;
    update) update_panel ;;
    uninstall) uninstall_panel ;;
    logs)   view_logs ;;
    *)      show_menu ;;
esac
KARPANEL_SCRIPT
    chmod +x "$KARPANEL_CMD"
    ok "Created command: karpanel (type 'karpanel' anywhere)"
}

# ═══════════════════════════════════════════════════════════
#  MAIN INSTALLER
# ═══════════════════════════════════════════════════════════

main_install() {
    echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     Employer Panel - Installer       ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"

    # root check
    if [[ $EUID -ne 0 ]]; then
        err "Please run as root: sudo bash install.sh"
        exit 1
    fi

    # install deps
    info "Installing required packages..."
    apt update -y && apt install -y python3 python3-pip python3-venv curl wget git nginx 2>/dev/null || true

    # setup directory
    mkdir -p "$INSTALL_DIR"
    cp -r "$DIR"/* "$INSTALL_DIR/" 2>/dev/null || cp "$DIR"/*.py "$DIR"/*.txt "$DIR"/*.sh "$INSTALL_DIR/" 2>/dev/null || true
    cd "$INSTALL_DIR"

    info "Installing Python dependencies..."
    pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt 2>/dev/null || true

    echo -e "\n${BLUE}────────────────────────────────────────${NC}"
    echo -e "${BLUE}  Installation method:${NC}"
    echo -e "  ${GREEN}1)${NC} Direct IP (http://IP:5000)"
    echo -e "  ${GREEN}2)${NC} Subdomain with SSL (requires Cloudflare)"
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

    # create karpanel command
    create_karpanel_cmd

    echo -e "\n${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║      Installation Complete!           ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
    echo -e "${CYAN}  Type 'karpanel' anytime for management menu${NC}"
    echo -e "${CYAN}  ─────────────────────────────${NC}"
    echo ""
    cat "$INSTALL_DIR/url.txt" 2>/dev/null
    echo ""
    echo -e "${YELLOW}  Important: Edit config.py and set your BOT_TOKEN & ADMIN_ID${NC}"
    echo -e "${YELLOW}  Then run: karpanel${NC}"
}

install_direct_ip() {
    IP=$(curl -s ifconfig.me || curl -s icanhazip.com)
    FINAL_URL="http://$IP:5000"
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

    # firewall
    ufw allow 5000 2>/dev/null || true

    ok "Panel installed on direct IP"
    echo -e "${GREEN}  URL: $FINAL_URL${NC}"
    echo -e "${YELLOW}  Note: Open port 5000 in your firewall if needed${NC}"
}

install_subdomain() {
    echo ""
    read -rp "Subdomain (e.g. bot.example.com): " DOMAIN
    read -rp "Cloudflare API Token (recommended) or Global Key: " CF_KEY
    read -rp "Email for SSL certificate: " SSL_EMAIL
    IP=$(curl -s ifconfig.me || curl -s icanhazip.com)

    FINAL_URL="https://$DOMAIN"
    echo "$FINAL_URL" > "$INSTALL_DIR/url.txt"

    info "Setting up Cloudflare DNS..."

    ZONE_NAME="${DOMAIN#*.}"
    ZONE_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$ZONE_NAME" \
        -H "Authorization: Bearer $CF_KEY" \
        -H "Content-Type: application/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'] if d.get('result') else '')" 2>/dev/null)

    if [[ -z "$ZONE_ID" ]]; then
        read -rp "Cloudflare account email (for Global Key): " CF_EMAIL
        ZONE_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$ZONE_NAME" \
            -H "X-Auth-Email: $CF_EMAIL" \
            -H "X-Auth-Key: $CF_KEY" \
            -H "Content-Type: application/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'] if d.get('result') else '')" 2>/dev/null)
        if [[ -z "$ZONE_ID" ]]; then
            err "Domain $ZONE_NAME not found in Cloudflare"
            exit 1
        fi
        AUTH_HEADERS=("-H" "X-Auth-Email: $CF_EMAIL" "-H" "X-Auth-Key: $CF_KEY")
    else
        AUTH_HEADERS=("-H" "Authorization: Bearer $CF_KEY")
    fi

    # Delete existing A record if any
    EXISTING=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=A&name=$DOMAIN" \
        "${AUTH_HEADERS[@]}" -H "Content-Type: application/json")
    EXISTING_ID=$(echo "$EXISTING" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'] if d.get('result') else '')" 2>/dev/null)
    if [[ -n "$EXISTING_ID" ]]; then
        curl -s -X DELETE "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$EXISTING_ID" \
            "${AUTH_HEADERS[@]}" -H "Content-Type: application/json" >/dev/null
        info "Removed old DNS record"
    fi

    # Create A record
    RESULT=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
        "${AUTH_HEADERS[@]}" -H "Content-Type: application/json" \
        -d "{\"type\":\"A\",\"name\":\"$DOMAIN\",\"content\":\"$IP\",\"ttl\":120,\"proxied\":false}")
    SUCCESS=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success'))")
    if [[ "$SUCCESS" != "True" ]]; then
        err "DNS record creation failed"
        echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"
        exit 1
    fi
    ok "DNS A record $DOMAIN -> $IP created"

    info "Getting SSL certificate via acme.sh..."
    if ! command -v acme.sh &>/dev/null; then
        curl https://get.acme.sh | sh -s email="$SSL_EMAIL" 2>/dev/null
        source ~/.bashrc 2>/dev/null || true
    fi

    if [[ -n "$CF_EMAIL" ]]; then
        export CF_Email="$CF_EMAIL"
        export CF_Key="$CF_KEY"
    else
        export CF_Token="$CF_KEY"
    fi

    ~/.acme.sh/acme.sh --issue --dns dns_cf -d "$DOMAIN" --force --log 2>/dev/null || {
        warn "DNS challenge failed. Trying standalone..."
        apt install -y socat 2>/dev/null
        ~/.acme.sh/acme.sh --issue --standalone -d "$DOMAIN" --force --log 2>/dev/null || {
            err "SSL failed. Run manually: ~/.acme.sh/acme.sh --issue --dns dns_cf -d $DOMAIN"
            exit 1
        }
    }

    mkdir -p /etc/ssl/employer-panel
    ~/.acme.sh/acme.sh --install-cert -d "$DOMAIN" \
        --key-file /etc/ssl/employer-panel/key.pem \
        --fullchain-file /etc/ssl/employer-panel/fullchain.pem \
        --reloadcmd "systemctl reload nginx 2>/dev/null || true"
    ok "SSL certificate installed"

    info "Configuring Nginx reverse proxy..."
    cat > /etc/nginx/sites-available/employer-panel <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate /etc/ssl/employer-panel/fullchain.pem;
    ssl_certificate_key /etc/ssl/employer-panel/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }

    location /api/voice-proxy/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_read_timeout 120s;
        proxy_buffering off;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/employer-panel /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl restart nginx || {
        err "Nginx config error. Check /var/log/nginx/error.log"
        exit 1
    }
    ok "Nginx configured"

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

    info "Setting up auto SSL renewal..."
    ~/.acme.sh/acme.sh --cron --home ~/.acme.sh >/dev/null 2>&1
    (crontab -l 2>/dev/null; echo "0 0 * * * ~/.acme.sh/acme.sh --cron --home ~/.acme.sh >/dev/null 2>&1") | crontab - 2>/dev/null || true
    ok "Auto SSL renewal configured"

    ok "Panel installed with SSL"
    echo -e "${GREEN}  URL: $FINAL_URL${NC}"
}

# ═══════════════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════════════

if [[ "$1" == "--menu" ]]; then
    create_karpanel_cmd
    bash "$KARPANEL_CMD" menu
    exit 0
fi

main_install
