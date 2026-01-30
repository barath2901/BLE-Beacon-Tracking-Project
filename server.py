import socket
import threading
import sqlite3
import os
from flask import Flask, render_template
from datetime import datetime
import logging

# --- CONFIGURATION ---
HOST = "0.0.0.0"       # Open to the entire network
SOCKET_PORT = 12000    # Port for Laptops 2-5 to connect
WEB_PORT = 5000        # Port for the Website
DB_NAME = "college_erp.db"

# Student Data (ID mapped to Name)
STUDENT_LIST = {
    101: "Barath", 102: "Hariharan", 103: "Alagar", 104: "Ajay",
    105: "Krishnan", 108: "Dhanamalini", 109: "Anupriya", 110: "Arun"
}

app = Flask(__name__)
# Reduce terminal clutter
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Students Table
    c.execute('CREATE TABLE IF NOT EXISTS Students (student_id INTEGER PRIMARY KEY, name TEXT)')
    
    # 2. Attendance Log (Tracks every single detection)
    c.execute('''CREATE TABLE IF NOT EXISTS Attendance_Log 
                 (log_id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  student_id INTEGER, 
                  period_num INTEGER, 
                  rssi INTEGER, 
                  node_name TEXT, 
                  timestamp DATETIME)''')
    
    # 3. Marks Table (Student Essentials)
    c.execute('''CREATE TABLE IF NOT EXISTS Marks 
                 (student_id INTEGER PRIMARY KEY, internal_marks INTEGER, attendance_pct INTEGER)''')

    # Populate Data
    for sid, name in STUDENT_LIST.items():
        c.execute("INSERT OR IGNORE INTO Students VALUES (?,?)", (sid, name))
        # Default Dummy Marks: 18/20 and 85% attendance
        c.execute("INSERT OR IGNORE INTO Marks VALUES (?,?,?)", (sid, 18, 85))
        
    conn.commit()
    conn.close()
    print(f"✅ Server Database Ready. Listening on {HOST}:{SOCKET_PORT}")

# --- LOGIC TO SAVE DATA ---
def log_to_db(sid, rssi, node_name):
    # Auto-detect Period (1 = Before 10 AM, 2 = After)
    period = 1 if datetime.now().hour < 10 else 2
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check if this student was already logged for THIS period TODAY
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT * FROM Attendance_Log WHERE student_id=? AND period_num=? AND date(timestamp)=?", 
              (sid, period, today))
    
    # If not logged yet today, insert the record
    if not c.fetchone():
        c.execute("INSERT INTO Attendance_Log (student_id, period_num, rssi, node_name, timestamp) VALUES (?,?,?,?,?)",
                  (sid, period, rssi, node_name, datetime.now()))
        conn.commit()
        print(f"💾 Logged: {STUDENT_LIST[sid]} detected by {node_name}")
    
    conn.close()

# --- SOCKET LISTENER (Handles Laptops 2-5) ---
def handle_client(client_socket, addr):
    try:
        # 1. First, receive the Node Name (e.g., "Front_Gate")
        node_name = client_socket.recv(1024).decode()
        print(f"🔗 Connected: {node_name} ({addr[0]})")
        
        # 2. Send the allowed IDs to the client
        id_list = ",".join(str(x) for x in STUDENT_LIST.keys())
        client_socket.sendall(id_list.encode())

        # 3. Listen for scans
        while True:
            data = client_socket.recv(1024).decode()
            if not data: break
            
            # Format: "minor_id,rssi"
            parts = data.split(",")
            if len(parts) == 2:
                log_to_db(int(parts[0]), int(parts[1]), node_name)
                
    except Exception as e:
        print(f"❌ Connection Error with {addr}: {e}")
    finally:
        client_socket.close()

def start_socket_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, SOCKET_PORT))
    server.listen(5) # Allow up to 5 laptops
    while True:
        client, addr = server.accept()
        threading.Thread(target=handle_client, args=(client, addr), daemon=True).start()

# --- WEBSITE DASHBOARD ---
@app.route('/')
def dashboard():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Get Students + Today's Attendance + Marks
    c.execute('''
        SELECT s.student_id, s.name, a.timestamp, a.node_name, m.internal_marks 
        FROM Students s
        LEFT JOIN Attendance_Log a ON s.student_id = a.student_id AND date(a.timestamp) = date('now')
        LEFT JOIN Marks m ON s.student_id = m.student_id
        GROUP BY s.student_id
    ''')
    data = c.fetchall()
    conn.close()
    return render_template('index.html', attendance=data)

if __name__ == "__main__":
    init_db()
    # Run Socket Server in background
    threading.Thread(target=start_socket_server, daemon=True).start()
    # Run Website
    print(f"🌐 Dashboard Live at http://localhost:{WEB_PORT}")
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)
