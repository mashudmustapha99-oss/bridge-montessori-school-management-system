from app import app
from models import User
from extensions import db
from werkzeug.security import generate_password_hash

with app.app_context():

    existing_user = User.query.filter_by(username="developer").first()

    if existing_user:
        print("Developer account already exists.")

    else:
        developer = User(
            username="developer",
            password_hash=generate_password_hash("Developer@2026"),
            role="developer"
        )

        db.session.add(developer)
        db.session.commit()

        print("Developer account created successfully.")