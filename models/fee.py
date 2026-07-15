from extensions import db
from datetime import datetime


class Fee(db.Model):
    __tablename__ = "fees"

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.Integer,
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

    # NEW
    school_fee = db.Column(
        db.Float,
        nullable=False
    )

    # NEW
    previous_balance = db.Column(
        db.Float,
        default=0
    )

    total_fees = db.Column(
        db.Float,
        nullable=False
    )

    amount_paid = db.Column(
        db.Float,
        nullable=False
    )

    balance = db.Column(
        db.Float,
        nullable=False
    )

    receipt_number = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    payment_date = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )