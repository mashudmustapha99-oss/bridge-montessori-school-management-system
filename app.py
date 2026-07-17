from flask import Flask
from flask import redirect, url_for
from config import Config
from extensions import db
from models import User, Student, Fee, SchoolFee, AcademicYear
from routes.auth import auth
from werkzeug.security import generate_password_hash

app = Flask(__name__)

app.config.from_object(Config)

db.init_app(app)

app.register_blueprint(auth)


@app.route("/")
def home():
    return redirect(url_for("auth.login"))


with app.app_context():

    db.create_all()

    # Create Academic Year if it doesn't exist
    academic_year = AcademicYear.query.filter_by(is_active=True).first()

    if not academic_year:

        academic_year = AcademicYear(
            year="2026/2027",
            is_active=True
        )

        db.session.add(academic_year)
        db.session.commit()

        print("Academic Year created successfully.")

    # Create Admin if it doesn't exist
    admin = User.query.filter_by(username="admin").first()

    if not admin:

        admin = User(
            username="admin",
            password_hash=generate_password_hash("admin123"),
            role="admin"
        )

        db.session.add(admin)
        db.session.commit()

        print("Admin created successfully")


print(app.url_map)

if __name__ == "__main__":
    app.run(debug=False)
