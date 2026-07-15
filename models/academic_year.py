from extensions import db


class AcademicYear(db.Model):
    __tablename__ = "academic_years"

    id = db.Column(db.Integer, primary_key=True)

    year = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        default=False
    )