#!/bin/bash

# Update and install system dependencies
# Check if sudo is available, otherwise run directly (assuming root)
if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip git
else
    apt-get update
    apt-get install -y python3 python3-pip git
fi

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

# Setup Systemd Service
echo "Setting up Systemd Service..."
if [ -f "diana-vpn.service" ]; then
    # Adjust paths in service file if not in /root/ofsweb
    CUR_DIR=$(pwd)
    sed -i "s|/root/ofsweb|$CUR_DIR|g" diana-vpn.service

    if command -v sudo >/dev/null 2>&1; then
        sudo cp diana-vpn.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable diana-vpn.service
        sudo systemctl start diana-vpn.service
    else
        cp diana-vpn.service /etc/systemd/system/
        systemctl daemon-reload
        systemctl enable diana-vpn.service
        systemctl start diana-vpn.service
    fi
    echo "Service started successfully."
fi

echo "Setup complete. Domain configured to $domain_input."
echo "Web Panel is running in the background."
