import sqlite3
from datetime import datetime

DB_NAME = "college_erp.db"

def initialize_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Create Tables
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS Students (
            student_id INTEGER PRIMARY KEY,
            name TEXT,
            beacon_minor_id INTEGER UNIQUE
        );

        CREATE TABLE IF NOT EXISTS Attendance_Log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            period_num INTEGER,
            status TEXT,
            timestamp DATETIME,
            FOREIGN KEY (student_id) REFERENCES Students(student_id)
        );
    ''')
    
    # 2. Add your specific batchmates
    students = [
        (101, 'Barath', 101), (102, 'Hariharan', 102), (104, 'Ajay', 104),
        (105, 'Krishnan', 105), (108, 'Malini', 108), (109, 'Anupriya', 109),
        (110, 'Arun', 110)
    ]
    cursor.executemany("INSERT OR IGNORE INTO Students VALUES (?,?,?)", students)
    
    conn.commit()
    conn.close()
    print("✅ Database Initialized with Batchmate Details.")

def log_presence(minor_id, period):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Find student_id from minor_id
    cursor.execute("SELECT student_id FROM Students WHERE beacon_minor_id = ?", (minor_id,))
    result = cursor.fetchone()
    
    if result:
        student_id = result[0]
        # Check if already marked for this period today
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT * FROM Attendance_Log WHERE student_id = ? AND period_num = ? AND date(timestamp) = ?", 
                       (student_id, period, today))
        
        if not cursor.fetchone():
            cursor.execute("INSERT INTO Attendance_Log (student_id, period_num, status, timestamp) VALUES (?, ?, ?, ?)",
                           (student_id, period, "PRESENT", datetime.now()))
            conn.commit()
            print(f"💾 Database Updated: Student {student_id} marked Present for Period {period}")
    
    conn.close()

if __name__ == "__main__":
    initialize_db()
