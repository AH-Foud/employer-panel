#!/bin/bash
# ============================================================
# نصب‌کننده خودکار ربات بله + پنل مدیریت
# اجرا: sudo bash install.sh
# ============================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   نصب‌کننده ربات بله + پنل مدیریت   ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"

# root check
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}لطفاً با root اجرا کنید: sudo bash install.sh${NC}"
    exit 1
fi

# Python check
if ! command -v python3 &>/dev/null; then
    echo -e "${YELLOW}[1] نصب Python3...${NC}"
    apt update -y && apt install -y python3 python3-pip python3-venv curl wget git
fi

echo -e "\n${BLUE}[?] روش نصب را انتخاب کنید:${NC}"
echo -e "  ${GREEN}1)${NC} آی‌پی مستقیم (فقط پورت ۵۰۰۰)"
echo -e "  ${GREEN}2)${NC} ساب‌دامنه با SSL (نیاز به کلودفلر)"
read -rp $'\033[33mانتخاب (1 یا 2): \033[0m' choice

# ─── روش اول: آی‌پی مستقیم ─────────────────────────────
if [[ "$choice" == "1" ]]; then
    IP=$(curl -s ifconfig.me || curl -s icanhazip.com)
    echo -e "\n${GREEN}آی‌پی سرور: $IP${NC}"

    echo -e "${YELLOW}[2] نصب وابستگی‌های Python...${NC}"
    pip3 install -r "$DIR/requirements.txt" --break-system-packages 2>/dev/null || pip3 install -r "$DIR/requirements.txt"

    # systemd service
    echo -e "${YELLOW}[3] ایجاد سرویس systemd...${NC}"
    cat > /etc/systemd/system/balebot.service <<EOF
[Unit]
Description=Bale Bot + Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$DIR
ExecStart=$(which python3) $DIR/run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable balebot
    systemctl restart balebot

    FINAL_URL="http://$IP:5000"
    echo -e "\n${GREEN}✓ نصب کامل شد!${NC}"
    echo -e "${CYAN}  لینک پنل: ${FINAL_URL}${NC}"
    echo -e "${YELLOW}  نکته: پورت ۵۰۰۰ را در فایروال باز کنید.${NC}"
    exit 0
fi

# ─── روش دوم: ساب‌دامنه با SSL ─────────────────────────
if [[ "$choice" != "2" ]]; then
    echo -e "${RED}انتخاب نامعتبر${NC}"
    exit 1
fi

# دریافت اطلاعات
read -rp $'\033[33mساب‌دامنه (مثلاً bot.example.com): \033[0m' DOMAIN
read -rp $'\033[33mCloudflare API Token (ترجیحاً) یا Global API Key: \033[0m' CF_KEY
read -rp $'\033[33mایمیل برای SSL (مثلاً admin@example.com): \033[0m' SSL_EMAIL
IP=$(curl -s ifconfig.me || curl -s icanhazip.com)

echo -e "\n${YELLOW}[1] تنظیم DNS در کلودفلر...${NC}"

# تشخیص Zone ID
ZONE_NAME="${DOMAIN#*.}"
ZONE_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$ZONE_NAME" \
    -H "Authorization: Bearer $CF_KEY" \
    -H "Content-Type: application/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'] if d.get('result') else '')" 2>/dev/null)

if [[ -z "$ZONE_ID" ]]; then
    # شاید API Key وارد شده Global Key باشد (با ایمیل)
    read -rp $'\033[33mایمیل حساب کلودفلر (برای Global Key): \033[0m' CF_EMAIL
    ZONE_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$ZONE_NAME" \
        -H "X-Auth-Email: $CF_EMAIL" \
        -H "X-Auth-Key: $CF_KEY" \
        -H "Content-Type: application/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'] if d.get('result') else '')" 2>/dev/null)
    if [[ -z "$ZONE_ID" ]]; then
        echo -e "${RED}خطا: دامنه $ZONE_NAME در کلودفلر یافت نشد${NC}"
        exit 1
    fi
    AUTH_HEADERS=("-H" "X-Auth-Email: $CF_EMAIL" "-H" "X-Auth-Key: $CF_KEY")
else
    AUTH_HEADERS=("-H" "Authorization: Bearer $CF_KEY")
fi

# حذف رکورد قبلی (اگر هست) و ایجاد جدید
EXISTING=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=A&name=$DOMAIN" \
    "${AUTH_HEADERS[@]}" -H "Content-Type: application/json")
EXISTING_ID=$(echo "$EXISTING" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'] if d.get('result') else '')" 2>/dev/null)

if [[ -n "$EXISTING_ID" ]]; then
    curl -s -X DELETE "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$EXISTING_ID" \
        "${AUTH_HEADERS[@]}" -H "Content-Type: application/json" >/dev/null
    echo -e "${YELLOW}  رکورد قدیمی حذف شد${NC}"
fi

RESULT=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
    "${AUTH_HEADERS[@]}" -H "Content-Type: application/json" \
    -d "{\"type\":\"A\",\"name\":\"$DOMAIN\",\"content\":\"$IP\",\"ttl\":120,\"proxied\":false}")
SUCCESS=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success'))")

if [[ "$SUCCESS" != "True" ]]; then
    echo -e "${RED}خطا در ایجاد رکورد DNS:${NC}"
    echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"
    exit 1
fi
echo -e "${GREEN}  ✓ رکورد A برای $DOMAIN -> $IP ایجاد شد${NC}"

# ─── نصب وابستگی‌ها ────────────────────────────────
echo -e "${YELLOW}[2] نصب وابستگی‌های Python...${NC}"
pip3 install -r "$DIR/requirements.txt" --break-system-packages 2>/dev/null || pip3 install -r "$DIR/requirements.txt"

# ─── SSL با acme.sh ────────────────────────────────
echo -e "${YELLOW}[3] دریافت SSL certificate با acme.sh...${NC}"
if ! command -v acme.sh &>/dev/null; then
    curl https://get.acme.sh | sh -s email="$SSL_EMAIL" 2>/dev/null
    source ~/.bashrc 2>/dev/null || true
fi

# ثبت DNS API در acme.sh
if [[ -n "$CF_EMAIL" ]]; then
    export CF_Email="$CF_EMAIL"
    export CF_Key="$CF_KEY"
else
    # برای API Token
    export CF_Token="$CF_KEY"
    export CF_Account_ID="$ZONE_ID"
fi

~/.acme.sh/acme.sh --issue --dns dns_cf -d "$DOMAIN" --force --log 2>/dev/null || {
    echo -e "${YELLOW}  تلاش با روش standalone...${NC}"
    apt install -y socat 2>/dev/null
    ~/.acme.sh/acme.sh --issue --standalone -d "$DOMAIN" --force --log 2>/dev/null || {
        echo -e "${RED}خطا در دریافت SSL. لطفاً دستی اجرا کنید:${NC}"
        echo -e "  ~/.acme.sh/acme.sh --issue --dns dns_cf -d $DOMAIN"
        exit 1
    }
}

mkdir -p /etc/ssl/balebot
~/.acme.sh/acme.sh --install-cert -d "$DOMAIN" \
    --key-file /etc/ssl/balebot/key.pem \
    --fullchain-file /etc/ssl/balebot/fullchain.pem \
    --reloadcmd "systemctl reload nginx 2>/dev/null || true"

echo -e "${GREEN}  ✓ SSL certificate دریافت شد${NC}"

# ─── نصب Nginx ─────────────────────────────────────
echo -e "${YELLOW}[4] تنظیم Nginx反向 پراکسی...${NC}"
if ! command -v nginx &>/dev/null; then
    apt install -y nginx
fi

cat > /etc/nginx/sites-available/balebot <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate /etc/ssl/balebot/fullchain.pem;
    ssl_certificate_key /etc/ssl/balebot/key.pem;
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

ln -sf /etc/nginx/sites-available/balebot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx || {
    echo -e "${RED}خطا در تنظیم Nginx. لاگ: /var/log/nginx/error.log${NC}"
    exit 1
}
echo -e "${GREEN}  ✓ Nginx تنظیم شد${NC}"

# ─── systemd service ──────────────────────────────
echo -e "${YELLOW}[5] ایجاد سرویس systemd...${NC}"
cat > /etc/systemd/system/balebot.service <<EOF
[Unit]
Description=Bale Bot + Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$DIR
ExecStart=$(which python3) $DIR/run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable balebot
systemctl restart balebot

# ─── تمدید خودکار SSL ─────────────────────────────
echo -e "${YELLOW}[6] تنظیم تمدید خودکار SSL...${NC}"
~/.acme.sh/acme.sh --cron --home ~/.acme.sh >/dev/null 2>&1
(crontab -l 2>/dev/null; echo "0 0 * * * ~/.acme.sh/acme.sh --cron --home ~/.acme.sh >/dev/null 2>&1") | crontab -
echo -e "${GREEN}  ✓ تمدید خودکار SSL فعال شد${NC}"

# ─── اتمام ─────────────────────────────────────────
FINAL_URL="https://$DOMAIN"
echo -e "\n${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         نصب با موفقیت کامل شد!       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo -e "${CYAN}  لینک پنل مدیریت: ${FINAL_URL}${NC}"
echo -e "${CYAN}  پورت داخلی: 127.0.0.1:5000${NC}"
echo -e ""
echo -e "${YELLOW}  نکات مهم:${NC}"
echo -e "  - حتماً توکن بات و ADMIN_ID را در config.py تنظیم کنید"
echo -e "  - برای مشاهده لاگ: journalctl -u balebot -f"
echo -e "  - برای ریستارت: systemctl restart balebot"
echo -e "${GREEN}  ──────────────────────────────${NC}"
