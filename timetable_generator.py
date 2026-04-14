import random
from db import get_db_connection
from datetime import datetime, timedelta


# ---------------- SETTINGS ----------------

def get_settings():
    conn = get_db_connection()
    s = conn.execute("SELECT * FROM timetable_settings LIMIT 1").fetchone()
    conn.close()
    return s


def generate_days(n):
    base = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
    return base[:n]


def generate_periods(n):
    return ["p"+str(i+1) for i in range(n)]




def generate_time_slots():

    s = get_settings()

    start = datetime.strptime(s["start_time"], "%H:%M")
    duration = s["period_duration"]
    lunch_after = s["lunch_after"]
    lunch_duration = s["lunch_duration"]
    periods = s["periods_per_day"]

    slots = []
    period_no = 1

    for i in range(1, periods+1):

        end = start + timedelta(minutes=duration)

        slots.append({
            "type": "period",
            "p": "p" + str(period_no),
            "label": start.strftime("%H:%M") + "-" + end.strftime("%H:%M")
        })

        start = end
        period_no += 1

        if i == lunch_after:

            lunch_end = start + timedelta(minutes=lunch_duration)

            slots.append({
                "type": "lunch",
                "label": "LUNCH"
            })

            start = lunch_end

    return slots


# ---------------- FETCH DATA ----------------

def fetch_data():
    conn = get_db_connection()

    classes = conn.execute("SELECT * FROM class").fetchall()
    subjects = conn.execute("SELECT * FROM subject").fetchall()
    teachers = conn.execute("SELECT * FROM teacher WHERE status='Active'").fetchall()

    conn.close()
    return classes, subjects, teachers


# ---------------- HELPER ----------------

def teacher_free(teacher_busy, teacher_id, day, period):
    return teacher_id not in teacher_busy[day][period]


# ---------------- MAIN SCHEDULER ----------------

def schedule():

    s = get_settings()

    DAYS = generate_days(s["days_per_week"])
    PERIODS = generate_periods(s["periods_per_day"])

    classes, subjects, teachers = fetch_data()

    timetable = {
        cls["id"]: {
            day: {p: None for p in PERIODS}
            for day in DAYS
        }
        for cls in classes
    }

    teacher_busy = {
        day: {p: set() for p in PERIODS}
        for day in DAYS
    }

    for cls in classes:

        dept_subjects = [
            sub for sub in subjects
            if sub["department_id"] == cls["department_id"]
        ]

        theory_subjects = [
            sub for sub in dept_subjects
            if sub["type"] == "Subject"
        ]

        lab_subjects = [
            sub for sub in dept_subjects
            if sub["type"] == "Lab"
        ]

        # Track daily subject usage
        daily_count = {day: {} for day in DAYS}

        # ---------- LABS ----------
        for lab in lab_subjects:

            blocks = lab["hours"] // 2

            for _ in range(blocks):

                for _ in range(100):

                    day = random.choice(DAYS)
                    i = random.randint(0, len(PERIODS)-2)

                    p1 = PERIODS[i]
                    p2 = PERIODS[i+1]

                    if (
                        timetable[cls["id"]][day][p1] is None and
                        timetable[cls["id"]][day][p2] is None and
                        teacher_free(teacher_busy, lab["teacher_id"], day, p1) and
                        teacher_free(teacher_busy, lab["teacher_id"], day, p2)
                    ):

                        timetable[cls["id"]][day][p1] = lab["name"]
                        timetable[cls["id"]][day][p2] = lab["name"]

                        teacher_busy[day][p1].add(lab["teacher_id"])
                        teacher_busy[day][p2].add(lab["teacher_id"])

                        daily_count[day][lab["name"]] = daily_count[day].get(lab["name"], 0) + 2

                        break

        # ---------- THEORY ----------
        expanded = []
        subject_remaining = {}

        for sub in theory_subjects:
            expanded += [sub] * sub["hours"]

            subject_remaining[sub["name"]] = {
                "hours": sub["hours"],
                "teacher_id": sub["teacher_id"]
            }

        random.shuffle(expanded)

        for sub in expanded:

            for _ in range(100):

                day = random.choice(DAYS)
                period = random.choice(PERIODS)

                # max 2 per day
                if daily_count[day].get(sub["name"], 0) >= 2:
                    continue

                # avoid consecutive
                idx = PERIODS.index(period)
                if idx > 0:
                    prev_p = PERIODS[idx-1]
                    if timetable[cls["id"]][day][prev_p] == sub["name"]:
                        continue

                if (
                    timetable[cls["id"]][day][period] is None and
                    teacher_free(teacher_busy, sub["teacher_id"], day, period) and
                    subject_remaining[sub["name"]]["hours"] > 0
                ):

                    timetable[cls["id"]][day][period] = sub["name"]
                    teacher_busy[day][period].add(sub["teacher_id"])

                    subject_remaining[sub["name"]]["hours"] -= 1
                    daily_count[day][sub["name"]] = daily_count[day].get(sub["name"], 0) + 1

                    break

        # ---------- SMART FILL ----------
        for day in DAYS:
            for p in PERIODS:

                if timetable[cls["id"]][day][p] is None:

                    placed = False

                    for sub in theory_subjects:

                        if daily_count[day].get(sub["name"], 0) >= 2:
                            continue

                        teacher_id = sub["teacher_id"]

                        if not teacher_free(teacher_busy, teacher_id, day, p):
                            continue

                        timetable[cls["id"]][day][p] = sub["name"]
                        teacher_busy[day][p].add(teacher_id)

                        daily_count[day][sub["name"]] = daily_count[day].get(sub["name"], 0) + 1

                        placed = True
                        break

                    if not placed:
                        timetable[cls["id"]][day][p] = "FREE"

    return timetable


# ---------------- SAVE ----------------

def save_timetable_to_db(timetable):

    conn = get_db_connection()
    cursor = conn.cursor()

    s = get_settings()

    DAYS = generate_days(s["days_per_week"])
    PERIODS = generate_periods(s["periods_per_day"])

    cursor.execute("DELETE FROM timetable")

    for cls_id in timetable:
        for day in DAYS:

            row = {
                "class_id": cls_id,
                "day": day,
                "p1": "", "p2": "", "p3": "",
                "p4": "", "p5": "", "p6": "", "p7": ""
            }

            for p in PERIODS:
                row[p] = timetable[cls_id][day][p]

            cursor.execute("""
                INSERT INTO timetable
                (class_id, day, p1, p2, p3, p4, p5, p6, p7)
                VALUES
                (:class_id, :day, :p1, :p2, :p3, :p4, :p5, :p6, :p7)
            """, row)

    conn.commit()
    conn.close()

    print("✅ Perfect Timetable Generated")


# ---------------- RUN ----------------

def generate_and_save():
    timetable = schedule()
    save_timetable_to_db(timetable)
    return timetable