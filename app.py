from flask import Flask, render_template, request, redirect, jsonify, session
from timetable_generator import schedule, save_timetable_to_db, generate_time_slots
import sqlite3
from db import init_db
from werkzeug.security import generate_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = "secret123"

# Initialize DB
init_db()

# ---------------- DB CONNECTION ----------------
def get_db_connection():
    conn = sqlite3.connect("ai_timetable.db")
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- ADMIN CHECK ----------------
def is_admin_registered():
    with get_db_connection() as conn:
        admin = conn.execute("SELECT * FROM admin").fetchone()
    return admin is not None

# ---------------- LOGIN CHECK DECORATOR ----------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function

# ---------------- ROUTES ----------------

# Login page (redirect to registration if no admin)
@app.route("/")
def login_page():
    if not is_admin_registered():
        return redirect("/admin_register")
    return render_template("admin_login.html")

# Admin registration
@app.route("/admin_register", methods=["GET","POST"])
def admin_register():
    if is_admin_registered():
        return redirect("/")  # no duplicate registration

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO admin(username,password) VALUES(?,?)",
                (username,password)
            )

        return redirect("/")

    return render_template("admin_register.html")

# Admin login
@app.route("/admin_login", methods=["POST"])
def admin_login():
    username = request.form["username"]
    password = request.form["password"]

    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM admin WHERE username=? AND password=?",
            (username,password)
        ).fetchone()

    if user:
        session["admin_logged_in"] = True
        session["admin_id"] = user["id"]
        return redirect("/dashboard")
    else:
        return "Invalid login"

# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    with get_db_connection() as conn:
        dept_count = conn.execute("SELECT COUNT(*) FROM department").fetchone()[0]
        class_count = conn.execute("SELECT COUNT(*) FROM class").fetchone()[0]
        teacher_count = conn.execute("SELECT COUNT(*) FROM teacher").fetchone()[0]
        subject_count = conn.execute("SELECT COUNT(*) FROM subject").fetchone()[0]

    return render_template(
        "dashboard.html",
        dept_count=dept_count,
        class_count=class_count,
        teacher_count=teacher_count,
        subject_count=subject_count
    )

# ---------------- DEPARTMENT ----------------
@app.route("/departments")
@login_required
def departments_page():
    return render_template("departments.html")

@app.route("/add_department", methods=["POST"])
@login_required
def add_department():
    data = request.json
    with get_db_connection() as conn:
        conn.execute("INSERT INTO department(name) VALUES(?)",(data["name"],))
    return "added"

@app.route("/get_departments")
@login_required
def get_departments():
    with get_db_connection() as conn:
        data = conn.execute("SELECT * FROM department").fetchall()
    return jsonify([dict(row) for row in data])

@app.route("/delete_department/<int:id>", methods=["DELETE"])
@login_required
def delete_department(id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM department WHERE id=?",(id,))
    return "deleted"

# ---------------- ROOMS ----------------
@app.route("/rooms")
@login_required
def rooms_page():
    return render_template("rooms.html")

@app.route("/get_rooms")
@login_required
def get_rooms():
    with get_db_connection() as conn:
        rooms = conn.execute("SELECT * FROM rooms").fetchall()
    return jsonify([dict(r) for r in rooms])

@app.route("/add_room", methods=["POST"])
@login_required
def add_room():
    data = request.json
    room_names = data["room_name"].split(",")
    capacity = int(data["capacity"])
    with get_db_connection() as conn:
        for r in room_names:
            r = r.strip()
            if r:
                conn.execute("INSERT OR IGNORE INTO rooms(room_name,capacity) VALUES(?,?)",(r,capacity))
    return jsonify({"message": "Room(s) added successfully"})

@app.route("/delete_room/<int:id>", methods=["DELETE"])
@login_required
def delete_room(id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM rooms WHERE id=?",(id,))
    return jsonify({"message": "deleted"})

# ---------------- CLASSES ----------------
@app.route("/classes")
@login_required
def classes_page():
    return render_template("classes.html")

@app.route("/add_class", methods=["POST"])
@login_required
def add_class():
    data = request.json
    class_name = data["branch"] + " " + data["year"]
    with get_db_connection() as conn:
        conn.execute("INSERT INTO class(class_name,department_id) VALUES(?,?)",(class_name,data["department_id"]))
    return "added"

@app.route("/get_classes")
@login_required
def get_classes():
    with get_db_connection() as conn:
        data = conn.execute("""
        SELECT class.id,class.class_name,department.name
        FROM class
        JOIN department ON class.department_id = department.id
        """).fetchall()
    return jsonify([{"id":row[0],"class_name":row[1],"department":row[2]} for row in data])

@app.route("/delete_class/<int:id>", methods=["DELETE"])
@login_required
def delete_class(id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM class WHERE id=?",(id,))
    return "deleted"



# ---------------- PUBLIC REGISTRATION PAGE ----------------

@app.route("/faculty_register")
def faculty_register_page():
    return render_template("faculty_register.html")


# ---------------- ADMIN FACULTY LIST PAGE ----------------

@app.route("/teachers")
@login_required
def teachers_page():
    return render_template("teachers.html")


# ---------------- PENDING APPROVAL PAGE ----------------

@app.route("/faculty_approval")
@login_required
def faculty_approval():

    conn = get_db_connection()

    faculty = conn.execute("""
        SELECT 
            t.id,
            t.name,
            t.email,
            t.status,
            d.name as department
        FROM teacher t
        LEFT JOIN department d
        ON t.department_id = d.id
        WHERE t.status='Pending'
        ORDER BY t.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "faculty_approval.html",
        faculty=faculty
    )


# ---------------- FACULTY SIGNUP ----------------

@app.route("/faculty_signup", methods=["POST"])
def faculty_signup():

    data = request.json

    if not data:
        return jsonify({
            "error":"No data received"
        }),400


    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    department_id = data.get("department_id")


    # validation
    if not name or not email or not password or not department_id:

        return jsonify({
            "error":"All fields required"
        }),400


    conn = get_db_connection()


    # check duplicate email
    existing = conn.execute(
        "SELECT id FROM teacher WHERE email=?",
        (email,)
    ).fetchone()


    if existing:

        conn.close()

        return jsonify({
            "error":"Email already registered"
        }),400


    # hash password
    hashed_password = generate_password_hash(password)


    conn.execute("""

        INSERT INTO teacher
        (
            name,
            email,
            password,
            department_id,
            status
        )

        VALUES
        (
            ?,?,?,?,?
        )

    """,

    (
        name,
        email,
        hashed_password,
        department_id,
        "Pending"
    )

    )


    conn.commit()

    conn.close()


    return jsonify({

        "message":
        "Registered successfully. Wait for admin approval."

    })


# ---------------- GET ALL FACULTY ----------------

@app.route("/get_faculty")
@login_required
def get_faculty():

    conn = get_db_connection()

    faculty = conn.execute("""

        SELECT 
            teacher.id,
            teacher.name,
            teacher.email,
            teacher.status,
            department.name as department

        FROM teacher

        LEFT JOIN department

        ON teacher.department_id = department.id

        ORDER BY teacher.id DESC

    """).fetchall()

    conn.close()


    return jsonify(

        [dict(f) for f in faculty]

    )


# ---------------- APPROVE FACULTY ----------------

@app.route("/approve_faculty/<int:id>")
@login_required
def approve_faculty(id):

    conn = get_db_connection()

    conn.execute(
        "UPDATE teacher SET status='Active' WHERE id=?",
        (id,)
    )

    conn.commit()

    conn.close()


    return jsonify({

        "message":"Faculty approved"

    })


# ---------------- DELETE FACULTY ----------------

@app.route(
    "/delete_faculty/<int:id>",
    methods=["DELETE"]
)
@login_required
def delete_faculty(id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM teacher WHERE id=?",
        (id,)
    )

    conn.commit()

    conn.close()


    return jsonify({

        "message":"Faculty deleted"

    })


# ---------------- ACTIVE TEACHERS FOR SUBJECT DROPDOWN ----------------

@app.route("/get_active_teachers")
@login_required
def get_active_teachers():

    conn = get_db_connection()

    teachers = conn.execute("""

        SELECT 
            id,
            name

        FROM teacher

        WHERE status='Active'

        ORDER BY name

    """).fetchall()

    conn.close()


    return jsonify(

        [dict(t) for t in teachers]

    )

# ---------------- SUBJECTS & LABS ----------------
@app.route("/subjects")
@login_required
def subjects_page():
    return render_template("subjects.html")

@app.route("/add_subject", methods=["POST"])
@login_required
def add_subject():
    data = request.json
    if not all(data.get(k) for k in ["name","code","department_id","teacher_id"]):
        return jsonify({"error":"All fields required"}),400
    name = data["name"].strip()
    code = data["code"].strip().upper()
    dept_id = int(data["department_id"])
    teacher_id = int(data["teacher_id"])
    with get_db_connection() as conn:
        teacher = conn.execute("SELECT status FROM teacher WHERE id=?",(teacher_id,)).fetchone()
        if not teacher or teacher["status"]!="Active":
            return jsonify({"error":"Only active teachers allowed"}),400
        exists = conn.execute("SELECT id FROM subject WHERE name=? AND department_id=? AND type='Subject'",(name,dept_id)).fetchone()
        if exists:
            return jsonify({"error":f"{name} already exists"}),400
        conn.execute("INSERT INTO subject(name,code,type,hours,department_id,teacher_id) VALUES(?,?,?,?,?,?)",
                     (name,code,"Subject",3,dept_id,teacher_id))
    return jsonify({"message":f"{name} ({code}) added"})

@app.route("/get_subjects")
@login_required
def get_subjects():
    with get_db_connection() as conn:
        data = conn.execute("""
            SELECT s.id,s.name,s.code,s.type,s.hours,d.name as department,t.name as teacher
            FROM subject s
            JOIN department d ON s.department_id=d.id
            JOIN teacher t ON s.teacher_id=t.id
            ORDER BY s.department_id,s.name
        """).fetchall()
    return jsonify([dict(row) for row in data])

@app.route("/delete_subject/<int:id>",methods=["DELETE"])
@login_required
def delete_subject(id):
    with get_db_connection() as conn:
        sub = conn.execute("SELECT name,code FROM subject WHERE id=?",(id,)).fetchone()
        if not sub:
            return jsonify({"error":"Subject not found"}),404
        conn.execute("DELETE FROM subject WHERE id=?",(id,))
    return jsonify({"message":f'{sub["name"]} ({sub["code"]}) deleted'})

@app.route("/add_lab", methods=["POST"])
@login_required
def add_lab():
    data = request.json

    # check all required fields
    if not all(data.get(k) for k in ["name","code","department_id","teacher_id","duration"]):
        return jsonify({"error":"All fields required"}),400

    name = data["name"].strip()
    code = data["code"].strip().upper()
    dept_id = int(data["department_id"])
    teacher_id = int(data["teacher_id"])
    duration = int(data["duration"])

    # validate duration
    if duration <= 0:
        return jsonify({"error":"Duration must be at least 1 period"}),400

    with get_db_connection() as conn:
        # check if teacher is active
        teacher = conn.execute("SELECT status FROM teacher WHERE id=?",(teacher_id,)).fetchone()
        if not teacher or teacher["status"] != "Active":
            return jsonify({"error":"Only active teachers allowed"}),400

        # check duplicate by name or code
        exists = conn.execute(
            "SELECT id FROM subject WHERE (name=? OR code=?) AND department_id=? AND type='Lab'",
            (name, code, dept_id)
        ).fetchone()

        if exists:
            return jsonify({"error":f"{name} lab or code {code} already exists"}),400

        # insert lab
        conn.execute(
            "INSERT INTO subject(name,code,type,hours,department_id,teacher_id) VALUES(?,?,?,?,?,?)",
            (name, code, "Lab", duration, dept_id, teacher_id)
        )

    return jsonify({"message":f"{name} ({code}) added successfully"})
@app.route("/get_labs")
@login_required
def get_labs():
    with get_db_connection() as conn:
        data = conn.execute("""
            SELECT s.id,s.name,s.code,s.type,s.hours as duration,d.name as department,t.name as teacher
            FROM subject s
            JOIN department d ON s.department_id=d.id
            JOIN teacher t ON s.teacher_id=t.id
            WHERE s.type='Lab'
            ORDER BY s.department_id,s.name
        """).fetchall()
    return jsonify([dict(row) for row in data])

@app.route("/delete_lab/<int:id>",methods=["DELETE"])
@login_required
def delete_lab(id):
    with get_db_connection() as conn:
        lab = conn.execute("SELECT name,code FROM subject WHERE id=? AND type='Lab'",(id,)).fetchone()
        if not lab:
            return jsonify({"error":"Lab not found"}),404
        conn.execute("DELETE FROM subject WHERE id=?",(id,))
    return jsonify({"message":f'{lab["name"]} ({lab["code"]}) deleted'})





# ---------------- OPEN TIMETABLE SETTINGS PAGE ----------------

@app.route("/timetable_settings")
@login_required
def timetable_settings():

    return render_template("timetable_settings.html")


# ---------------- SAVE SETTINGS ----------------

@app.route("/save_settings", methods=["POST"])
@login_required
def save_settings():

    data = request.get_json()

    conn = get_db_connection()

    # remove old settings
    conn.execute("DELETE FROM timetable_settings")

    # save new settings
    conn.execute("""

    INSERT INTO timetable_settings(

    days_per_week,
    periods_per_day,
    start_time,
    period_duration,
    lunch_after,
    lunch_duration

    )

    VALUES (?,?,?,?,?,?)

    """,(

    data["days"],
    data["periods"],
    data["start_time"],
    data["duration"],
    data["lunch_after"],
    data["lunch_duration"]

    ))

    conn.commit()

    conn.close()

    return jsonify({
        "message":"Settings Saved Successfully"
    })


# ---------------- OPEN GENERATE PAGE ----------------

@app.route("/generate_timetable")
@login_required
def generate_page():

    return render_template("generate_timetable.html")


# ---------------- GENERATE TIMETABLE ----------------

@app.route("/generate_timetable_action")
@login_required
def generate_timetable_action():

    try:

        timetable = schedule()

        save_timetable_to_db(timetable)

        return jsonify({
            "status":"success"
        })

    except Exception as e:

        return jsonify({
            "status":"error",
            "message":str(e)
        })
# ---------------- GET TIMETABLE DATA ----------------

@app.route("/get_timetable")
@login_required
def get_timetable():

    conn = get_db_connection()

    timetable = conn.execute("""

    SELECT *

    FROM timetable

    ORDER BY

    CASE day

        WHEN 'Monday' THEN 1
        WHEN 'Tuesday' THEN 2
        WHEN 'Wednesday' THEN 3
        WHEN 'Thursday' THEN 4
        WHEN 'Friday' THEN 5
        WHEN 'Saturday' THEN 6

    END

    """).fetchall()

    conn.close()

    # generate dynamic time slots
    times = generate_time_slots()

    return jsonify({

        "rows":[dict(row) for row in timetable],

        "times":times

    })


# ---------------- RUN ----------------

if __name__ == "__main__":

    app.run(debug=True)