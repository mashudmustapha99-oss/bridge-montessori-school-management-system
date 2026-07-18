from flask import Blueprint, render_template, request, redirect, url_for, send_file, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from models import User, Student, Fee, SchoolFee
from extensions import db
from functools import wraps
from openpyxl import Workbook
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from models import AcademicYear
import os
import shutil
from constants import CLASSES
import io



def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

auth = Blueprint("auth", __name__)


# ---------------- LOGIN ----------------

@auth.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if not user:
            flash(
                "Login unsuccessful. Please check your username and password.",
                "error"
            )
            return redirect(url_for("auth.login"))

        # Check if account is locked
        if user.locked_until_utc and datetime.utcnow() < user.locked_until_utc:
            flash(
                "Your account has been locked for security reasons after multiple unsuccessful login attempts. Please contact the system developer or administrator.",
                "error"
            )
            return redirect(url_for("auth.login"))

        # Correct password
        if check_password_hash(user.password_hash, password):
            user.failed_attempts = 0
            user.locked_until_utc = None
            db.session.commit()

            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role

            return redirect(url_for("auth.dashboard"))

        # Wrong password
        user.failed_attempts += 1
        attempts_left = 3 - user.failed_attempts

        if user.failed_attempts >= 3:
            user.locked_until_utc = datetime.utcnow() + timedelta(days=365)
            db.session.commit()

            flash(
                "Your account has been locked for security reasons after multiple unsuccessful login attempts. Please contact the system developer or administrator.",
                "error"
            )
            return redirect(url_for("auth.login"))

        db.session.commit()

        if attempts_left == 2:
            flash(
                "Login unsuccessful. Please check your password and try again. You have 2 attempts remaining.",
                "error"
            )

        elif attempts_left == 1:
            flash(
                "Login unsuccessful again. Please verify your login details carefully. You have 1 attempt remaining.",
                "error"
            )

        return redirect(url_for("auth.login"))

    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@auth.route("/dashboard")
@login_required
def dashboard():

    active_students = Student.query.filter_by(is_deleted=False).all()
    active_student_ids = [student.id for student in active_students]

    total_students = len(active_students)

    fees = Fee.query.filter(Fee.student_id.in_(active_student_ids)).all()

    total_fees_collected = sum(fee.amount_paid for fee in fees)
    total_outstanding_balance = sum(fee.balance for fee in fees)

    debtors_count = len(
        set(fee.student_id for fee in fees if fee.balance > 0)
    )

    fully_paid_count = len(
        set(fee.student_id for fee in fees if fee.balance == 0)
    )

    return render_template(
        "dashboard.html",
        total_students=total_students,
        total_fees_collected=total_fees_collected,
        total_outstanding_balance=total_outstanding_balance,
        debtors_count=debtors_count,
        fully_paid_count=fully_paid_count
    )



# ---------------- SET SCHOOL FEE ----------------

@auth.route("/set-school-fee", methods=["GET", "POST"])
@login_required
def set_school_fee():

    if request.method == "POST":

        # Get active academic year
        active_year = AcademicYear.query.filter_by(is_active=True).first()

        if not active_year:
            flash("No active academic year found.", "error")
            return redirect(url_for("auth.set_school_fee"))

        student_class = request.form.get("student_class")
        term = request.form.get("term")
        amount = request.form.get("amount")

        # Validate empty fields
        if not student_class or not term or not amount:
            flash("All fields are required.", "error")
            return redirect(url_for("auth.set_school_fee"))

        # Validate amount
        try:
            amount = float(amount)
        except ValueError:
            flash("Amount must be a valid number.", "error")
            return redirect(url_for("auth.set_school_fee"))

        if amount <= 0:
            flash("Amount must be greater than 0.", "error")
            return redirect(url_for("auth.set_school_fee"))

        # Check if fee already exists
        existing_fee = SchoolFee.query.filter_by(
            student_class=student_class,
            academic_year=active_year.year,
            term=term
        ).first()

        if existing_fee:
            flash("School fee for this class, term and academic year already exists.", "error")
            return redirect(url_for("auth.set_school_fee"))

        # Save fee
        fee = SchoolFee(
            student_class=student_class,
            academic_year=active_year.year,
            term=term,
            amount=amount
        )

        db.session.add(fee)
        db.session.commit()

        flash("School fee saved successfully!", "success")
        return redirect(url_for("auth.set_school_fee"))

    # Display all fee records

    fees = SchoolFee.query.order_by(
    SchoolFee.academic_year.desc(),
    SchoolFee.student_class,
    SchoolFee.term
).all()

    active_year = AcademicYear.query.filter_by(is_active=True).first()

    return render_template(
    "set_school_fee.html",
    fees=fees,
    classes=CLASSES,
    active_year=active_year
)
   

#---------------------SCHOOL FEE RECORDS--------------------


@auth.route("/school-fee-records")
@login_required
def school_fee_records():

    fees = SchoolFee.query.order_by(
        SchoolFee.student_class.asc(),
        SchoolFee.term.asc()
    ).all()

    return render_template(
        "school_fee_records.html",
        fees=fees,
        classes=CLASSES
    )

#-------------------------EDIT SCHOOL FEE--------------------------


@auth.route("/edit-school-fee/<int:id>", methods=["GET", "POST"])
@login_required
def edit_school_fee(id):

    fee = SchoolFee.query.get_or_404(id)

    if request.method == "POST":

        new_amount = float(request.form.get("amount"))

        # Update school fee
        fee.amount = new_amount

        # Find all students in this class
        students = Student.query.filter_by(
            student_class=fee.student_class
        ).all()

        for student in students:

            # Find the student's fee record for this term
            payment = Fee.query.filter_by(
                student_id=student.id,
                term=fee.term
            ).first()

            if payment:
                payment.total_fees = new_amount
                payment.balance = new_amount - payment.amount_paid

        db.session.commit()

        flash(
            "School fee updated successfully. All affected student balances have been recalculated.",
            "success"
        )

        return redirect(url_for("auth.school_fee_records"))

    return render_template(
        "edit_school_fee.html",
        fee=fee,
        classes=CLASSES
    )


# ---------------- ADD STUDENT ----------------

@auth.route("/add-student", methods=["GET", "POST"])
@login_required
def add_student():

    if request.method == "POST":

        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        middle_name = request.form.get("middle_name")
        gender = request.form.get("gender")
        date_of_birth = request.form.get("date_of_birth")
        parent_contact = request.form.get("parent_contact")
        emergency_contact = request.form.get("emergency_contact")
        address = request.form.get("address")
        student_class = request.form.get("student_class")

        if not all([
            first_name,
            last_name,
            gender,
            date_of_birth,
            parent_contact,
            emergency_contact,
            address,
            student_class
        ]):
            flash("All required fields must be filled.", "error")
            return redirect(url_for("auth.add_student"))

        if not parent_contact.isdigit():
            flash("Parent contact must contain numbers only.", "error")
            return redirect(url_for("auth.add_student"))

        if not emergency_contact.isdigit():
            flash("Emergency contact must contain numbers only.", "error")
            return redirect(url_for("auth.add_student"))

        student_count = Student.query.count() + 1
        student_id = f"SMS2026{student_count:03d}"

        student = Student(
            student_id=student_id,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            gender=gender,
            date_of_birth=date_of_birth,
            parent_contact=parent_contact,
            emergency_contact=emergency_contact,
            address=address,
            student_class=student_class
        )

        db.session.add(student)
        db.session.commit()

        flash("Student saved successfully!", "success")
        return redirect(url_for("auth.add_student"))

    return render_template(
    "add_student.html",
    classes=CLASSES
)
    

   

# ---------------- VIEW STUDENTS ----------------
@auth.route("/students")
@login_required
def students():

    search = request.args.get("search", "")
    selected_class = request.args.get("student_class", "")

    # Only active students
    query = Student.query.filter_by(is_deleted=False)

    # Search filter
    if search:
        query = query.filter(
            (Student.student_id.contains(search)) |
            (Student.first_name.contains(search)) |
            (Student.last_name.contains(search))
        )

    # Class filter
    if selected_class:
        query = query.filter(
            Student.student_class == selected_class
        )

    students = query.all()

    fees = Fee.query.all()

    fee_map = {}
    for fee in fees:
        fee_map[fee.student_id] = fee

    return render_template(
        "students.html",
        students=students,
        fee_map=fee_map,
        search=search,
        selected_class=selected_class
    )
# ---------------- STUDENT DETAILS ----------------
@auth.route("/student/<int:id>")
@login_required
def student_details(id):

    student = Student.query.get_or_404(id)

    fee = Fee.query.filter_by(
        student_id=id
    ).order_by(Fee.id.desc()).first()

    payment_history = Fee.query.filter_by(
        student_id=id
    ).order_by(Fee.id.desc()).all()

    return render_template(
        "student_details.html",
        student=student,
        fee=fee,
        payment_history=payment_history
    )



# ---------------- EDIT STUDENT ----------------
@auth.route("/edit-student/<int:id>", methods=["GET", "POST"])
@login_required
def edit_student(id):

    student = Student.query.get_or_404(id)

    if request.method == "POST":

        student.first_name = request.form.get("first_name")
        student.last_name = request.form.get("last_name")
        student.middle_name = request.form.get("middle_name")
        student.gender = request.form.get("gender")
        student.date_of_birth = request.form.get("date_of_birth")
        student.parent_contact = request.form.get("parent_contact")
        student.emergency_contact = request.form.get("emergency_contact")
        student.address = request.form.get("address")
        student.student_class = request.form.get("student_class")

        db.session.commit()

        flash("Student details updated successfully.", "success")

        return redirect(url_for("auth.students"))

    return render_template(
    "edit_student.html",
    student=student,
    classes=CLASSES
)

# ---------------- ADD FEE (SMART SYSTEM) ----------------
@auth.route("/add-fee", methods=["GET", "POST"])
@login_required
def add_fee():

    if request.method == "POST":

        student_code = request.form.get("student_id").strip()
        term = request.form.get("term")
        amount_paid = request.form.get("amount_paid")

        # Active Academic Year
        active_year = AcademicYear.query.filter_by(is_active=True).first()

        if not active_year:
            flash("No active academic year found.", "error")
            return redirect(url_for("auth.add_fee"))

        # Validate empty fields
        if not student_code or not term or not amount_paid:
            flash("All fields are required.", "error")
            return redirect(url_for("auth.add_fee"))

        try:
            payment = float(amount_paid)
        except ValueError:
            flash("Invalid payment amount.", "error")
            return redirect(url_for("auth.add_fee"))

        if payment <= 0:
            flash("Payment must be greater than 0.", "error")
            return redirect(url_for("auth.add_fee"))

        student = Student.query.filter_by(student_id=student_code).first()

        if not student:
            flash("Student not found.", "error")
            return redirect(url_for("auth.add_fee"))

        # Get school fee for ACTIVE academic year
        school_fee = SchoolFee.query.filter_by(
            student_class=student.student_class,
            academic_year=active_year.year,
            term=term
        ).first()

        if not school_fee:
            flash(
                f"School fee has not been set for {student.student_class}, {term}, {active_year.year}.",
                "error"
            )
            return redirect(url_for("auth.add_fee"))

        # ==========================================
        # Existing payment
        # ==========================================

        existing_fee = Fee.query.filter_by(
            student_id=student.id,
            term=term,
            academic_year=active_year.year
        ).first()

        if existing_fee:

            outstanding = existing_fee.balance

            if payment > outstanding:
                flash(
                    f"Payment cannot exceed the outstanding balance of GH₵ {outstanding:.2f}.",
                    "error"
                )
                return redirect(url_for("auth.add_fee"))

            existing_fee.amount_paid += payment
            existing_fee.balance = existing_fee.total_fees - existing_fee.amount_paid
            existing_fee.payment_date = datetime.utcnow()

            db.session.commit()

            flash("Additional payment added successfully.", "success")

            return redirect(
                url_for(
                    "auth.receipt",
                    fee_id=existing_fee.id
                )
            )

        # ==========================================
        # Previous Academic Year's Outstanding Balance
        # ==========================================

        previous_balance = 0

        previous_fee = Fee.query.filter(
            Fee.student_id == student.id,
            Fee.academic_year != active_year.year
        ).order_by(Fee.id.desc()).first()

        if previous_fee:
            previous_balance = previous_fee.balance

        # Current School Fee
        school_fee_amount = school_fee.amount

        # Total Amount Payable
        total_fees = school_fee_amount + previous_balance

        # NEW: Prevent overpayment
        if payment > total_fees:
            flash(
                f"Payment cannot exceed the total fees of GH₵ {total_fees:.2f}.",
                "error"
            )
            return redirect(url_for("auth.add_fee"))

        # Remaining Balance
        balance = total_fees - payment

        current_year = datetime.now().year

        last_receipt = Fee.query.order_by(Fee.id.desc()).first()

        if last_receipt:
            last_number = int(last_receipt.receipt_number.split("-")[-1])
            next_number = last_number + 1
        else:
            next_number = 1

        receipt_number = f"BMS-{current_year}-{next_number:06d}"

        fee = Fee(
            student_id=student.id,
            academic_year=active_year.year,
            term=term,
            school_fee=school_fee_amount,
            previous_balance=previous_balance,
            total_fees=total_fees,
            amount_paid=payment,
            balance=balance,
            receipt_number=receipt_number,
            payment_date=datetime.utcnow()
        )

        db.session.add(fee)
        db.session.commit()

        flash("Fee payment saved successfully.", "success")

        return redirect(
            url_for(
                "auth.receipt",
                fee_id=fee.id
            )
        )

    return render_template("add_fee.html")


     

# ---------------- VIEW FEES ----------------
@auth.route("/fees")
@login_required
def fees():

    search = request.args.get("search", "")
    term = request.args.get("term", "")

    fees = Fee.query.all()
    students = Student.query.all()

    student_map = {student.id: student for student in students}

    filtered_fees = []

    for fee in fees:

        student = student_map.get(fee.student_id)

        if not student:
            continue

        if search:
            search_lower = search.lower()
            if not (
                search_lower in student.student_id.lower()
                or search_lower in student.first_name.lower()
                or search_lower in student.last_name.lower()
            ):
                continue

        if term and fee.term != term:
            continue

        filtered_fees.append(fee)

    return render_template(
        "fees.html",
        fees=filtered_fees,
        student_map=student_map,
        search=search,
        term=term
    )



#---------------------------RECEIPT-------------------------


@auth.route("/receipt/<int:fee_id>")
@login_required
def receipt(fee_id):

    fee = Fee.query.get_or_404(fee_id)

    student = Student.query.get_or_404(fee.student_id)

    active_year = AcademicYear.query.filter_by(
        year=fee.academic_year
    ).first()

    return render_template(
        "receipt.html",
        fee=fee,
        student=student,
        active_year=active_year,
        classes=CLASSES
    )

#-----------------------------PROMOTE ALL------------------------


@auth.route("/promote-all")
@login_required
def promote_all():

    class_map = {
        "Creche": "Nursery 1",
        "Nursery 1": "Nursery 2",
        "Nursery 2": "KG 1",
        "KG 1": "KG 2",
        "KG 2": "Primary 1",
        "Primary 1": "Primary 2",
        "Primary 2": "Primary 3",
        "Primary 3": "Primary 4",
        "Primary 4": "Primary 5",
        "Primary 5": "Primary 6",
        "Primary 6": "JHS 1",
        "JHS 1": "JHS 2",
        "JHS 2": "JHS 3",
        "JHS 3": "Graduated"
    }

    # Promote students
    students = Student.query.filter_by(is_deleted=False).all()

    for student in students:

        if student.student_class in class_map:
            student.student_class = class_map[student.student_class]

    # Update Academic Year
    active_year = AcademicYear.query.filter_by(is_active=True).first()

    if active_year:

        start_year = int(active_year.year.split("/")[0])
        end_year = int(active_year.year.split("/")[1])

        next_year = f"{start_year + 1}/{end_year + 1}"

        active_year.is_active = False

        existing = AcademicYear.query.filter_by(year=next_year).first()

        if existing:
            existing.is_active = True
        else:
            new_year = AcademicYear(
                year=next_year,
                is_active=True
            )
            db.session.add(new_year)

    db.session.commit()

    flash(
        "Students promoted successfully. Academic year has been updated.",
        "success"
    )

    return redirect(url_for("auth.dashboard"))


#------------------------DEBTORS------------------------------


@auth.route("/debtors")
@login_required
def debtors():

    fees = Fee.query.filter(Fee.balance > 0).all()
    students = Student.query.filter_by(is_deleted=False).all()

    student_map = {}
    debtor_summary = {}

    for student in students:
        student_map[student.id] = student

    for fee in fees:

        # Skip deleted students
        if fee.student_id not in student_map:
            continue

        if fee.student_id not in debtor_summary:
            debtor_summary[fee.student_id] = 0

        debtor_summary[fee.student_id] += fee.balance

    debtor_summary = dict(
        sorted(
            debtor_summary.items(),
            key=lambda item: item[1],
            reverse=True
        )
    )

    total_outstanding = sum(debtor_summary.values())
    total_debtors = len(debtor_summary)

    return render_template(
        "debtors.html",
        debtor_summary=debtor_summary,
        student_map=student_map,
        total_outstanding=total_outstanding,
        total_debtors=total_debtors
    )

#---------------EXPORT DEBTORS Excel-------------------------------


@auth.route("/export-debtors-excel")
def export_debtors_excel():

    active_students = Student.query.filter_by(is_deleted=False).all()

    student_map = {}
    for student in active_students:
        student_map[student.id] = student

    fees = Fee.query.filter(Fee.balance > 0).all()

    debtor_summary = {}

    for fee in fees:

        # Skip deleted students
        if fee.student_id not in student_map:
            continue

        if fee.student_id not in debtor_summary:
            debtor_summary[fee.student_id] = 0

        debtor_summary[fee.student_id] += fee.balance

    wb = Workbook()
    ws = wb.active
    ws.title = "Debtors Report"

    ws.append(["Student ID", "Student Name", "Outstanding Balance"])

    for student_id, balance in debtor_summary.items():
        student = student_map.get(student_id)

        if student:
            ws.append([
                student.student_id,
                f"{student.first_name} {student.last_name}",
                balance
            ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="debtors_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

#----------------------EXPORT DEBTORS Pdf--------------------------------


@auth.route("/export-debtors-pdf")
def export_debtors_pdf():

    active_students = Student.query.filter_by(is_deleted=False).all()

    student_map = {}
    for student in active_students:
        student_map[student.id] = student

    fees = Fee.query.filter(Fee.balance > 0).all()

    debtor_summary = {}

    for fee in fees:

        if fee.student_id not in student_map:
            continue

        if fee.student_id not in debtor_summary:
            debtor_summary[fee.student_id] = 0

        debtor_summary[fee.student_id] += fee.balance

    buffer = io.BytesIO()

    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 50

    p.setFont("Helvetica-Bold", 16)
    p.drawString(200, y, "Debtors Report")

    y -= 40

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Student ID")
    p.drawString(180, y, "Student Name")
    p.drawString(420, y, "Balance")

    y -= 30

    p.setFont("Helvetica", 11)

    for student_id, balance in debtor_summary.items():
        student = student_map.get(student_id)

        if student:
            p.drawString(50, y, student.student_id)
            p.drawString(180, y, f"{student.first_name} {student.last_name}")
            p.drawString(420, y, str(balance))

            y -= 25

            if y < 50:
                p.showPage()
                y = height - 50

    p.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="debtors_report.pdf",
        mimetype="application/pdf"
    )

#---------------CHANGE PASSWORD--------------------------------

@auth.route("/change-password", methods=["GET", "POST"])
def change_password():

    user = User.query.first()

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not check_password_hash(user.password_hash, current_password):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("auth.change_password"))

        if new_password != confirm_password:
            flash("New passwords do not match.", "error")
            return redirect(url_for("auth.change_password"))

        if len(new_password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("auth.change_password"))

        user.password_hash = generate_password_hash(new_password)

        db.session.commit()

        flash("Password changed successfully.", "success")
        return redirect(url_for("auth.dashboard"))

    return render_template("change_password.html")


#---------------DEVELOPER TOOLS-----------------------------

@auth.route("/developer-tools-2026", methods=["GET", "POST"])
def developer_tools():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        developer = User.query.filter_by(username=username).first()

        if not developer:
            flash("Invalid developer credentials.", "error")
            return redirect(url_for("auth.developer_tools"))

        if developer.role != "developer":
            flash("Access denied.", "error")
            return redirect(url_for("auth.developer_tools"))

        if not check_password_hash(developer.password_hash, password):
            flash("Invalid developer credentials.", "error")
            return redirect(url_for("auth.developer_tools"))

        session["developer_access"] = True

        flash("Developer access granted.", "success")
        return redirect(url_for("auth.developer_tools"))

    return render_template("developer_tools.html")


#-----------------UNLOCK ADMIN-----------------------------


@auth.route("/unlock-admin")
def unlock_admin():

    if not session.get("developer_access"):
        flash("Unauthorized access.", "error")
        return redirect(url_for("auth.developer_tools"))

    admin = User.query.filter_by(username="admin").first()

    if not admin:
        flash("Admin account not found.", "error")
        return redirect(url_for("auth.developer_tools"))

    admin.failed_attempts = 0
    admin.locked_until_utc = None
    admin.is_active = True

    db.session.commit()

    flash("Admin unlocked successfully.", "success")
    return redirect(url_for("auth.developer_tools"))


#-------------------RESET ADMIN PASSWORD-------------------------


@auth.route("/reset-admin-password", methods=["POST"])
def reset_admin_password():

    if not session.get("developer_access"):
        flash("Unauthorized access.", "error")
        return redirect(url_for("auth.developer_tools"))

    new_password = request.form.get("new_password")

    admin = User.query.filter_by(username="admin").first()

    if not admin:
        flash("Admin account not found.", "error")
        return redirect(url_for("auth.developer_tools"))

    admin.password_hash = generate_password_hash(new_password)

    db.session.commit()

    flash("Admin password reset successfully.", "success")
    return redirect(url_for("auth.developer_tools"))


#-------------------CHANGE DEVELOPER PASSWORD------------------


@auth.route("/change-developer-password", methods=["POST"])
def change_developer_password():

    if not session.get("developer_access"):
        flash("Unauthorized access.", "error")
        return redirect(url_for("auth.developer_tools"))

    new_password = request.form.get("developer_password")

    developer = User.query.filter_by(role="developer").first()

    if not developer:
        flash("Developer account not found.", "error")
        return redirect(url_for("auth.developer_tools"))

    developer.password_hash = generate_password_hash(new_password)

    db.session.commit()

    flash("Developer password changed successfully.", "success")
    return redirect(url_for("auth.developer_tools"))


#---------------------LOGOUT------------------------------


@auth.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("auth.login"))


#------------------STUDENT PROFILE-------------------------


@auth.route("/student-profile/<int:student_id>")
@login_required
def student_profile(student_id):

    student = Student.query.get_or_404(student_id)

    fees = Fee.query.filter_by(
        student_id=student.id
    ).order_by(Fee.id.asc()).all()

    total_paid = sum(fee.amount_paid for fee in fees)

    if fees:
        total_balance = fees[-1].balance
    else:
        total_balance = 0

    return render_template(
        "student_profile.html",
        student=student,
        fees=fees,
        total_paid=total_paid,
        total_balance=total_balance
    )


#-----------------------DELETE STUDENT-----------------------


@auth.route("/delete-student/<int:student_id>")
@login_required
def soft_delete_student(student_id):

    student = Student.query.get_or_404(student_id)
    student.is_deleted = True

    db.session.commit()

    flash("Student moved to recycle bin.", "success")
    return redirect(url_for("auth.students"))


#-----------------RECYCLE BIN-----------------------------


@auth.route("/recycle-bin")
@login_required
def recycle_bin():

    students = Student.query.filter_by(is_deleted=True).all()

    return render_template(
        "recycle_bin.html",
        students=students
    )


#--------------------------RESTORE STUDENT------------------------------


@auth.route("/restore-student/<int:student_id>")
@login_required
def restore_student(student_id):

    student = Student.query.get_or_404(student_id)

    student.is_deleted = False

    db.session.commit()

    flash("Student restored successfully.", "success")
    return redirect(url_for("auth.recycle_bin"))


#------------------DELETE PERMANENTLY-------------------------


@auth.route("/permanent-delete-student/<int:student_id>")
@login_required
def permanent_delete_student(student_id):

    student = Student.query.get_or_404(student_id)

    db.session.delete(student)

    db.session.commit()

    flash("Student permanently deleted.", "success")
    return redirect(url_for("auth.recycle_bin"))


#-----------------------BACKUP DATABASE----------------------------

from flask import current_app, send_file, flash, redirect, url_for, session

@auth.route("/backup-database")
def backup_database():

    if not session.get("developer_access"):
        flash("Unauthorized access.", "error")
        return redirect(url_for("auth.developer_tools"))

    db_path = os.path.join(current_app.instance_path, "school.db")

    if not os.path.exists(db_path):
        flash(f"Database file not found: {db_path}", "error")
        return redirect(url_for("auth.developer_tools"))

    return send_file(
        db_path,
        as_attachment=True,
        download_name="school_backup.db"
    )


#-------------------DELETE SCHOOL FEE-------------------------------


@auth.route("/delete-school-fee/<int:id>")
@login_required
def delete_school_fee(id):

    fee = SchoolFee.query.get_or_404(id)

    fee_used = Fee.query.filter_by(
        total_fees=fee.amount
    ).first()

    if fee_used:
        flash("This school fee has already been used for student payments and cannot be deleted.", "error")
        return redirect(url_for("auth.school_fee_records"))

    db.session.delete(fee)
    db.session.commit()

    flash("School fee deleted successfully.", "success")

    return redirect(url_for("auth.school_fee_records"))





