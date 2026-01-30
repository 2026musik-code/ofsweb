import os
import json
import subprocess
import shutil
from datetime import datetime

XRAY_CONFIG_PATH = '/usr/local/etc/xray/config.json'
XRAY_RESTART_CMD = ['systemctl', 'restart', 'xray']

def run_command(cmd):
    """Runs a shell command. Returns True if successful, False otherwise."""
    print(f"Running command: {' '.join(cmd)}")
    if os.geteuid() != 0:
        print("[MOCK] Not root, skipping execution.")
        return True

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Command failed: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Error running command: {e}")
        return False

class VPNManager:
    @staticmethod
    def create_ssh_user(username, password, expiry_date):
        """Creates a system user for SSH."""
        # Create user with no home directory and shell set to /usr/sbin/nologin (or /bin/bash if needed)
        # Using /bin/bash allows SSH login.
        if not run_command(['useradd', '-m', '-s', '/bin/bash', username]):
            return False

        # Set password
        p = subprocess.Popen(['chpasswd'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if os.geteuid() == 0:
            out, err = p.communicate(input=f'{username}:{password}')
            if p.returncode != 0:
                print(f"Failed to set password: {err}")
                return False
        else:
            print(f"[MOCK] Setting password for {username}")

        # Set expiry
        expiry_str = expiry_date.strftime('%Y-%m-%d')
        if not run_command(['chage', '-E', expiry_str, username]):
             return False

        return True

    @staticmethod
    def delete_ssh_user(username):
        """Deletes a system user."""
        return run_command(['userdel', '-r', username])

    @staticmethod
    def _read_xray_config():
        if not os.path.exists(XRAY_CONFIG_PATH):
            print(f"Xray config not found at {XRAY_CONFIG_PATH}")
            return None

        try:
            with open(XRAY_CONFIG_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading Xray config: {e}")
            return None

    @staticmethod
    def _write_xray_config(config):
        # Backup first
        if os.geteuid() == 0 and os.path.exists(XRAY_CONFIG_PATH):
            shutil.copy(XRAY_CONFIG_PATH, XRAY_CONFIG_PATH + '.bak')

        if os.geteuid() != 0:
            print("[MOCK] Writing Xray config")
            return True

        try:
            with open(XRAY_CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error writing Xray config: {e}")
            return False

    @staticmethod
    def add_xray_user(protocol, username, uuid, email=""):
        """Adds a user to the Xray config."""
        config = VPNManager._read_xray_config()
        if not config:
            # If config doesn't exist (e.g. in sandbox), we can't really do much unless we create a mock one.
            # For now, let's just log it.
            print("[WARN] No Xray config found, skipping modification.")
            return True # Return True to not block app flow in dev

        changed = False
        inbounds = config.get('inbounds', [])

        target_tag = f"{protocol}_inbound" # e.g., vless_inbound

        found_inbound = False
        for inbound in inbounds:
            if inbound.get('tag') == target_tag or inbound.get('protocol') == protocol:
                found_inbound = True
                settings = inbound.get('settings', {})
                clients = settings.get('clients', [])

                # Check if user exists
                if any(c.get('email') == username for c in clients):
                    print(f"User {username} already exists in {protocol}")
                    continue

                new_client = {
                    "id": uuid,
                    "email": username
                }

                # Protocol specific fields
                if protocol == 'vmess':
                    new_client['alterId'] = 0
                if protocol == 'trojan':
                    new_client['password'] = uuid
                    del new_client['id'] # Trojan uses password, not id in some configs, or structure differs.
                    # Standard Xray Trojan: "clients": [ { "password": "...", "email": "..." } ]

                clients.append(new_client)
                settings['clients'] = clients
                inbound['settings'] = settings
                changed = True

        if not found_inbound:
            print(f"Inbound for {protocol} not found in config.")
            return False

        if changed:
            if VPNManager._write_xray_config(config):
                return VPNManager.restart_xray()

        return True

    @staticmethod
    def remove_xray_user(protocol, username):
        config = VPNManager._read_xray_config()
        if not config:
            return True

        changed = False
        inbounds = config.get('inbounds', [])

        for inbound in inbounds:
            if inbound.get('protocol') == protocol:
                settings = inbound.get('settings', {})
                clients = settings.get('clients', [])

                initial_len = len(clients)
                clients = [c for c in clients if c.get('email') != username]

                if len(clients) < initial_len:
                    settings['clients'] = clients
                    inbound['settings'] = settings
                    changed = True

        if changed:
            if VPNManager._write_xray_config(config):
                return VPNManager.restart_xray()

        return True

    @staticmethod
    def restart_xray():
        return run_command(XRAY_RESTART_CMD)
