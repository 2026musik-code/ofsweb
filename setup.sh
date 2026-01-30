#!/bin/bash

# Update and install system dependencies
if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip git curl socat gnupg nginx certbot
else
    apt-get update
    apt-get install -y python3 python3-pip git curl socat gnupg nginx certbot
fi

# Install Xray (Official Script)
echo "Installing Xray..."
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# Install Python dependencies
pip3 install -r requirements.txt

# Prompt for Domain
read -p "Masukkan Domain VPS Anda (contoh: vpn.example.com): " domain_input

if [ -z "$domain_input" ]; then
    echo "Domain tidak boleh kosong. Menggunakan default: localhost"
    domain_input="localhost"
fi

python3 init_domain.py "$domain_input"

# Initialize Admin
echo "Initializing Default Admin..."
python3 init_admin.py

# SSL Certificate (Standalone Mode for Xray)
echo "Installing SSL Certificate..."
systemctl stop nginx
certbot certonly --standalone -d "$domain_input" --non-interactive --agree-tos --email admin@"$domain_input" || echo "SSL setup failed. Check domain settings."

# Configure Xray
echo "Configuring Xray..."
mkdir -p /usr/local/etc/xray
if [ -f "xray_config.json" ]; then
    cp xray_config.json /usr/local/etc/xray/config.json
    # Replace DOMAIN_PLACEHOLDER with actual domain
    sed -i "s|DOMAIN_PLACEHOLDER|$domain_input|g" /usr/local/etc/xray/config.json
fi
systemctl restart xray

# Configure Nginx (Backend for Fallback)
echo "Configuring Nginx..."
cat <<EOF > /etc/nginx/sites-available/diana-vpn
server {
    listen 8080 proxy_protocol; # Listen on localhost 8080, accept proxy protocol from Xray
    server_name $domain_input;

    # Correct IP from Xray Fallback
    set_real_ip_from 127.0.0.1;
    real_ip_header proxy_protocol;

    # Global Tuning
    tcp_nodelay on;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    location /vless {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:10001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;

        # Low Latency Tuning
        proxy_buffering off;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }

    location /vmess {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:10002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;

        # Low Latency Tuning
        proxy_buffering off;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }

    location /trojan {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:10003;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;

        # Low Latency Tuning
        proxy_buffering off;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }

    location /ss {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:10004;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;

        # Low Latency Tuning
        proxy_buffering off;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
}

# Standard Port 80 Listener (Redirect to HTTPS or Handle Non-TLS WS)
server {
    listen 80;
    server_name $domain_input;

    # Global Tuning
    tcp_nodelay on;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    # WS Paths for Non-TLS
    location /vless {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:10001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_buffering off;
    }

    location /vmess {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:10002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_buffering off;
    }

    location /trojan {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:10003;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_buffering off;
    }

    location /ss {
        proxy_redirect off;
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
systemctl restart nginx

# Setup Systemd Service for Web Panel
echo "Setting up Systemd Service..."
if [ -f "diana-vpn.service" ]; then
    CUR_DIR=$(pwd)
    sed -i "s|/root/ofsweb|$CUR_DIR|g" diana-vpn.service

    cp diana-vpn.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable diana-vpn.service
    systemctl start diana-vpn.service
    echo "Service started successfully."
fi

echo "Setup complete. Access your panel at https://$domain_input"
echo "NOTE: Xray is now managing Port 443 with SNI Fallback to Nginx."
