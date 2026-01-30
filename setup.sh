#!/bin/bash

# Update and install system dependencies
if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip git curl socat gnupg nginx certbot python3-certbot-nginx
else
    apt-get update
    apt-get install -y python3 python3-pip git curl socat gnupg nginx certbot python3-certbot-nginx
fi

# Install Xray (Official Script)
echo "Installing Xray..."
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# Configure Xray
echo "Configuring Xray..."
mkdir -p /usr/local/etc/xray
if [ -f "xray_config.json" ]; then
    cp xray_config.json /usr/local/etc/xray/config.json
fi
systemctl restart xray

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

# Configure Nginx
echo "Configuring Nginx..."
cat <<EOF > /etc/nginx/sites-available/diana-vpn
server {
    listen 80;
    server_name $domain_input;

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
    }

    location /vmess {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:10002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }

    location /trojan {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:10003;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }

    location /ss {
        proxy_redirect off;
        proxy_pass http://127.0.0.1:10004;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }
}
EOF

ln -s /etc/nginx/sites-available/diana-vpn /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
systemctl restart nginx

# SSL Certificate (Optional but recommended)
echo "Installing SSL Certificate..."
certbot --nginx -d "$domain_input" --non-interactive --agree-tos --email admin@"$domain_input" --redirect || echo "SSL setup failed. Check domain settings."

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
