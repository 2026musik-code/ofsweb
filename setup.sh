#!/bin/bash
set -e

# Update and install system dependencies
echo "Updating package list..."
if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip git curl socat gnupg nginx certbot python3-certbot-nginx dropbear websocat
else
    apt-get update -y
    apt-get install -y python3 python3-pip git curl socat gnupg nginx certbot python3-certbot-nginx dropbear websocat
fi

# Configure Dropbear
echo "Configuring Dropbear..."
sed -i 's/NO_START=1/NO_START=0/g' /etc/default/dropbear
sed -i 's/DROPBEAR_PORT=22/DROPBEAR_PORT=109/g' /etc/default/dropbear
sed -i 's/DROPBEAR_EXTRA_ARGS=/DROPBEAR_EXTRA_ARGS="-p 143"/g' /etc/default/dropbear
service dropbear restart

# Setup WS-ePro (using websocat as bridge)
# Nginx /ssh -> 10015 -> websocat -> 109 (Dropbear)
echo "Setting up WS-ePro..."
cat <<EOF > /etc/systemd/system/ws-epro.service
[Unit]
Description=WS-ePro (Websocat)
After=network.target

[Service]
ExecStart=/usr/bin/websocat -E --binary-type=arraybuffer ws-l:127.0.0.1:10015 tcp:127.0.0.1:109
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ws-epro
systemctl start ws-epro

# Install Xray
echo "Installing Xray..."
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# Install Python dependencies
echo "Installing Python dependencies..."
python3 -m pip install -r requirements.txt

# Prompt for Domain
read -p "Masukkan Domain VPS Anda (contoh: vpn.example.com): " domain_input

if [ -z "$domain_input" ]; then
    echo "Domain tidak boleh kosong. Menggunakan default: localhost"
    domain_input="localhost"
fi

python3 init_domain.py "$domain_input"
python3 init_admin.py

# Configure Xray
echo "Configuring Xray..."
mkdir -p /usr/local/etc/xray
if [ -f "xray_config.json" ]; then
    cp xray_config.json /usr/local/etc/xray/config.json
fi
systemctl restart xray

# Configure Nginx (Front-End 443)
echo "Configuring Nginx..."
mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled

cat <<EOF > /etc/nginx/sites-available/diana-vpn
server {
    listen 80;
    server_name $domain_input;

    # Global Tuning
    tcp_nodelay on;

    # Auto Redirect to HTTPS
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $domain_input;

    ssl_certificate /etc/letsencrypt/live/$domain_input/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$domain_input/privkey.pem;

    # Global Tuning
    tcp_nodelay on;

    # Web Panel
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    # SSH WS
    location /ssh {
        proxy_pass http://127.0.0.1:10015;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_buffering off;
    }

    # Xray VLESS WS
    location /vless {
        proxy_pass http://127.0.0.1:10001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_buffering off;
    }

    # Xray VMess WS
    location /vmess {
        proxy_pass http://127.0.0.1:10002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_buffering off;
    }

    # Xray Trojan WS
    location /trojan {
        proxy_pass http://127.0.0.1:10003;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_buffering off;
    }

    # Xray SS WS
    location /ss {
        proxy_pass http://127.0.0.1:10004;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_buffering off;
    }
}
EOF

ln -s /etc/nginx/sites-available/diana-vpn /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# SSL with Certbot Nginx Plugin
echo "Installing SSL..."
certbot --nginx -d "$domain_input" --non-interactive --agree-tos --email admin@"$domain_input" --redirect

# Setup Systemd
echo "Setting up Service..."
if [ -f "diana-vpn.service" ]; then
    CUR_DIR=$(pwd)
    sed -i "s|/root/ofsweb|$CUR_DIR|g" diana-vpn.service
    cp diana-vpn.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable diana-vpn.service
    systemctl start diana-vpn.service
fi

echo "Setup complete. Xray & Nginx Front-End ready."
echo "SSH WS Port: 443 (Path: /ssh)"
