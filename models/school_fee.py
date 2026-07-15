from extensions import db


class SchoolFee(db.Model):
    __tablename__ = "school_fees"

    id = db.Column(db.Integer, primary_key=True)

    student_class = db.Column(
        db.String(50),
        nullable=False
    )

    academic_year = db.Column(
        db.String(20),
        nullable=False
    )

    term = db.Column(
        db.String(50),
        nullable=False
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )