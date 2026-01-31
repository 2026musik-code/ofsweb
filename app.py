from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, VPNAccount, SystemConfig
import bcrypt
import os
import psutil
import subprocess
import uuid
import json
import base64
from datetime import datetime, timedelta
from vpn_utils import VPNManager
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'diana-vpn-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diana.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('login.html')

    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if user and bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
        if not user.is_approved:
            return jsonify({'success': False, 'message': 'Account pending approval'}), 401

        login_user(user)
        return jsonify({'success': True, 'message': 'Login successful'})

    return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
         return jsonify({'success': False, 'message': 'Missing data'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already exists'}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    # First user ever registered could be auto-approved/admin, but we handle that in init script.
    # Default: Not approved, Not admin
    new_user = User(name=name, email=email, password=hashed_password, is_approved=False, is_admin=False)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Registration successful. Please wait for admin approval.'})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', name=current_user.name, is_admin=current_user.is_admin)

# --- API Endpoints ---

@app.route('/api/admin/users')
@login_required
def list_users():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    users = User.query.all()
    user_list = []
    for u in users:
        user_list.append({
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'is_approved': u.is_approved,
            'is_admin': u.is_admin
        })
    return jsonify({'users': user_list})

@app.route('/api/admin/approve/<int:id>', methods=['POST'])
@login_required
def approve_user(id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    user = User.query.get(id)
    if user:
        user.is_approved = True
        db.session.commit()
        return jsonify({'success': True, 'message': 'User approved'})
    return jsonify({'success': False, 'message': 'User not found'}), 404

@app.route('/api/admin/reject/<int:id>', methods=['POST'])
@login_required
def reject_user(id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    user = User.query.get(id)
    if user:
        # Prevent deleting yourself
        if user.id == current_user.id:
             return jsonify({'success': False, 'message': 'Cannot delete yourself'}), 400

        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True, 'message': 'User rejected/deleted'})
    return jsonify({'success': False, 'message': 'User not found'}), 404

@app.route('/api/admin/edit_user/<int:id>', methods=['POST'])
@login_required
def edit_user(id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    user = User.query.get(id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    if name:
        user.name = name
    if email:
        # Check if email taken by other
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != id:
            return jsonify({'success': False, 'message': 'Email already taken'}), 400
        user.email = email
    if password:
        user.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    db.session.commit()
    return jsonify({'success': True, 'message': 'User updated successfully'})

@app.route('/api/stats')
@login_required
def get_stats():
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    active_accounts = VPNAccount.query.filter_by(user_id=current_user.id).count()
    return jsonify({'cpu': cpu, 'ram': ram, 'active_accounts': active_accounts})

@app.route('/api/monitor/online')
@login_required
def get_online_users():
    # Only Admin should probably see full list, but let's allow all for now or restrict?
    # User requirement: "Fitur aktif yg sedang online pakai VPN kita"

    online_users = []

    # 1. Check SSH (Standard)
    # Using 'w' command or 'who' or reading /var/log/auth.log
    # Simplest reliable way for active SSH connections:
    try:
        # ps -ef | grep 'sshd: ' | grep -v 'grep' | grep -v 'priv'
        # Format usually: sshd: username@pts/0
        cmd = "ps -eo user,cmd | grep 'sshd: ' | grep '@' | grep -v grep"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) > 0:
                    # User is the first column in 'ps -eo user...'
                    # But the cmd part 'sshd: user@pts/0' contains the actual connected user if it's a session.
                    # Let's parse 'sshd: user@' part.
                    # Example: root 1234 ... sshd: myuser@pts/0
                    # The 'ps -eo user,cmd' output: "root sshd: myuser@pts/0"

                    # Better command: "who"
                    pass
    except:
        pass

    try:
        # Use 'who' command for SSH
        res = subprocess.run(['who'], capture_output=True, text=True)
        if res.stdout:
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 1:
                    online_users.append({
                        'username': parts[0],
                        'protocol': 'SSH (System)',
                        'ip': parts[-1].strip('()'), # usually IP in brackets
                        'duration': 'Active'
                    })
    except Exception as e:
        print(f"Error checking SSH online: {e}")

    # 2. Check Dropbear
    # Dropbear logs to syslog/auth.log or we can check process list.
    # ps -ef | grep dropbear
    # Dropbear forks per connection.
    try:
        # ps -ef | grep dropbear | grep -v grep
        # Look for child processes.
        # This is harder to map to username without log parsing.
        # For MVP, we might skip Dropbear user mapping unless we parse logs.
        pass
    except:
        pass

    # 3. Check Xray (Optional / Advanced)
    # Requires 'stats' query.
    # For now, return what we have (SSH System Users).

    return jsonify({'online': online_users})

@app.route('/api/domain', methods=['GET', 'POST'])
@login_required
def manage_domain():
    if request.method == 'POST':
        data = request.json
        new_domain = data.get('domain')
        if not new_domain:
            return jsonify({'success': False, 'message': 'Domain cannot be empty'}), 400

        config = SystemConfig.query.get('domain')
        if not config:
            config = SystemConfig(key='domain', value=new_domain)
            db.session.add(config)
        else:
            config.value = new_domain
        db.session.commit()
        return jsonify({'success': True, 'message': 'Domain updated successfully'})

@app.route('/api/system/autoreboot', methods=['POST'])
@login_required
def auto_reboot():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.json
    enable = data.get('enable')
    time_str = data.get('time') # HH:MM

    # Simple Crontab implementation via subprocess
    # Note: Requires root usually. We can write to /etc/cron.d/autoreboot or use `crontab` command.
    # Safe way: echo "0 0 * * * /sbin/reboot" | crontab -

    try:
        # Clear existing reboot job
        # 1. Read current crontab
        # 2. Filter out our reboot job
        # 3. Add new if enabled

        # Simplified: We overwrite a dedicated cron file /etc/cron.d/diana-reboot
        # Format: m h dom mon dow user command

        cron_path = '/etc/cron.d/diana-reboot'

        if not enable:
            if os.path.exists(cron_path):
                os.remove(cron_path)
            return jsonify({'success': True, 'message': 'Auto reboot disabled'})

        if not time_str:
             return jsonify({'success': False, 'message': 'Time required'}), 400

        # Validate time format to prevent RCE
        import re
        if not re.match(r'^\d{2}:\d{2}$', time_str):
             return jsonify({'success': False, 'message': 'Invalid time format'}), 400

        hour, minute = time_str.split(':')

        # Ensure hour and minute are integers within range
        h, m = int(hour), int(minute)
        if not (0 <= h <= 23 and 0 <= m <= 59):
             return jsonify({'success': False, 'message': 'Invalid time range'}), 400

        cron_content = f"{m} {h} * * * root /sbin/reboot\n"

        with open(cron_path, 'w') as f:
            f.write(cron_content)

        return jsonify({'success': True, 'message': f'Auto reboot set to {time_str}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/domain', methods=['GET', 'POST'])
@login_required
def manage_domain():
    if request.method == 'POST':
        data = request.json
        new_domain = data.get('domain')
        if not new_domain:
            return jsonify({'success': False, 'message': 'Domain cannot be empty'}), 400

        config = SystemConfig.query.get('domain')
        if not config:
            config = SystemConfig(key='domain', value=new_domain)
            db.session.add(config)
        else:
            config.value = new_domain
        db.session.commit()
        return jsonify({'success': True, 'message': 'Domain updated successfully'})

    config = SystemConfig.query.get('domain')
    domain = config.value if config else 'localhost'
    return jsonify({'domain': domain})

@app.route('/update', methods=['POST'])
@login_required
def update_system():
    try:
        # Ensure remote is correct
        repo_url = "https://github.com/2026musik-code/ofsweb"
        subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url], check=False)

        # Pull latest changes from git
        result = subprocess.run(['git', 'pull', 'origin', 'main'], capture_output=True, text=True)
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'System updated successfully. Restarting service recommended.'})
        else:
            return jsonify({'success': False, 'message': f'Update failed: {result.stderr}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/account/create', methods=['POST'])
@login_required
def create_account():
    data = request.json
    acc_type = data.get('type')
    username = data.get('username')
    password = data.get('password')
    duration_input = data.get('duration')

    if not username:
        return jsonify({'success': False, 'message': 'Username required'}), 400

    is_trial = False
    if duration_input == 'trial':
        is_trial = True
        duration_days = 1 # 24 hours
        # Force trial username format if desired, or let user pick.
        # Let's enforce a trial prefix to be safe/identifiable
        if not username.startswith("trial_"):
             username = f"trial_{username}"
    else:
        try:
            duration_days = int(duration_input)
        except:
            duration_days = 30

    # Check if username exists for this type
    if VPNAccount.query.filter_by(username=username, account_type=acc_type).first():
         return jsonify({'success': False, 'message': 'Username already exists'}), 400

    expiry_date = datetime.utcnow() + timedelta(days=duration_days)

    new_acc = VPNAccount(
        user_id=current_user.id,
        account_type=acc_type,
        username=username,
        expiry=expiry_date
    )

    # Logic for different types
    success = False

    # Get system domain for link generation logic later if needed
    sys_config = SystemConfig.query.get('domain')
    system_domain = sys_config.value if sys_config else 'localhost'
    new_acc.domain = system_domain

    if acc_type == 'ssh':
        new_acc.password = password
        new_acc.port = 22
        if VPNManager.create_ssh_user(username, password, expiry_date):
            success = True

    elif acc_type in ['vmess', 'vless', 'trojan']:
        new_acc.uuid = str(uuid.uuid4())
        new_acc.port = 443
        new_acc.protocol = 'ws'

        # Add to Xray (Dual Mode: XTLS + WS)
        # For VLESS, we might want to add to both 'vless_xtls' and 'vless_ws' inbounds.
        # VPNManager currently adds to all inbounds matching protocol or tag.
        # Since our tags are vless_xtls and vless_ws, and protocol is vless, it should add to both!
        if VPNManager.add_xray_user(acc_type, username, new_acc.uuid):
            success = True

    elif acc_type == 'ss':
         # Shadowsocks via Xray
         new_acc.password = password if password else str(uuid.uuid4())[:16]
         new_acc.port = 443
         if VPNManager.add_xray_user('shadowsocks', username, new_acc.password):
             success = True

    if success:
        db.session.add(new_acc)
        db.session.commit()
        return jsonify({'success': True, 'message': f'{acc_type.upper()} Account created'})
    else:
        return jsonify({'success': False, 'message': 'Failed to create system account'}), 500

@app.route('/api/account/list')
@login_required
def list_accounts():
    acc_type = request.args.get('type')
    accounts = VPNAccount.query.filter_by(user_id=current_user.id, account_type=acc_type).all()

    # Get Current Domain
    sys_config = SystemConfig.query.get('domain')
    system_domain = sys_config.value if sys_config else 'localhost'

    acc_list = []
    for acc in accounts:
        details = ""
        links = {}

        # Determine domain for this account
        domain = acc.domain if acc.domain and acc.domain != 'example.com' else system_domain

        if acc.account_type in ['ssh', 'ss']:
             details = f"Pass: {acc.password}"
        else:
            # --- Link Generation ---
            if acc.account_type == 'vless':
                # WS TLS (Port 443)
                links['tls'] = f"vless://{acc.uuid}@{domain}:443?security=tls&encryption=none&type=ws&host={domain}&sni={domain}&path=/vless#{acc.username}"
                # WS Non-TLS (Port 80)
                links['nontls'] = f"vless://{acc.uuid}@{domain}:80?security=none&encryption=none&type=ws&host={domain}&path=/vless#{acc.username}"

                details = f"UUID: {acc.uuid}"

                vless_details = f"""
================================
       VLESS ACCOUNT
================================
Domain    : {domain}
UUID      : {acc.uuid}
================================
LINK WS TLS (CDN/Cloudflare):
{links['tls']}

LINK WS NON-TLS:
{links['nontls']}
================================
""".strip()

            elif acc.account_type == 'vmess':
                # TLS
                vmess_tls = {
                    "v": "2", "ps": acc.username, "add": domain, "port": "443", "id": acc.uuid,
                    "aid": "0", "net": "ws", "type": "none", "host": domain, "path": "/vmess", "tls": "tls"
                }
                # Non-TLS
                vmess_nontls = {
                    "v": "2", "ps": acc.username, "add": domain, "port": "80", "id": acc.uuid,
                    "aid": "0", "net": "ws", "type": "none", "host": domain, "path": "/vmess", "tls": "none"
                }
                links['tls'] = "vmess://" + base64.b64encode(json.dumps(vmess_tls).encode('utf-8')).decode('utf-8')
                links['nontls'] = "vmess://" + base64.b64encode(json.dumps(vmess_nontls).encode('utf-8')).decode('utf-8')
                details = f"UUID: {acc.uuid}"

            elif acc.account_type == 'trojan':
                links['tls'] = f"trojan://{acc.uuid}@{domain}:443?security=tls&headerType=none&type=ws&host={domain}&sni={domain}&path=/trojan#{acc.username}"
                # Trojan typically implies TLS, but for consistency in structure:
                links['nontls'] = f"trojan://{acc.uuid}@{domain}:80?security=none&headerType=none&type=ws&host={domain}&path=/trojan#{acc.username}"
                details = f"Password/UUID: {acc.uuid}"

            elif acc.account_type == 'ss':
                # SS usually simpler, but assuming WS path via plugin param or just raw info
                # Xray SS with WS
                # ss://method:password@domain:443?plugin=v2ray-plugin%3Bmode%3Dwebsocket%3Bhost%3Ddomain%3Bpath%3D%2Fss%3Btls
                method = "aes-256-gcm"
                user_info = base64.b64encode(f"{method}:{acc.password}".encode()).decode().strip()
                plugin_tls = f"v2ray-plugin;mode=websocket;host={domain};path=/ss;tls"
                plugin_nontls = f"v2ray-plugin;mode=websocket;host={domain};path=/ss"

                links['tls'] = f"ss://{user_info}@{domain}:443?plugin={plugin_tls}#{acc.username}"
                links['nontls'] = f"ss://{user_info}@{domain}:80?plugin={plugin_nontls}#{acc.username}"
                details = f"Pass: {acc.password}"

        # Quota formatting
        quota_str = "0 B"
        if acc.quota_used:
            gb = acc.quota_used / (1024 * 1024 * 1024)
            if gb >= 1:
                quota_str = f"{gb:.2f} GB"
            else:
                mb = acc.quota_used / (1024 * 1024)
                quota_str = f"{mb:.2f} MB"

        ssh_details = ""
        if acc.account_type == 'ssh':
             ssh_details = f"""
================================
       SSH ACCOUNT DETAILS
================================
Domain         : {domain}
Username       : {acc.username}
Password       : {acc.password}
Created        : {acc.created_at.strftime('%Y-%m-%d')}
Expired        : {acc.expiry.strftime('%Y-%m-%d') if acc.expiry else 'N/A'}
================================
Port OpenSSH   : 22
Port Dropbear  : 109, 143
Port SSL/TLS   : 443
Port WS HTTP   : 80
Port WS HTTPS  : 443
================================
Payload WS (No TLS):
GET / HTTP/1.1[crlf]Host: {domain}[crlf]Upgrade: websocket[crlf][crlf]

Payload WS (TLS):
GET / HTTP/1.1[crlf]Host: {domain}[crlf]Upgrade: websocket[crlf][crlf]
================================
""".strip()

        # Helper for other protocols to have details view if needed (like VLESS)
        full_details = ssh_details
        if acc.account_type == 'vless' and 'vless_details' in locals():
            full_details = vless_details

        acc_list.append({
            'id': acc.id,
            'username': acc.username,
            'details': details,
            'links': links,
            'ssh_details': full_details,
            'quota': quota_str,
            'expiry': acc.expiry.strftime('%Y-%m-%d') if acc.expiry else 'N/A'
        })

    return jsonify({'accounts': acc_list})

# Background Task for Xray Stats
def query_xray_stats():
    # Simple loop to query Xray stats via API command line tool or direct gRPC
    # Since we don't have python-xray-proto generated, we use `xray api statsquery` if binary exists.
    # Or simpler: Rely on Xray logging if API is hard to reach without libs.
    # For MVP: We skip complex gRPC implementation here and assume future expansion.
    # But user asked for "Traffic Monitor".
    # Let's try to mock or use basic file tracking if possible.
    # Real implementation needs `grpcio` and `xray_api_pb2`.
    # Let's mock the update for now or leave it for "Real Implementation" phase if libraries missing.
    # BUT, we can use `subprocess` to call `xray api stats` if `xray` binary supports it.
    pass

# Start background thread
# threading.Thread(target=query_xray_stats, daemon=True).start()

@app.route('/api/account/delete/<int:id>', methods=['DELETE'])
@login_required
def delete_account(id):
    acc = VPNAccount.query.get(id)
    if acc and acc.user_id == current_user.id:
        # Remove system account
        if acc.account_type == 'ssh':
            VPNManager.delete_ssh_user(acc.username)
        elif acc.account_type in ['vmess', 'vless', 'trojan', 'ss']:
            VPNManager.remove_xray_user(acc.account_type if acc.account_type != 'ss' else 'shadowsocks', acc.username)

        db.session.delete(acc)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Account deleted'})
    return jsonify({'success': False, 'message': 'Account not found or unauthorized'}), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Debug mode should be False in production
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
