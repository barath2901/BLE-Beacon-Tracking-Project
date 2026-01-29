import socket
import threading
import sqlite3
import os
from flask import Flask, render_template
from datetime import datetime
import logging

# --- CONFIGURATION ---
HOST = "0.0.0.0"
SOCKET_PORT = 12000
WEB_PORT = 5000
DB_NAME = "college_erp.db"

# Master list of students
STUDENT_LIST = {
    101: "Barath", 102: "Hariharan", 103: "Suresh", 104: "Ajay",
    105: "Krishnan", 108: "Ramesh", 109: "Vignesh", 110: "Karthik"
}

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- 1. DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Create Tables
    c.execute('CREATE TABLE IF NOT EXISTS Students (student_id INTEGER PRIMARY KEY, name TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS Attendance_Log 
                 (log_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, 
                  period_num INTEGER, rssi INTEGER, client_ip TEXT, timestamp DATETIME)''')
    # Extra Essentials: Marks Table
    c.execute('''CREATE TABLE IF NOT EXISTS Marks 
                 (student_id INTEGER PRIMARY KEY, internal_marks INTEGER, attendance_pct INTEGER)''')
    
    # Insert students and dummy marks
    for sid, name in STUDENT_LIST.items():
        c.execute("INSERT OR IGNORE INTO Students VALUES (?,?)", (sid, name))
        # Adding dummy marks: 18/20 internals and 90% attendance for everyone initially
        c.execute("INSERT OR IGNORE INTO Marks VALUES (?,?,?)", (sid, 18, 90))
        
    conn.commit()
    conn.close()
    print("✅ Database & Marks Initialized.")

def log_to_db(sid, rssi, client_ip):
    # Determine Period: 1 (Morning), 2 (Afternoon)
    hour = datetime.now().hour
    period = 1 if hour < 12 else 2
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Only insert if no log exists for this student in this period TODAY
    c.execute("SELECT * FROM Attendance_Log WHERE student_id=? AND period_num=? AND date(timestamp)=?", 
              (sid, period, today))
    if not c.fetchone():
        c.execute("INSERT INTO Attendance_Log (student_id, period_num, rssi, client_ip, timestamp) VALUES (?,?,?,?,?)",
                  (sid, period, rssi, client_ip, datetime.now()))
        conn.commit()
    conn.close()

# --- 2. SOCKET SERVER LOGIC ---
def handle_socket_client(client, addr):
    client_ip = addr[0]
    try:
        id_string = ",".join(str(i) for i in STUDENT_LIST.keys())
        client.sendall(id_string.encode())
        while True:
            data = client.recv(1024).decode()
            if not data: break
            parts = data.split(",")
            if len(parts) == 2:
                minor, rssi = int(parts[0]), int(parts[1])
                if minor in STUDENT_LIST:
                    log_to_db(minor, rssi, client_ip)
    except: pass
    finally: client.close()

def start_socket_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, SOCKET_PORT))
    s.listen()
    print(f"📡 Socket Server listening on port {SOCKET_PORT}")
    while True:
        client, addr = s.accept()
        threading.Thread(target=handle_socket_client, args=(client, addr), daemon=True).start()

# --- 3. WEB DASHBOARD LOGIC ---
@app.route('/')
def dashboard():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # QUERY: Join Students with TODAY's Attendance and their Marks
    c.execute('''
        SELECT s.student_id, s.name, a.timestamp, a.client_ip, m.internal_marks, m.attendance_pct
        FROM Students s
        LEFT JOIN Attendance_Log a ON s.student_id = a.student_id AND date(a.timestamp) = date('now')
        LEFT JOIN Marks m ON s.student_id = m.student_id
        GROUP BY s.student_id
        ORDER BY s.student_id ASC
    ''')
    rows = c.fetchall()
    conn.close()
    return render_template('index.html', attendance=rows)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=start_socket_server, daemon=True).start()
    print(f"🌐 Website live at http://localhost:{WEB_PORT}")
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)
