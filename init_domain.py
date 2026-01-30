import sys
from flask import Flask
from models import db, SystemConfig

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diana.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def init_domain(domain):
    with app.app_context():
        db.create_all()
        config = SystemConfig.query.get('domain')
        if not config:
            config = SystemConfig(key='domain', value=domain)
            db.session.add(config)
        else:
            config.value = domain
        db.session.commit()
        print(f"Domain set to: {domain}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 init_domain.py <domain>")
        sys.exit(1)
    init_domain(sys.argv[1])
