# # app.py
# # Streamlit Lecture Arrangement Portal
# # -----------------------------------
# # Features
# # - Public timetable page (no login required)
# # - Departmental (HOD) login
# # - HODs can add classes/teachers/subjects/rooms and arrange the timetable
# # - Fixed day/period structure (Mon–Sat), with Lunch 1:00–1:55 PM after 4 periods
# # - Finalize/Lock timetable per department (read-only once finalized; can unlock)
# # - SQLite persistence
# #
# # How to run:
# #   1) Install deps:  pip install streamlit pandas
# #   2) Launch:        streamlit run app.py
# #
# # Demo HOD login (change after first run):
# #   Dept: CSE | username: csehod | password: 1234

# import hashlib
# import sqlite3
# from contextlib import closing
# from datetime import datetime
# from typing import List, Tuple

# import pandas as pd
# import streamlit as st

# DB_PATH = "lecture_portal.db"

# # -------------------------------
# # Fixed day/slot structure
# # -------------------------------
# DAYS = [
#     (1, "Monday"),
#     (2, "Tuesday"),
#     (3, "Wednesday"),
#     (4, "Thursday"),
#     (5, "Friday"),
#     (6, "Saturday"),
# ]

# # Seven teaching periods with lunch after Period 4
# # Edit these if your institute uses different times
# PERIODS = [
#     (1, "09:40–10:30"),
#     (2, "10:30–11:20"),
#     (3, "11:20–12:10"),
#     (4, "12:10–13:00"),  # Lunch after P4
#     (5, "13:55–14:45"),
#     (6, "14:45–15:35"),
#     (7, "15:45–16:25"),  # As requested (3:45–4:25)
# ]

# LUNCH_LABEL = "Lunch 13:00–13:55"

# # -------------------------------
# # Helpers
# # -------------------------------


# def sha256(text: str) -> str:
#     return hashlib.sha256(text.encode("utf-8")).hexdigest()


# def run_query(q: str, params: Tuple = ()):  # returns list of tuples
#     with sqlite3.connect(DB_PATH) as con:
#         with closing(con.cursor()) as cur:
#             cur.execute(q, params)
#             rows = cur.fetchall()
#     return rows


# def run_exec(q: str, params: Tuple = ()):  # executes INSERT/UPDATE/DELETE
#     with sqlite3.connect(DB_PATH) as con:
#         with closing(con.cursor()) as cur:
#             cur.execute(q, params)
#             con.commit()


# # -------------------------------
# # DB Setup
# # -------------------------------


# def init_db():
#     with sqlite3.connect(DB_PATH) as con:
#         cur = con.cursor()
#         cur.executescript(
#             """
#             CREATE TABLE IF NOT EXISTS departments (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 name TEXT UNIQUE NOT NULL,
#                 hod_username TEXT UNIQUE NOT NULL,
#                 hod_password_hash TEXT NOT NULL,
#                 is_finalized INTEGER DEFAULT 0,
#                 updated_at TEXT
#             );

#             CREATE TABLE IF NOT EXISTS classes (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 department_id INTEGER NOT NULL,
#                 name TEXT NOT NULL,
#                 UNIQUE(department_id, name),
#                 FOREIGN KEY(department_id) REFERENCES departments(id)
#             );

#             CREATE TABLE IF NOT EXISTS teachers (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 department_id INTEGER NOT NULL,
#                 name TEXT NOT NULL,
#                 short_code TEXT,
#                 UNIQUE(department_id, name),
#                 FOREIGN KEY(department_id) REFERENCES departments(id)
#             );

#             CREATE TABLE IF NOT EXISTS subjects (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 department_id INTEGER NOT NULL,
#                 code TEXT,
#                 name TEXT NOT NULL,
#                 UNIQUE(department_id, name),
#                 FOREIGN KEY(department_id) REFERENCES departments(id)
#             );

#             CREATE TABLE IF NOT EXISTS rooms (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 name TEXT UNIQUE NOT NULL,
#                 capacity INTEGER
#             );

#             CREATE TABLE IF NOT EXISTS timetable (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 department_id INTEGER NOT NULL,
#                 class_id INTEGER NOT NULL,
#                 day INTEGER NOT NULL,
#                 period INTEGER NOT NULL,
#                 subject_id INTEGER,
#                 teacher_id INTEGER,
#                 room_id INTEGER,
#                 note TEXT,
#                 UNIQUE(department_id, class_id, day, period),
#                 FOREIGN KEY(department_id) REFERENCES departments(id),
#                 FOREIGN KEY(class_id) REFERENCES classes(id),
#                 FOREIGN KEY(subject_id) REFERENCES subjects(id),
#                 FOREIGN KEY(teacher_id) REFERENCES teachers(id),
#                 FOREIGN KEY(room_id) REFERENCES rooms(id)
#             );
#             """
#         )
#         con.commit()

#         # Seed demo department/HOD if empty
#         cur.execute("SELECT COUNT(*) FROM departments")
#         if cur.fetchone()[0] == 0:
#             cur.execute(
#                 "INSERT INTO departments(name, hod_username, hod_password_hash, is_finalized, updated_at) VALUES(?,?,?,?,?)",
#                 ("CSE", "csehod", sha256("1234"), 0, datetime.utcnow().isoformat()),
#             )
#             con.commit()


# # -------------------------------
# # Auth
# # -------------------------------


# def auth_hod(username: str, password: str):
#     rows = run_query(
#         "SELECT id, name, is_finalized FROM departments WHERE hod_username=? AND hod_password_hash=?",
#         (username, sha256(password)),
#     )
#     if rows:
#         dept_id, dept_name, is_finalized = rows[0]
#         return {
#             "department_id": dept_id,
#             "department_name": dept_name,
#             "is_finalized": bool(is_finalized),
#         }
#     return None


# # -------------------------------
# # CRUD helpers
# # -------------------------------


# def get_departments() -> List[Tuple[int, str]]:
#     return run_query("SELECT id, name FROM departments ORDER BY name")


# def get_classes(dept_id: int):
#     return run_query(
#         "SELECT id, name FROM classes WHERE department_id=? ORDER BY name", (dept_id,)
#     )


# def get_teachers(dept_id: int):
#     return run_query(
#         "SELECT id, name FROM teachers WHERE department_id=? ORDER BY name", (dept_id,)
#     )


# def get_subjects(dept_id: int):
#     return run_query(
#         "SELECT id, COALESCE(code,'') || CASE WHEN code IS NULL OR code='' THEN '' ELSE ' - ' END || name FROM subjects WHERE department_id=? ORDER BY name",
#         (dept_id,),
#     )


# def get_rooms():
#     return run_query("SELECT id, name FROM rooms ORDER BY name")


# def upsert_timetable(
#     dept_id: int,
#     class_id: int,
#     day: int,
#     period: int,
#     subject_id: int,
#     teacher_id: int,
#     room_id: int,
#     note: str = "",
# ):
#     # Insert or update the unique (dept, class, day, period)
#     existing = run_query(
#         "SELECT id FROM timetable WHERE department_id=? AND class_id=? AND day=? AND period=?",
#         (dept_id, class_id, day, period),
#     )
#     if existing:
#         run_exec(
#             "UPDATE timetable SET subject_id=?, teacher_id=?, room_id=?, note=? WHERE id=?",
#             (subject_id, teacher_id, room_id, note, existing[0][0]),
#         )
#     else:
#         run_exec(
#             "INSERT INTO timetable(department_id, class_id, day, period, subject_id, teacher_id, room_id, note) VALUES(?,?,?,?,?,?,?,?)",
#             (dept_id, class_id, day, period, subject_id, teacher_id, room_id, note),
#         )


# def clear_slot(dept_id: int, class_id: int, day: int, period: int):
#     run_exec(
#         "DELETE FROM timetable WHERE department_id=? AND class_id=? AND day=? AND period=?",
#         (dept_id, class_id, day, period),
#     )


# def fetch_timetable_df(dept_id: int, class_id: int) -> pd.DataFrame:
#     # Build a grid with periods as rows and days as cols
#     # Cell content: "SUBJ\nTEACHER\nROOM"
#     df = pd.DataFrame(index=[p for p, _ in PERIODS], columns=[d for d, _ in DAYS])
#     df[:] = ""

#     rows = run_query(
#         """
#         SELECT t.day, t.period,
#                COALESCE(s.name, '') AS subject,
#                COALESCE(te.name, '') AS teacher,
#                COALESCE(r.name, '') AS room
#         FROM timetable t
#         LEFT JOIN subjects s ON t.subject_id = s.id
#         LEFT JOIN teachers te ON t.teacher_id = te.id
#         LEFT JOIN rooms r ON t.room_id = r.id
#         WHERE t.department_id=? AND t.class_id=?
#         """,
#         (dept_id, class_id),
#     )
#     for day, period, subject, teacher, room in rows:
#         parts = [x for x in [subject, teacher, room] if x]
#         df.loc[period, day] = "\n".join(parts)

#     # Replace indices/columns with labels
#     df.index = [f"P{p} ({label})" for p, label in PERIODS]
#     df.columns = [label for _, label in DAYS]

#     # Insert Lunch visual row after P4
#     lunch_row = pd.DataFrame({c: LUNCH_LABEL for c in df.columns}, index=["Lunch"])
#     top = df.iloc[:4]
#     bottom = df.iloc[4:]
#     df_out = pd.concat([top, lunch_row, bottom])
#     return df_out


# # -------------------------------
# # UI Components
# # -------------------------------


# def public_view():
#     st.title("📅 Public Timetable")
#     depts = get_departments()
#     if not depts:
#         st.info("No departments yet.")
#         return

#     dept_name_to_id = {name: did for did, name in depts}
#     dept_name = st.selectbox("Department", [name for _, name in depts])
#     dept_id = dept_name_to_id[dept_name]

#     classes = get_classes(dept_id)
#     if not classes:
#         st.info("No classes for this department.")
#         return

#     class_name_to_id = {name: cid for cid, name in classes}
#     class_name = st.selectbox("Class/Section", [name for _, name in classes])
#     class_id = class_name_to_id[class_name]

#     df = fetch_timetable_df(dept_id, class_id)
#     st.dataframe(df, use_container_width=True)

#     # Download as CSV
#     csv = df.to_csv().encode("utf-8")
#     st.download_button(
#         "Download CSV",
#         data=csv,
#         file_name=f"{dept_name}_{class_name}_timetable.csv",
#         mime="text/csv",
#     )


# def hod_dashboard(hod_info):
#     st.title(f"🛠️ HOD Dashboard — {hod_info['department_name']}")

#     # Finalize toggle
#     finalized = hod_info["is_finalized"]
#     status = "🔒 Finalized (read-only)" if finalized else "🟢 Editable"
#     st.subheader(f"Status: {status}")

#     cols = st.columns(3)
#     with cols[0]:
#         if finalized:
#             if st.button("Unlock for Editing"):
#                 run_exec(
#                     "UPDATE departments SET is_finalized=0, updated_at=? WHERE id=?",
#                     (datetime.utcnow().isoformat(), hod_info["department_id"]),
#                 )
#                 st.rerun()
#         else:
#             if st.button("Finalize / Lock Timetable"):
#                 run_exec(
#                     "UPDATE departments SET is_finalized=1, updated_at=? WHERE id=?",
#                     (datetime.utcnow().isoformat(), hod_info["department_id"]),
#                 )
#                 st.rerun()

#     st.divider()

#     # Data management
#     st.header("Masters")
#     tab_classes, tab_teachers, tab_subjects, tab_rooms = st.tabs(
#         ["Classes", "Teachers", "Subjects", "Rooms"]
#     )

#     disabled = finalized

#     with tab_classes:
#         st.subheader("Add Class/Section")
#         cname = st.text_input("Class name (e.g., CSE-2A)", key="cname")
#         if st.button("Add Class", disabled=disabled) and cname.strip():
#             try:
#                 run_exec(
#                     "INSERT INTO classes(department_id, name) VALUES(?, ?)",
#                     (hod_info["department_id"], cname.strip()),
#                 )
#                 st.success("Added.")
#             except sqlite3.IntegrityError:
#                 st.warning("Class already exists.")

#         with st.expander("Existing Classes", expanded=True):
#             rows = get_classes(hod_info["department_id"]) or []
#             st.table(pd.DataFrame(rows, columns=["ID", "Name"]))

#     with tab_teachers:
#         st.subheader("Add Teacher")
#         tname = st.text_input("Teacher name")
#         tcode = st.text_input("Short code (optional)")
#         if st.button("Add Teacher", disabled=disabled) and tname.strip():
#             try:
#                 run_exec(
#                     "INSERT INTO teachers(department_id, name, short_code) VALUES(?,?,?)",
#                     (hod_info["department_id"], tname.strip(), tcode.strip()),
#                 )
#                 st.success("Added.")
#             except sqlite3.IntegrityError:
#                 st.warning("Teacher already exists.")

#         with st.expander("Existing Teachers", expanded=True):
#             rows = get_teachers(hod_info["department_id"]) or []
#             st.table(pd.DataFrame(rows, columns=["ID", "Name"]))

#     with tab_subjects:
#         st.subheader("Add Subject")
#         scode = st.text_input("Subject code (optional)")
#         sname = st.text_input("Subject name")
#         if st.button("Add Subject", disabled=disabled) and sname.strip():
#             try:
#                 run_exec(
#                     "INSERT INTO subjects(department_id, code, name) VALUES(?,?,?)",
#                     (hod_info["department_id"], scode.strip(), sname.strip()),
#                 )
#                 st.success("Added.")
#             except sqlite3.IntegrityError:
#                 st.warning("Subject already exists.")

#         with st.expander("Existing Subjects", expanded=True):
#             rows = run_query(
#                 "SELECT id, COALESCE(code,'') as code, name FROM subjects WHERE department_id=? ORDER BY name",
#                 (hod_info["department_id"],),
#             )
#             st.table(pd.DataFrame(rows, columns=["ID", "Code", "Name"]))

#     with tab_rooms:
#         st.subheader("Add Room (shared across departments)")
#         rname = st.text_input("Room name (e.g., FF01)")
#         rcap = st.number_input("Capacity (optional)", min_value=0, step=1)
#         if st.button("Add Room", disabled=disabled) and rname.strip():
#             try:
#                 run_exec(
#                     "INSERT INTO rooms(name, capacity) VALUES(?, ?)",
#                     (rname.strip(), int(rcap) if rcap else None),
#                 )
#                 st.success("Added.")
#             except sqlite3.IntegrityError:
#                 st.warning("Room already exists.")

#         with st.expander("Existing Rooms", expanded=True):
#             rows = run_query("SELECT id, name, capacity FROM rooms ORDER BY name") or []
#             st.table(pd.DataFrame(rows, columns=["ID", "Name", "Capacity"]))

#     st.divider()

#     # Timetable builder
#     st.header("Arrange Timetable")

#     # Choose class
#     classes = get_classes(hod_info["department_id"]) or []
#     if not classes:
#         st.info("Add at least one Class in Masters → Classes.")
#         return

#     class_name_map = {name: cid for cid, name in classes}
#     class_name = st.selectbox("Class/Section", [name for _, name in classes])
#     class_id = class_name_map[class_name]

#     # Pick slot
#     day_label_map = {label: d for d, label in DAYS}
#     period_label_map = {label: p for p, label in PERIODS}

#     day_label = st.selectbox("Day", [label for _, label in DAYS])
#     period_label = st.selectbox("Period", [label for _, label in PERIODS])

#     # Pick entities
#     subjects = get_subjects(hod_info["department_id"]) or []
#     teachers = get_teachers(hod_info["department_id"]) or []
#     rooms = get_rooms() or []

#     subject_map = {name: sid for sid, name in subjects}
#     teacher_map = {name: tid for tid, name in teachers}
#     room_map = {name: rid for rid, name in rooms}

#     subject_name = (
#         st.selectbox(
#             "Subject", list(subject_map.keys()) if subject_map else ["— None —"]
#         )
#         if subjects
#         else None
#     )
#     teacher_name = (
#         st.selectbox(
#             "Teacher", list(teacher_map.keys()) if teacher_map else ["— None —"]
#         )
#         if teachers
#         else None
#     )
#     room_name = (
#         st.selectbox("Room", list(room_map.keys()) if room_map else ["— None —"])
#         if rooms
#         else None
#     )

#     note = st.text_input("Note (optional)")

#     colA, colB = st.columns(2)
#     with colA:
#         if st.button(
#             "Save Slot", disabled=disabled or not (subjects and teachers and rooms)
#         ):
#             upsert_timetable(
#                 hod_info["department_id"],
#                 class_id,
#                 day_label_map[day_label],
#                 period_label_map[period_label],
#                 subject_map.get(subject_name),
#                 teacher_map.get(teacher_name),
#                 room_map.get(room_name),
#                 note.strip(),
#             )
#             st.success("Saved.")
#     with colB:
#         if st.button("Clear Slot", disabled=disabled):
#             clear_slot(
#                 hod_info["department_id"],
#                 class_id,
#                 day_label_map[day_label],
#                 period_label_map[period_label],
#             )
#             st.warning("Cleared.")

#     st.subheader("Preview for Selected Class")
#     df = fetch_timetable_df(hod_info["department_id"], class_id)
#     st.dataframe(df, use_container_width=True)

#     st.caption(
#         "Tip: Use the Public Timetable page for a read-only view and CSV export."
#     )


# # -------------------------------
# # App Entry
# # -------------------------------


# def main():
#     st.set_page_config(page_title="Lecture Arrangement Portal", layout="wide")
#     init_db()

#     st.sidebar.title("Portal Navigation")
#     page = st.sidebar.radio("Go to", ["Public Timetable", "HOD Login"], index=0)

#     if page == "Public Timetable":
#         public_view()
#         return

#     # HOD Login page
#     st.title("🔐 Departmental Login (HOD)")

#     with st.form("login_form"):
#         username = st.text_input("HOD Username")
#         password = st.text_input("Password", type="password")
#         submitted = st.form_submit_button("Login")

#     if submitted:
#         info = auth_hod(username, password)
#         if info:
#             st.session_state["hod_info"] = info
#             st.success(f"Welcome, {info['department_name']} HOD!")
#         else:
#             st.error("Invalid credentials.")

#     hod_info = st.session_state.get("hod_info")
#     if hod_info:
#         # Refresh finalized flag in case it changed
#         dept = run_query(
#             "SELECT is_finalized FROM departments WHERE id=?",
#             (hod_info["department_id"],),
#         )
#         if dept:
#             hod_info["is_finalized"] = bool(dept[0][0])
#         hod_dashboard(hod_info)


# if __name__ == "__main__":
#     main()


# app.py
# Streamlit Lecture Arrangement Portal
# -----------------------------------
# Features
# - Public timetable page (no login required)
# - Departmental (HOD) login (different HOD for each branch)
# - HODs can add classes/teachers/subjects/rooms and arrange the timetable
# - Fixed day/period structure (Mon–Sat), with Lunch 1:00–1:55 PM after 4 periods
# - Finalize/Lock timetable per department (read-only once finalized; can unlock)
# - SQLite persistence
# - Export timetable to Excel (with college header "XYZ")
#
# How to run:
#   1) Install deps:  pip install streamlit pandas openpyxl
#   2) Launch:        streamlit run app.py
#
# Demo HOD logins (default password for all is 1234 — change in production):
#   Dept: CSE    | username: cse_hod    | password: 1234
#   Dept: CIVIL  | username: civil_hod  | password: 1234
#   Dept: AI/ML  | username: aiml_hod   | password: 1234
#   Dept: AI/DS  | username: aids_hod   | password: 1234
#   Dept: EC     | username: ec_hod     | password: 1234
#   Dept: EE     | username: ee_hod     | password: 1234

import hashlib
import sqlite3
import os
from contextlib import closing
from datetime import datetime
from io import BytesIO
from typing import List, Tuple

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Helper function to get config values from either Streamlit secrets or environment variables
def get_config(key: str, default: str = "") -> str:
    # Try Streamlit secrets first (for cloud deployment)
    try:
        return st.secrets[key]
    except (KeyError, AttributeError):
        # Fall back to environment variables (for local development)
        return os.getenv(key, default)


DB_PATH = "lecture_portal.db"
COLLEGE_NAME = get_config("COLLEGE_NAME", "XYZ")

# -------------------------------
# Fixed day/slot structure
# -------------------------------
DAYS = [
    (1, "Monday"),
    (2, "Tuesday"),
    (3, "Wednesday"),
    (4, "Thursday"),
    (5, "Friday"),
    (6, "Saturday"),
]

# Seven teaching periods with lunch after Period 4
PERIODS = [
    (1, "09:40–10:30"),
    (2, "10:30–11:20"),
    (3, "11:20–12:10"),
    (4, "12:10–13:00"),  # Lunch after P4
    (5, "13:55–14:45"),
    (6, "14:45–15:35"),
    (7, "15:45–16:25"),  # 3:45–4:25
]

LUNCH_LABEL = "Lunch 13:00–13:55"

# -------------------------------
# Helpers
# -------------------------------


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_query(q: str, params: Tuple = ()):  # returns list of tuples
    with sqlite3.connect(DB_PATH) as con:
        with closing(con.cursor()) as cur:
            cur.execute(q, params)
            rows = cur.fetchall()
    return rows


def run_exec(q: str, params: Tuple = ()):  # executes INSERT/UPDATE/DELETE
    with sqlite3.connect(DB_PATH) as con:
        with closing(con.cursor()) as cur:
            cur.execute(q, params)
            con.commit()


# -------------------------------
# DB Setup
# -------------------------------


def init_db():
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                hod_username TEXT UNIQUE NOT NULL,
                hod_password_hash TEXT NOT NULL,
                is_finalized INTEGER DEFAULT 0,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(department_id, name),
                FOREIGN KEY(department_id) REFERENCES departments(id)
            );

            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                short_code TEXT,
                UNIQUE(department_id, name),
                FOREIGN KEY(department_id) REFERENCES departments(id)
            );

            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_id INTEGER NOT NULL,
                code TEXT,
                name TEXT NOT NULL,
                UNIQUE(department_id, name),
                FOREIGN KEY(department_id) REFERENCES departments(id)
            );

            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                capacity INTEGER
            );

            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                day INTEGER NOT NULL,
                period INTEGER NOT NULL,
                subject_id INTEGER,
                teacher_id INTEGER,
                room_id INTEGER,
                note TEXT,
                UNIQUE(department_id, class_id, day, period),
                FOREIGN KEY(department_id) REFERENCES departments(id),
                FOREIGN KEY(class_id) REFERENCES classes(id),
                FOREIGN KEY(subject_id) REFERENCES subjects(id),
                FOREIGN KEY(teacher_id) REFERENCES teachers(id),
                FOREIGN KEY(room_id) REFERENCES rooms(id)
            );
            """
        )
        con.commit()

        # Seed demo departments/HODs if empty
        cur.execute("SELECT COUNT(*) FROM departments")
        count = cur.fetchone()[0]

        if count == 0:
            demo = [
                (
                    "CSE",
                    get_config("CSE_HOD_USERNAME", "cse_hod"),
                    get_config("CSE_HOD_PASSWORD", "1234"),
                ),
                (
                    "CIVIL",
                    get_config("CIVIL_HOD_USERNAME", "civil_hod"),
                    get_config("CIVIL_HOD_PASSWORD", "1234"),
                ),
                (
                    "AI/ML",
                    get_config("AIML_HOD_USERNAME", "aiml_hod"),
                    get_config("AIML_HOD_PASSWORD", "1234"),
                ),
                (
                    "AI/DS",
                    get_config("AIDS_HOD_USERNAME", "aids_hod"),
                    get_config("AIDS_HOD_PASSWORD", "1234"),
                ),
                (
                    "EC",
                    get_config("EC_HOD_USERNAME", "ec_hod"),
                    get_config("EC_HOD_PASSWORD", "1234"),
                ),
                (
                    "EE",
                    get_config("EE_HOD_USERNAME", "ee_hod"),
                    get_config("EE_HOD_PASSWORD", "1234"),
                ),
            ]
            for name, user, pwd in demo:
                cur.execute(
                    "INSERT INTO departments(name, hod_username, hod_password_hash, is_finalized, updated_at) VALUES(?,?,?,?,?)",
                    (name, user, sha256(pwd), 0, datetime.utcnow().isoformat()),
                )
            con.commit()


# -------------------------------
# Auth
# -------------------------------


def auth_hod(username: str, password: str):
    rows = run_query(
        "SELECT id, name, is_finalized FROM departments WHERE hod_username=? AND hod_password_hash=?",
        (username, sha256(password)),
    )
    if rows:
        dept_id, dept_name, is_finalized = rows[0]
        return {
            "department_id": dept_id,
            "department_name": dept_name,
            "is_finalized": bool(is_finalized),
        }
    return None


# -------------------------------
# CRUD helpers
# -------------------------------


def get_departments() -> List[Tuple[int, str]]:
    return run_query("SELECT id, name FROM departments ORDER BY name")


def get_classes(dept_id: int):
    return run_query(
        "SELECT id, name FROM classes WHERE department_id=? ORDER BY name", (dept_id,)
    )


def get_teachers(dept_id: int):
    return run_query(
        "SELECT id, name FROM teachers WHERE department_id=? ORDER BY name", (dept_id,)
    )


def get_subjects(dept_id: int):
    return run_query(
        "SELECT id, COALESCE(code,'') || CASE WHEN code IS NULL OR code='' THEN '' ELSE ' - ' END || name FROM subjects WHERE department_id=? ORDER BY name",
        (dept_id,),
    )


def get_rooms():
    return run_query("SELECT id, name FROM rooms ORDER BY name")


def upsert_timetable(
    dept_id: int,
    class_id: int,
    day: int,
    period: int,
    subject_id: int,
    teacher_id: int,
    room_id: int,
    note: str = "",
):
    existing = run_query(
        "SELECT id FROM timetable WHERE department_id=? AND class_id=? AND day=? AND period=?",
        (dept_id, class_id, day, period),
    )
    if existing:
        run_exec(
            "UPDATE timetable SET subject_id=?, teacher_id=?, room_id=?, note=? WHERE id=?",
            (subject_id, teacher_id, room_id, note, existing[0][0]),
        )
    else:
        run_exec(
            "INSERT INTO timetable(department_id, class_id, day, period, subject_id, teacher_id, room_id, note) VALUES(?,?,?,?,?,?,?,?)",
            (dept_id, class_id, day, period, subject_id, teacher_id, room_id, note),
        )


def clear_slot(dept_id: int, class_id: int, day: int, period: int):
    run_exec(
        "DELETE FROM timetable WHERE department_id=? AND class_id=? AND day=? AND period=?",
        (dept_id, class_id, day, period),
    )


def fetch_timetable_df(dept_id: int, class_id: int) -> pd.DataFrame:
    df = pd.DataFrame(index=[p for p, _ in PERIODS], columns=[d for d, _ in DAYS])
    df[:] = ""

    rows = run_query(
        """
        SELECT t.day, t.period,
               COALESCE(s.name, '') AS subject,
               COALESCE(te.name, '') AS teacher,
               COALESCE(r.name, '') AS room
        FROM timetable t
        LEFT JOIN subjects s ON t.subject_id = s.id
        LEFT JOIN teachers te ON t.teacher_id = te.id
        LEFT JOIN rooms r ON t.room_id = r.id
        WHERE t.department_id=? AND t.class_id=?
        """,
        (dept_id, class_id),
    )
    for day, period, subject, teacher, room in rows:
        parts = [x for x in [subject, teacher, room] if x]
        df.loc[period, day] = "\n".join(parts)

    df.index = [f"P{p} ({label})" for p, label in PERIODS]
    df.columns = [label for _, label in DAYS]

    lunch_row = pd.DataFrame({c: LUNCH_LABEL for c in df.columns}, index=["Lunch"])
    top = df.iloc[:4]
    bottom = df.iloc[4:]
    df_out = pd.concat([top, lunch_row, bottom])
    return df_out


# -------------------------------
# Export helpers
# -------------------------------


def to_excel_bytes(df: pd.DataFrame, dept_name: str, class_name: str) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Write a header sheet containing college and meta
        meta = pd.DataFrame(
            {
                "College": [COLLEGE_NAME],
                "Department": [dept_name],
                "Class": [class_name],
                "GeneratedAt": [datetime.utcnow().isoformat()],
            }
        )
        meta.to_excel(writer, index=False, sheet_name="Info")
        # Write timetable
        df.to_excel(writer, index=True, sheet_name="Timetable")
        # Note: writer.save() is deprecated - the context manager handles saving automatically
    return output.getvalue()


# -------------------------------
# UI Components
# -------------------------------


def public_view():
    st.title(f"{COLLEGE_NAME} — Public Timetable")
    depts = get_departments()
    if not depts:
        st.info("No departments yet.")
        return

    dept_name_to_id = {name: did for did, name in depts}
    dept_name = st.selectbox("Department", [name for _, name in depts])
    dept_id = dept_name_to_id[dept_name]

    classes = get_classes(dept_id)
    if not classes:
        st.info("No classes for this department.")
        return

    class_name_to_id = {name: cid for cid, name in classes}
    class_name = st.selectbox("Class/Section", [name for _, name in classes])
    class_id = class_name_to_id[class_name]

    df = fetch_timetable_df(dept_id, class_id)
    st.dataframe(df, use_container_width=True)

    # Download as Excel
    excel_bytes = to_excel_bytes(df, dept_name, class_name)
    st.download_button(
        "Download Excel (.xlsx)",
        data=excel_bytes,
        file_name=f"{COLLEGE_NAME}_{dept_name}_{class_name}_timetable.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def hod_dashboard(hod_info):
    st.title(f"🛠️ HOD Dashboard — {hod_info['department_name']} ({COLLEGE_NAME})")

    finalized = hod_info["is_finalized"]
    status = "🔒 Finalized (read-only)" if finalized else "🟢 Editable"
    st.subheader(f"Status: {status}")

    cols = st.columns(3)
    with cols[0]:
        if finalized:
            if st.button("Unlock for Editing"):
                run_exec(
                    "UPDATE departments SET is_finalized=0, updated_at=? WHERE id=?",
                    (datetime.utcnow().isoformat(), hod_info["department_id"]),
                )
                st.rerun()
        else:
            if st.button("Finalize / Lock Timetable"):
                run_exec(
                    "UPDATE departments SET is_finalized=1, updated_at=? WHERE id=?",
                    (datetime.utcnow().isoformat(), hod_info["department_id"]),
                )
                st.rerun()

    st.divider()

    st.header("Masters")
    tab_classes, tab_teachers, tab_subjects, tab_rooms = st.tabs(
        ["Classes", "Teachers", "Subjects", "Rooms"]
    )

    disabled = finalized

    with tab_classes:
        st.subheader("Add Class/Section")
        cname = st.text_input(
            "Class name (e.g., CSE-2A)", key=f"cname_{hod_info['department_id']}"
        )
        if st.button("Add Class", disabled=disabled) and cname.strip():
            try:
                run_exec(
                    "INSERT INTO classes(department_id, name) VALUES(?, ?)",
                    (hod_info["department_id"], cname.strip()),
                )
                st.success("Added.")
            except sqlite3.IntegrityError:
                st.warning("Class already exists.")

        with st.expander("Existing Classes", expanded=True):
            rows = get_classes(hod_info["department_id"]) or []
            st.table(pd.DataFrame(rows, columns=["ID", "Name"]))

    with tab_teachers:
        st.subheader("Add Teacher")
        tname = st.text_input("Teacher name", key=f"tname_{hod_info['department_id']}")
        tcode = st.text_input(
            "Short code (optional)", key=f"tcode_{hod_info['department_id']}"
        )
        if st.button("Add Teacher", disabled=disabled) and tname.strip():
            try:
                run_exec(
                    "INSERT INTO teachers(department_id, name, short_code) VALUES(?,?,?)",
                    (hod_info["department_id"], tname.strip(), tcode.strip()),
                )
                st.success("Added.")
            except sqlite3.IntegrityError:
                st.warning("Teacher already exists.")

        with st.expander("Existing Teachers", expanded=True):
            rows = get_teachers(hod_info["department_id"]) or []
            st.table(pd.DataFrame(rows, columns=["ID", "Name"]))

    with tab_subjects:
        st.subheader("Add Subject")
        scode = st.text_input(
            "Subject code (optional)", key=f"scode_{hod_info['department_id']}"
        )
        sname = st.text_input("Subject name", key=f"sname_{hod_info['department_id']}")
        if st.button("Add Subject", disabled=disabled) and sname.strip():
            try:
                run_exec(
                    "INSERT INTO subjects(department_id, code, name) VALUES(?,?,?)",
                    (hod_info["department_id"], scode.strip(), sname.strip()),
                )
                st.success("Added.")
            except sqlite3.IntegrityError:
                st.warning("Subject already exists.")

        with st.expander("Existing Subjects", expanded=True):
            rows = run_query(
                "SELECT id, COALESCE(code,'') as code, name FROM subjects WHERE department_id=? ORDER BY name",
                (hod_info["department_id"],),
            )
            st.table(pd.DataFrame(rows, columns=["ID", "Code", "Name"]))

    with tab_rooms:
        st.subheader("Add Room (shared across departments)")
        rname = st.text_input(
            "Room name (e.g., FF01)", key=f"rname_{hod_info['department_id']}"
        )
        rcap = st.number_input(
            "Capacity (optional)",
            min_value=0,
            step=1,
            key=f"rcap_{hod_info['department_id']}",
        )
        if st.button("Add Room", disabled=disabled) and rname.strip():
            try:
                run_exec(
                    "INSERT INTO rooms(name, capacity) VALUES(?, ?)",
                    (rname.strip(), int(rcap) if rcap else None),
                )
                st.success("Added.")
            except sqlite3.IntegrityError:
                st.warning("Room already exists.")

        with st.expander("Existing Rooms", expanded=True):
            rows = run_query("SELECT id, name, capacity FROM rooms ORDER BY name") or []
            st.table(pd.DataFrame(rows, columns=["ID", "Name", "Capacity"]))

    st.divider()

    st.header("Arrange Timetable")

    classes = get_classes(hod_info["department_id"]) or []
    if not classes:
        st.info("Add at least one Class in Masters → Classes.")
        return

    class_name_map = {name: cid for cid, name in classes}
    class_name = st.selectbox(
        "Class/Section",
        [name for _, name in classes],
        key=f"selclass_{hod_info['department_id']}",
    )
    class_id = class_name_map[class_name]

    day_label_map = {label: d for d, label in DAYS}
    period_label_map = {label: p for p, label in PERIODS}

    day_label = st.selectbox(
        "Day", [label for _, label in DAYS], key=f"day_{hod_info['department_id']}"
    )
    period_label = st.selectbox(
        "Period",
        [label for _, label in PERIODS],
        key=f"period_{hod_info['department_id']}",
    )

    subjects = get_subjects(hod_info["department_id"]) or []
    teachers = get_teachers(hod_info["department_id"]) or []
    rooms = get_rooms() or []

    subject_map = {name: sid for sid, name in subjects}
    teacher_map = {name: tid for tid, name in teachers}
    room_map = {name: rid for rid, name in rooms}

    subject_name = (
        st.selectbox(
            "Subject",
            list(subject_map.keys()) if subject_map else ["— None —"],
            key=f"sub_{hod_info['department_id']}",
        )
        if subjects
        else None
    )
    teacher_name = (
        st.selectbox(
            "Teacher",
            list(teacher_map.keys()) if teacher_map else ["— None —"],
            key=f"teach_{hod_info['department_id']}",
        )
        if teachers
        else None
    )
    room_name = (
        st.selectbox(
            "Room",
            list(room_map.keys()) if room_map else ["— None —"],
            key=f"room_{hod_info['department_id']}",
        )
        if rooms
        else None
    )

    note = st.text_input("Note (optional)", key=f"note_{hod_info['department_id']}")

    colA, colB = st.columns(2)
    with colA:
        if st.button(
            "Save Slot",
            disabled=disabled or not (subjects and teachers and rooms),
            key=f"save_{hod_info['department_id']}",
        ):
            upsert_timetable(
                hod_info["department_id"],
                class_id,
                day_label_map[day_label],
                period_label_map[period_label],
                subject_map.get(subject_name),
                teacher_map.get(teacher_name),
                room_map.get(room_name),
                note.strip(),
            )
            st.success("Saved.")
    with colB:
        if st.button(
            "Clear Slot", disabled=disabled, key=f"clear_{hod_info['department_id']}"
        ):
            clear_slot(
                hod_info["department_id"],
                class_id,
                day_label_map[day_label],
                period_label_map[period_label],
            )
            st.warning("Cleared.")

    st.subheader("Preview for Selected Class")
    df = fetch_timetable_df(hod_info["department_id"], class_id)
    st.dataframe(df, use_container_width=True)

    # Excel export in HOD dashboard as well
    excel_bytes = to_excel_bytes(df, hod_info["department_name"], class_name)
    st.download_button(
        "Download Excel (.xlsx)",
        data=excel_bytes,
        file_name=f"{COLLEGE_NAME}_{hod_info['department_name']}_{class_name}_timetable.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.caption(
        "Tip: Use the Public Timetable page for a read-only view and CSV/Excel export."
    )


# -------------------------------
# App Entry
# -------------------------------


def main():
    st.set_page_config(page_title="Lecture Arrangement Portal", layout="wide")
    init_db()

    st.sidebar.title(f"{COLLEGE_NAME} Portal Navigation")
    page = st.sidebar.radio("Go to", ["Public Timetable", "HOD Login"], index=0)

    if page == "Public Timetable":
        public_view()
        return

    st.title("🔐 Departmental Login (HOD)")

    with st.form("login_form"):
        username = st.text_input("HOD Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        info = auth_hod(username, password)
        if info:
            st.session_state["hod_info"] = info
            st.success(f"Welcome, {info['department_name']} HOD!")
        else:
            st.error("Invalid credentials.")

    hod_info = st.session_state.get("hod_info")
    if hod_info:
        dept = run_query(
            "SELECT is_finalized FROM departments WHERE id=?",
            (hod_info["department_id"],),
        )
        if dept:
            hod_info["is_finalized"] = bool(dept[0][0])
        hod_dashboard(hod_info)


if __name__ == "__main__":
    main()
