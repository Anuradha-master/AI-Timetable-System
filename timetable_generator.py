import random
from db import get_db_connection
from datetime import datetime, timedelta
import openai

# ---------------- OPENAI CONFIG ----------------
openai.api_key = "YOUR_OPENAI_KEY"

def ai_suggest_theory_slot(cls_id, sub_name, teacher_id, timetable, DAYS, PERIODS):
    """
    Ask AI for best slot, fallback to random
    """
    prompt = f"""
    Schedule subject without teacher clash.

    Class ID: {cls_id}
    Subject: {sub_name}
    Teacher ID: {teacher_id}

    Days: {DAYS}
    Periods: {PERIODS}

    Suggest best Day and Period.
    Output format:
    Monday,p1
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        text = response['choices'][0]['message']['content'].strip()

        day, period = text.split(",")

        return day.strip(), period.strip()

    except:
        return random.choice(DAYS), random.choice(PERIODS)


# ---------------- SETTINGS ----------------

def get_settings():
    conn = get_db_connection()

    s = conn.execute(
        "SELECT * FROM timetable_settings LIMIT 1"
    ).fetchone()

    conn.close()

    return s


def generate_days(n):
    base = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]

    return base[:n]


def generate_periods(n):
    return ["p"+str(i+1) for i in range(n)]


# ---------------- TIME SLOT ----------------

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
            "type":"period",
            "p":"p"+str(period_no),
            "label": start.strftime("%H:%M") + "-" + end.strftime("%H:%M")
        })

        start = end

        period_no += 1

        if i == lunch_after:

            lunch_end = start + timedelta(minutes=lunch_duration)

            slots.append({
                "type":"lunch",
                "label":"LUNCH"
            })

            start = lunch_end

    return slots


# ---------------- FETCH DATA ----------------

def fetch_data():

    conn = get_db_connection()

    classes = conn.execute(
        "SELECT * FROM class"
    ).fetchall()

    subjects = conn.execute(
        "SELECT * FROM subject"
    ).fetchall()

    teachers = conn.execute(
        "SELECT * FROM teacher WHERE status='Active'"
    ).fetchall()

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


    # empty timetable

    timetable = {

        cls["id"]:{
            day:{p:None for p in PERIODS}
            for day in DAYS
        }

        for cls in classes
    }


    teacher_busy = {

        day:{
            p:set() for p in PERIODS
        }

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


        # ---------- PLACE LAB FIRST ----------

        for lab in lab_subjects:

            hours = lab["hours"]

            block_size = 2

            blocks = hours // block_size


            for b in range(blocks):

                placed = False

                attempts = 0


                while not placed and attempts < 100:

                    day = random.choice(DAYS)

                    i = random.randint(0, len(PERIODS)-2)


                    p1 = PERIODS[i]

                    p2 = PERIODS[i+1]


                    if (

                        timetable[cls["id"]][day][p1] is None

                        and timetable[cls["id"]][day][p2] is None

                        and teacher_free(teacher_busy, lab["teacher_id"], day, p1)

                        and teacher_free(teacher_busy, lab["teacher_id"], day, p2)

                    ):

                        timetable[cls["id"]][day][p1] = lab["name"]

                        timetable[cls["id"]][day][p2] = lab["name"]


                        teacher_busy[day][p1].add(lab["teacher_id"])

                        teacher_busy[day][p2].add(lab["teacher_id"])


                        placed = True


                    attempts += 1


        # ---------- PLACE THEORY ----------

        expanded = []


        for sub in theory_subjects:

            for i in range(sub["hours"]):

                expanded.append(sub)


        for sub in expanded:

            placed = False

            attempts = 0


            while not placed and attempts < 100:


                day, period = ai_suggest_theory_slot(

                    cls["id"],

                    sub["name"],

                    sub["teacher_id"],

                    timetable,

                    DAYS,

                    PERIODS

                )


                if (

                    timetable[cls["id"]][day][period] is None

                    and teacher_free(

                        teacher_busy,

                        sub["teacher_id"],

                        day,

                        period

                    )

                ):

                    timetable[cls["id"]][day][period] = sub["name"]


                    teacher_busy[day][period].add(

                        sub["teacher_id"]

                    )


                    placed = True


                attempts += 1


    # ---------- FILL EMPTY SLOTS ----------

    for cls_id in timetable:

        for day in DAYS:

            for p in PERIODS:

                if timetable[cls_id][day][p] is None:

                    timetable[cls_id][day][p] = "FREE"


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

                "class_id":cls_id,

                "day":day,

                "p1":"",

                "p2":"",

                "p3":"",

                "p4":"",

                "p5":"",

                "p6":"",

                "p7":""

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

    print("Timetable Generated Successfully")


# ---------------- RUN ----------------

def generate_and_save():

    timetable = schedule()

    save_timetable_to_db(timetable)

    return timetable