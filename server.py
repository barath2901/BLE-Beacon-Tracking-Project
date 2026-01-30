import socket
import threading
import sqlite3
import time
import os
from flask import Flask, render_template
from datetime import datetime
import logging

# --- CONFIGURATION ---
HOST = "0.0.0.0"       # Listen on all IPs
SOCKET_PORT = 12000    # Port for Client Laptops
WEB_PORT = 5000        # Port for Dashboard
DB_NAME = "college_erp.db"

# Safe Zones: Students here are "PRESENT". Anywhere else is "Bunking".
SAFE_ZONES = ["Classroom", "Library", "Staff Room", "Lab 1", "Seminar Hall"]

# TIMETABLE (Exact Match to your Image)
# Format: (StartHour, StartMin, EndHour, EndMin, "SubjectName")
TIMETABLE = {
    "Monday": [
        (9, 10, 10, 0, "CCW332 - Digital Marketing"),
        (10, 0, 10, 50, "CCS365 - Software Defined Networks"),
        # 10:50-11:05 is TEA BREAK
        (11, 5, 11, 55, "CCS345 - Ethics and AI"),
        (11, 55, 12, 45, "CCS345 - Ethics and AI"),
        # 12:45-13:30 is LUNCH
        (13, 30, 14, 15, "OCE351 - Env. Impact Assessment"),
        (14, 15, 15, 0, "CS3691 - Embedded Systems"),
        # 15:00-15:10 is TEA BREAK
        (15, 10, 15, 55, "CCS356 - OOSE"),
        (15, 55, 16, 40, "LIB - Library")
    ],
    "Friday": [
        (9, 10, 10, 0, "CCS356 - OOSE"),
        (10, 0, 10, 50, "CS3691 - Embedded Systems"),
        (11, 5, 11, 55, "CCS365 - SDN Laboratory"),
        (11, 55, 12, 45, "CCS365 - SDN Laboratory"),
        (13, 30, 14, 15, "ASS - Association"),
        (14, 15, 15, 0, "OCE351 - Env. Impact Assessment"),
        (15, 10, 15, 55, "CCW332 - Digital Marketing"),
        (15, 55, 16, 40, "MX3089 - Industrial Safety")
    ]
    # Add Tuesday, Wednesday, Thursday similarly if needed
}

# Student Batch List
STUDENT_LIST = {
    101: "Barath", 102: "Hariharan", 103: "Suresh", 104: "Ajay",
    105: "Krishnan", 108: "Ramesh", 109: "Vignesh", 110: "Karthik"
}

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR) # Hide flask logs

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Live Logs (Wiped every hour)
    c.execute('''CREATE TABLE IF NOT EXISTS Live_Logs 
                 (student_id INTEGER PRIMARY KEY, node_name TEXT, last_seen DATETIME)''')

    # 2. Permanent History (Saved forever)
    c.execute('''CREATE TABLE IF NOT EXISTS Permanent_History 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, 
                  date DATE, subject TEXT, status TEXT, location_found TEXT)''')
                  
    conn.commit()
    conn.close()
    print("✅ Database Initialized with Smart Cleaning Architecture.")

def wipe_live_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM Live_Logs")
    conn.commit()
    conn.close()

def log_live_location(sid, node_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("REPLACE INTO Live_Logs (student_id, node_name, last_seen) VALUES (?, ?, ?)",
              (sid, node_name, datetime.now()))
    conn.commit()
    conn.close()

# --- SMART LOGIC: TIME & ATTENDANCE ---
def get_current_status():
    now = datetime.now()
    current_min = now.hour * 60 + now.minute
    day_name = now.strftime("%A")

    # AUTO-SHUTDOWN at 4:40 PM (16:40 = 1000 mins)
    if current_min >= 1000:
        return "CLOSED", "College Closed"

    # CHECK CLASS SCHEDULE
    if day_name in TIMETABLE:
        for start_h, start_m, end_h, end_m, subject in TIMETABLE[day_name]:
            s_min = start_h * 60 + start_m
            e_min = end_h * 60 + end_m
            if s_min <= current_min < e_min:
                return "CLASS", subject

    # CHECK BREAKS
    if (650 <= current_min < 665): return "BREAK", "Tea Break"     # 10:50-11:05
    if (765 <= current_min < 810): return "BREAK", "Lunch Break"   # 12:45-01:30
    if (900 <= current_min < 910): return "BREAK", "Tea Break"     # 15:00-15:10

    return "FREE", "Free Period"

def generate_summary(subject_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    print(f"\n📝 GENERATING SUMMARY FOR: {subject_name}")
    
    # Get all students currently detected
    c.execute("SELECT student_id, node_name FROM Live_Logs")
    detected = {row[0]: row[1] for row in c.fetchall()}
    
    for sid, name in STUDENT_LIST.items():
        location = detected.get(sid, "Not Found")
        
        if sid in detected:
            if location in SAFE_ZONES:
                status = "PRESENT"
            else:
                status = "ABSENT (Bunking)" # Detected, but in Canteen/Gate
        else:
            status = "ABSENT"

        # Save to History
        c.execute("INSERT INTO Permanent_History (student_id, date, subject, status, location_found) VALUES (?,?,?,?,?)",
                  (sid, today, subject_name, status, location))
        print(f" > {name}: {status} [{location}]")
        
    conn.commit()
    conn.close()

def period_monitor():
    last_status, last_subject = get_current_status()
    print(f"🕒 Monitor Started. Current: {last_subject}")
    
    while True:
        time.sleep(30) # Check status every 30 seconds
        current_status, current_subject = get_current_status()
        
        if current_status == "CLOSED":
            print("\n🌙 4:40 PM Reached. Saving & Shutting Down.")
            wipe_live_db()
            os._exit(0) # Stop Server

        if current_subject != last_subject:
            print(f"\n🔔 STATUS CHANGE: {last_subject} -> {current_subject}")
            
            # If a class just finished, save attendance
            if last_status == "CLASS":
                generate_summary(last_subject)
                wipe_live_db()
                print("✅ Data Saved & Live Table Wiped.")
            
            # If a break just finished, clear 'Canteen' logs
            elif last_status == "BREAK":
                wipe_live_db()
                print("✅ Break Over. Cleared Canteen Logs.")

            last_status = current_status
            last_subject = current_subject

# --- SOCKET SERVER ---
def handle_client(client, addr):
    try:
        node_name = client.recv(1024).decode()
        # Send ID list to client
        client.sendall(",".join(str(x) for x in STUDENT_LIST.keys()).encode())
        while True:
            data = client.recv(1024).decode()
            if not data: break
            parts = data.split(",")
            if len(parts) == 2:
                log_live_location(int(parts[0]), node_name)
    except: pass
    finally: client.close()

def start_socket_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, SOCKET_PORT))
    s.listen()
    print(f"📡 Socket Server Listening on Port {SOCKET_PORT}")
    while True:
        client, addr = s.accept()
        threading.Thread(target=handle_client, args=(client, addr), daemon=True).start()

# --- DASHBOARD ---
@app.route('/')
def dashboard():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT student_id, node_name, last_seen FROM Live_Logs")
    live_data = {row[0]: (row[1], row[2]) for row in c.fetchall()}
    conn.close()
    
    status, subject = get_current_status()
    
    rows = []
    for sid, name in STUDENT_LIST.items():
        if sid in live_data:
            node, last_seen = live_data[sid]
            # Live Status Logic for Website
            s_text = "PRESENT" if node in SAFE_ZONES else "WARNING (Wrong Loc)"
        else:
            node, last_seen, s_text = "-", "-", "ABSENT"
        rows.append((sid, name, s_text, node, last_seen))
        
    return render_template('index.html', attendance=rows, subject=subject, status=status)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=start_socket_server, daemon=True).start()
    threading.Thread(target=period_monitor, daemon=True).start()
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)
