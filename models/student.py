from extensions import db


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.String(20),
        unique=True,
        nullable=False,
        index=True
    )

    first_name = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    last_name = db.Column(
        db.String(50),
        nullable=False,
        index=True
    )

    middle_name = db.Column(
        db.String(50),
        nullable=True
    )

    gender = db.Column(
        db.String(10),
        nullable=False
    )

    date_of_birth = db.Column(
        db.String(20),
        nullable=False
    )

    parent_contact = db.Column(
        db.String(20),
        nullable=False
    )

    emergency_contact = db.Column(
        db.String(20),
        nullable=False
    )

    address = db.Column(
        db.String(200),
        nullable=False
    )

    student_class = db.Column(
        db.String(50),
        nullable=False
    )

    is_deleted = db.Column(
        db.Boolean,
        default=False
    )