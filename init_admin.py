import bcrypt
from flask import Flask
from models import db, User
import sys

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diana.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def init_admin():
    with app.app_context():
        db.create_all()

        # Check if any user exists
        if User.query.first():
            print("Users already exist. Skipping admin creation.")
            return

        print("Creating default admin account...")
        password = "admin123"
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        admin = User(
            name="Administrator",
            email="admin@diana.com",
            password=hashed_password,
            is_approved=True,
            is_admin=True
        )

        db.session.add(admin)
        db.session.commit()

        print("\n" + "="*40)
        print("DEFAULT ADMIN CREATED")
        print("Email: admin@diana.com")
        print("Password: admin123")
        print("="*40 + "\n")

if __name__ == "__main__":
    init_admin()
