import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "exambot.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER,
            chat_id INTEGER,
            questions_json TEXT,
            exam_type TEXT DEFAULT 'mcq',
            status TEXT DEFAULT 'pending',
            scheduled_at TIMESTAMP,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            duration_minutes INTEGER DEFAULT 10,
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        );

        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            answers_json TEXT DEFAULT '{}',
            score INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 0,
            correct_answers INTEGER DEFAULT 0,
            submitted_at TIMESTAMP,
            time_taken_seconds INTEGER,
            FOREIGN KEY (exam_id) REFERENCES exams(id)
        );

        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            total_exams INTEGER DEFAULT 0,
            total_correct INTEGER DEFAULT 0,
            total_questions_answered INTEGER DEFAULT 0,
            total_score INTEGER DEFAULT 0,
            last_active TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            job_id TEXT,
            scheduled_at TIMESTAMP,
            status TEXT DEFAULT 'pending'
        );
    """)

    conn.commit()
    conn.close()

# ─── Topic Functions ───────────────────────────────────────────────

def save_topic(title, content, created_by):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO topics (title, content, created_by) VALUES (?, ?, ?)",
              (title, content, created_by))
    topic_id = c.lastrowid
    conn.commit()
    conn.close()
    return topic_id

def get_all_topics():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM topics ORDER BY created_at DESC")
    topics = c.fetchall()
    conn.close()
    return topics

def get_topic(topic_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))
    topic = c.fetchone()
    conn.close()
    return topic

def delete_topic(topic_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()

# ─── Exam Functions ─────────────────────────────────────────────────

def create_exam(topic_id, chat_id, questions_json, exam_type, scheduled_at, duration_minutes=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO exams 
                 (topic_id, chat_id, questions_json, exam_type, scheduled_at, duration_minutes)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (topic_id, chat_id, questions_json, exam_type, scheduled_at, duration_minutes))
    exam_id = c.lastrowid
    conn.commit()
    conn.close()
    return exam_id

def get_exam(exam_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
    exam = c.fetchone()
    conn.close()
    return exam

def get_active_exam(chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM exams WHERE chat_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1",
              (chat_id,))
    exam = c.fetchone()
    conn.close()
    return exam

def update_exam_status(exam_id, status):
    conn = get_conn()
    c = conn.cursor()
    if status == 'active':
        c.execute("UPDATE exams SET status = ?, started_at = ? WHERE id = ?",
                  (status, datetime.now(), exam_id))
    elif status == 'ended':
        c.execute("UPDATE exams SET status = ?, ended_at = ? WHERE id = ?",
                  (status, datetime.now(), exam_id))
    else:
        c.execute("UPDATE exams SET status = ? WHERE id = ?", (status, exam_id))
    conn.commit()
    conn.close()

def get_pending_exams():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM exams WHERE status = 'pending' ORDER BY scheduled_at")
    exams = c.fetchall()
    conn.close()
    return exams

# ─── Participant Functions ──────────────────────────────────────────

def save_participant(exam_id, user_id, username, full_name, answers_json,
                     score, total_questions, correct_answers, time_taken):
    conn = get_conn()
    c = conn.cursor()

    # Check if already submitted
    c.execute("SELECT id FROM participants WHERE exam_id = ? AND user_id = ?",
              (exam_id, user_id))
    existing = c.fetchone()
    if existing:
        conn.close()
        return False

    c.execute("""INSERT INTO participants 
                 (exam_id, user_id, username, full_name, answers_json, score,
                  total_questions, correct_answers, submitted_at, time_taken_seconds)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (exam_id, user_id, username, full_name, answers_json,
               score, total_questions, correct_answers, datetime.now(), time_taken))

    conn.commit()
    conn.close()

    # Update global stats
    update_user_stats(user_id, username, full_name, correct_answers, total_questions, score)
    return True

def get_exam_leaderboard(exam_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT full_name, username, score, correct_answers, total_questions,
                        time_taken_seconds, submitted_at
                 FROM participants WHERE exam_id = ?
                 ORDER BY score DESC, time_taken_seconds ASC""", (exam_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_participant(exam_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM participants WHERE exam_id = ? AND user_id = ?",
              (exam_id, user_id))
    row = c.fetchone()
    conn.close()
    return row

# ─── User Stats Functions ───────────────────────────────────────────

def update_user_stats(user_id, username, full_name, correct, total, score):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM user_stats WHERE user_id = ?", (user_id,))
    existing = c.fetchone()
    if existing:
        c.execute("""UPDATE user_stats SET
                     username = ?, full_name = ?,
                     total_exams = total_exams + 1,
                     total_correct = total_correct + ?,
                     total_questions_answered = total_questions_answered + ?,
                     total_score = total_score + ?,
                     last_active = ?
                     WHERE user_id = ?""",
                  (username, full_name, correct, total, score, datetime.now(), user_id))
    else:
        c.execute("""INSERT INTO user_stats 
                     (user_id, username, full_name, total_exams, total_correct,
                      total_questions_answered, total_score, last_active)
                     VALUES (?, ?, ?, 1, ?, ?, ?, ?)""",
                  (user_id, username, full_name, correct, total, score, datetime.now()))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM user_stats WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_weekly_leaderboard():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT p.full_name, p.username, p.user_id,
                        SUM(p.score) as total_score,
                        SUM(p.correct_answers) as total_correct,
                        SUM(p.total_questions) as total_questions,
                        COUNT(DISTINCT p.exam_id) as exams_taken
                 FROM participants p
                 JOIN exams e ON p.exam_id = e.id
                 WHERE e.ended_at >= datetime('now', '-7 days')
                 GROUP BY p.user_id
                 ORDER BY total_score DESC
                 LIMIT 10""")
    rows = c.fetchall()
    conn.close()
    return rows

def get_monthly_leaderboard():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT p.full_name, p.username, p.user_id,
                        SUM(p.score) as total_score,
                        SUM(p.correct_answers) as total_correct,
                        SUM(p.total_questions) as total_questions,
                        COUNT(DISTINCT p.exam_id) as exams_taken
                 FROM participants p
                 JOIN exams e ON p.exam_id = e.id
                 WHERE e.ended_at >= datetime('now', '-30 days')
                 GROUP BY p.user_id
                 ORDER BY total_score DESC
                 LIMIT 10""")
    rows = c.fetchall()
    conn.close()
    return rows

def get_alltime_leaderboard():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT full_name, username, user_id,
                        total_score, total_correct,
                        total_questions_answered, total_exams
                 FROM user_stats
                 ORDER BY total_score DESC
                 LIMIT 10""")
    rows = c.fetchall()
    conn.close()
    return rows

# ─── Admin Functions ─────────────────────────────────────────────────

def is_admin(user_id):
    # Check env-based admin
    admin_ids = os.environ.get("ADMIN_IDS", "")
    if str(user_id) in admin_ids.split(","):
        return True
    # Check DB-based admin
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None

def add_admin(user_id, username):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO admins (user_id, username) VALUES (?, ?)",
              (user_id, username))
    conn.commit()
    conn.close()
