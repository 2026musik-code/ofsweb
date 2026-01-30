from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

class VPNAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_type = db.Column(db.String(20), nullable=False) # ssh, vmess, vless, trojan, ss
    username = db.Column(db.String(50))
    password = db.Column(db.String(100)) # for SSH/SS
    uuid = db.Column(db.String(100)) # for vmess/vless/trojan
    domain = db.Column(db.String(100))
    port = db.Column(db.Integer)
    protocol = db.Column(db.String(10)) # ws, tls, tcp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expiry = db.Column(db.DateTime)

class SystemConfig(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200))
