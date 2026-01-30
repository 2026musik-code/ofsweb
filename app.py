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

@app.route('/api/stats')
@login_required
def get_stats():
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    active_accounts = VPNAccount.query.filter_by(user_id=current_user.id).count()
    return jsonify({'cpu': cpu, 'ram': ram, 'active_accounts': active_accounts})

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
        # Pull latest changes from git
        result = subprocess.run(['git', 'pull'], capture_output=True, text=True)
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
    duration = data.get('duration')

    if not username:
        return jsonify({'success': False, 'message': 'Username required'}), 400

    if not duration:
        duration = 30
    else:
        try:
            duration = int(duration)
        except:
            duration = 30

    # Check if username exists for this type
    if VPNAccount.query.filter_by(username=username, account_type=acc_type).first():
         return jsonify({'success': False, 'message': 'Username already exists'}), 400

    expiry_date = datetime.utcnow() + timedelta(days=duration)

    new_acc = VPNAccount(
        user_id=current_user.id,
        account_type=acc_type,
        username=username,
        expiry=expiry_date
    )

    # Mock Logic for different types
    if acc_type in ['ssh', 'ss']:
        new_acc.password = password
        new_acc.port = 22 if acc_type == 'ssh' else 8388
    elif acc_type in ['vmess', 'vless', 'trojan']:
        new_acc.uuid = str(uuid.uuid4())
        new_acc.port = 443
        new_acc.protocol = 'ws' # default to ws tls as requested
        # new_acc.domain = 'example.com'

    db.session.add(new_acc)
    db.session.commit()

    return jsonify({'success': True, 'message': f'{acc_type.upper()} Account created'})

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

        if acc.account_type in ['ssh', 'ss']:
            details = f"Pass: {acc.password}, Port: {acc.port}"
        else:
            # Use stored domain if account domain is default/placeholder, otherwise use account specific if implemented
            domain = system_domain

            # --- Link Generation ---
            if acc.account_type == 'vless':
                # TLS
                links['tls'] = f"vless://{acc.uuid}@{domain}:443?security=tls&encryption=none&headerType=none&type=ws&host={domain}&sni={domain}#{acc.username}"
                # Non-TLS
                links['nontls'] = f"vless://{acc.uuid}@{domain}:80?security=none&encryption=none&headerType=none&type=ws&host={domain}#{acc.username}"
                details = f"UUID: {acc.uuid}"

            elif acc.account_type == 'vmess':
                # TLS
                vmess_tls = {
                    "v": "2", "ps": acc.username, "add": domain, "port": "443", "id": acc.uuid,
                    "aid": "0", "net": "ws", "type": "none", "host": domain, "path": "/", "tls": "tls"
                }
                # Non-TLS
                vmess_nontls = {
                    "v": "2", "ps": acc.username, "add": domain, "port": "80", "id": acc.uuid,
                    "aid": "0", "net": "ws", "type": "none", "host": domain, "path": "/", "tls": "none"
                }
                links['tls'] = "vmess://" + base64.b64encode(json.dumps(vmess_tls).encode('utf-8')).decode('utf-8')
                links['nontls'] = "vmess://" + base64.b64encode(json.dumps(vmess_nontls).encode('utf-8')).decode('utf-8')
                details = f"UUID: {acc.uuid}"

            elif acc.account_type == 'trojan':
                links['tls'] = f"trojan://{acc.uuid}@{domain}:443?security=tls&headerType=none&type=ws&host={domain}&sni={domain}#{acc.username}"
                # Trojan typically implies TLS, but for consistency in structure:
                links['nontls'] = f"trojan://{acc.uuid}@{domain}:80?security=none&headerType=none&type=ws&host={domain}#{acc.username}"
                details = f"Password/UUID: {acc.uuid}"

        acc_list.append({
            'id': acc.id,
            'username': acc.username,
            'details': details,
            'links': links,
            'expiry': acc.expiry.strftime('%Y-%m-%d') if acc.expiry else 'N/A'
        })

    return jsonify({'accounts': acc_list})

@app.route('/api/account/delete/<int:id>', methods=['DELETE'])
@login_required
def delete_account(id):
    acc = VPNAccount.query.get(id)
    if acc and acc.user_id == current_user.id:
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
