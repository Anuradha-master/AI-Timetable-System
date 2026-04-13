import sqlite3
DB_NAME = "ai_timetable.db"

# ---------- SIMPLE CONNECTION ----------
def connect():
    return sqlite3.connect(DB_NAME, timeout=30)

# ---------- DICT STYLE CONNECTION ----------
def get_db_connection():

    conn = sqlite3.connect(
        DB_NAME,
        timeout=30,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


# ---------- INIT DATABASE ----------
def init_db():
    conn = connect()
    c = conn.cursor()

    # ---------------- ADMIN ----------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS admin(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)


    # ---------------- DEPARTMENT ----------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS department(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
    """)


    # ---------------- CLASS ----------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS class(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_name TEXT,
        department_id INTEGER
    )
    """)


    # ---------------- ROOMS ----------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS rooms(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_name TEXT UNIQUE,
        capacity INTEGER
    )
    """)


    # ---------------- TEACHER ----------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS teacher(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        department_id INTEGER,
        status TEXT DEFAULT 'Pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (department_id) REFERENCES department(id)
    )
    """)


    # ---------------- SUBJECT ----------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS subject(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL DEFAULT 'Subject',
        hours INTEGER NOT NULL DEFAULT 3,
        department_id INTEGER NOT NULL,
        teacher_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (department_id) REFERENCES department(id),
        FOREIGN KEY (teacher_id) REFERENCES teacher(id),
        CHECK (type IN ('Subject','Lab'))
    )
    """)


    # ---------------- TIMETABLE SETTINGS ----------------
    c.execute("""
    CREATE TABLE IF NOT EXISTS timetable_settings(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        days_per_week INTEGER DEFAULT 5,

        periods_per_day INTEGER DEFAULT 6,

        start_time TEXT DEFAULT '09:00',

        period_duration INTEGER DEFAULT 50,

        lunch_after INTEGER DEFAULT 3,

        lunch_duration INTEGER DEFAULT 40

    )
    """)


    # insert default row only once
    c.execute("SELECT COUNT(*) FROM timetable_settings")

    if c.fetchone()[0] == 0:

        c.execute("""

        INSERT INTO timetable_settings(

        days_per_week,
        periods_per_day,
        start_time,
        period_duration,
        lunch_after,
        lunch_duration

        )

        VALUES (5,6,'09:00',50,3,40)

        """)


    # ---------------- TIMETABLE ----------------

    c.execute("""
    CREATE TABLE IF NOT EXISTS timetable(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        class_id INTEGER,

        day TEXT,

        p1 TEXT,
        p2 TEXT,
        p3 TEXT,
        p4 TEXT,
        p5 TEXT,
        p6 TEXT,
        p7 TEXT,
        p8 TEXT,
        p9 TEXT,
        p10 TEXT

    )
    """)
    conn.commit()
    conn.close()

    print("Database initialized successfully")