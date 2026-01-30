import socket
import threading
import sqlite3
import time
import os
import csv
from flask import Flask, render_template, send_from_directory
from datetime import datetime
import logging

# --- CONFIGURATION ---
HOST = "0.0.0.0"       # Listen on all network interfaces
SOCKET_PORT = 12000    # Port for Clients to connect
WEB_PORT = 5000        # Port for the Website
DB_NAME = "college_erp.db"
CSV_FOLDER = "attendance_reports"
STUDENT_FILE = "students.csv"
TIMETABLE_FILE = "timetable.csv"

# Ensure CSV folder exists
if not os.path.exists(CSV_FOLDER):
    os.makedirs(CSV_FOLDER)

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # Reduce terminal clutter

# --- LOAD DATA (Fixed for Excel CSVs) ---
def load_students_from_csv():
    students = {}
    if os.path.exists(STUDENT_FILE):
        try:
            # FIX: encoding='utf-8-sig' removes the invisible BOM character from Excel
            with open(STUDENT_FILE, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                # Clean header names (remove accidental spaces)
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
                
                for row in reader:
                    if row['id'] and row['name']:
                        try:
                            s_id = int(row['id'].strip())
                            s_name = row['name'].strip()
                            students[s_id] = s_name
                        except ValueError:
                            continue # Skip rows with bad IDs
            print(f"✅ Loaded {len(students)} students from {STUDENT_FILE}")
        except Exception as e:
            print(f"❌ Error loading {STUDENT_FILE}: {e}")
    else:
        print(f"⚠️ Warning: {STUDENT_FILE} not found. Create it with 'id,name' columns.")
    return students

# Load students once at startup
STUDENT_LIST = load_students_from_csv()

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Timetable Table
    c.execute('''CREATE TABLE IF NOT EXISTS Timetable 
                 (day TEXT, start_h INTEGER, start_m INTEGER, 
                  end_h INTEGER, end_m INTEGER, subject TEXT)''')

    # 2. Live Logs (Temporary)
    c.execute('''CREATE TABLE IF NOT EXISTS Live_Logs 
                 (student_id INTEGER PRIMARY KEY, node_name TEXT, last_seen DATETIME)''')

    # 3. History (Permanent)
    c.execute('''CREATE TABLE IF NOT EXISTS Permanent_History 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, 
                  date DATE, subject TEXT, status TEXT, location_found TEXT)''')
    
    # Load Timetable from CSV
    if os.path.exists(TIMETABLE_FILE):
        c.execute("DELETE FROM Timetable") # Clear old data
        try:
            with open(TIMETABLE_FILE, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
                count = 0
                for row in reader:
                    day = row['Day'].strip()
                    sub = row['Subject'].strip()
                    # Parse Time (e.g. "09:10")
                    sh, sm = map(int, row['Start_Time'].split(':'))
                    eh, em = map(int, row['End_Time'].split(':'))
                    
                    c.execute("INSERT INTO Timetable VALUES (?,?,?,?,?,?)", 
                              (day, sh, sm, eh, em, sub))
                    count += 1
            print(f"✅ Loaded {count} periods from {TIMETABLE_FILE}")
        except Exception as e:
            print(f"❌ Error loading {TIMETABLE_FILE}: {e}")
    
    conn.commit()
    conn.close()

def wipe_live_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM Live_Logs")
    conn.commit()
    conn.close()

def log_live_location(sid, node_name):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("REPLACE INTO Live_Logs (student_id, node_name, last_seen) VALUES (?, ?, ?)",
                 (sid, node_name, datetime.now()))
    conn.commit()
    conn.close()

# --- SMART LOGIC ---
SAFE_ZONES = ["Classroom", "Library", "Staff Room", "Lab 1", "Seminar Hall"]

def get_current_status():
    now = datetime.now()
    current_min = now.hour * 60 + now.minute
    day_name = now.strftime("%A")

    # Auto-Shutdown at 4:40 PM (16:40 = 1000 mins)
    if current_min >= 1000:
        return "CLOSED", "College Closed"

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT start_h, start_m, end_h, end_m, subject FROM Timetable WHERE day=?", (day_name,))
    periods = c.fetchall()
    conn.close()

    for sh, sm, eh, em, sub in periods:
        s_min = sh * 60 + sm
        e_min = eh * 60 + em
        if s_min <= current_min < e_min:
            if "BREAK" in sub.upper():
                return "BREAK", sub
            return "CLASS", sub

    return "FREE", "Free Period"

def export_to_csv(subject_name):
    if "BREAK" in subject_name.upper(): return # Don't record attendance for breaks

    today = datetime.now().strftime('%Y-%m-%d_%H-%M')
    filename = f"Attendance_{subject_name.replace(' ', '_')}_{today}.csv"
    filepath = os.path.join(CSV_FOLDER, filename)
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT student_id, node_name FROM Live_Logs")
    present_data = {row[0]: row[1] for row in c.fetchall()}
    
    with open(filepath, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Roll No", "Name", "Subject", "Status", "Location"])
        
        for sid, name in STUDENT_LIST.items():
            loc = present_data.get(sid, "Not Found")
            if sid in present_data:
                status = "PRESENT" if loc in SAFE_ZONES else "ABSENT (Bunking)"
            else:
                status = "ABSENT"
                
            writer.writerow([sid, name, subject_name, status, loc])
            
            # Save to permanent history
            c.execute("INSERT INTO Permanent_History (student_id, date, subject, status, location_found) VALUES (?,?,?,?,?)",
                      (sid, datetime.now().strftime('%Y-%m-%d'), subject_name, status, loc))
    
    conn.commit()
    conn.close()
    print(f"📄 Report Generated: {filename}")

def period_monitor():
    last_status, last_subject = get_current_status()
    print(f"🕒 Monitor Started. Current Status: {last_subject}")
    
    while True:
        time.sleep(10)
        current_status, current_subject = get_current_status()
        
        if current_status == "CLOSED":
            print("\n🌙 4:40 PM Reached. Saving & Shutting Down.")
            wipe_live_db()
            os._exit(0)

        if current_subject != last_subject:
            print(f"\n🔔 CHANGE: {last_subject} -> {current_subject}")
            
            if last_status == "CLASS":
                export_to_csv(last_subject)
                wipe_live_db()
                print("✅ Data Saved & Live Table Wiped.")
            elif last_status == "BREAK":
                wipe_live_db()
                print("✅ Break Over. Ready for class.")

            last_status = current_status
            last_subject = current_subject

# --- SOCKET SERVER ---
def handle_client(client, addr):
    try:
        node_name = client.recv(1024).decode()
        # Send Student IDs to client
        id_string = ",".join(str(x) for x in STUDENT_LIST.keys())
        client.sendall(id_string.encode())
        
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
    # FIX: Allow port reuse to prevent "Address already in use" errors
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, SOCKET_PORT))
    s.listen()
    print(f"📡 Socket Server Listening on Port {SOCKET_PORT}")
    while True:
        client, addr = s.accept()
        threading.Thread(target=handle_client, args=(client, addr), daemon=True).start()

# --- WEB DASHBOARD ---
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
            # Convert datetime string to simpler time format
            try:
                dt_obj = datetime.strptime(str(last_seen).split('.')[0], "%Y-%m-%d %H:%M:%S")
                time_str = dt_obj.strftime("%I:%M:%S %p")
            except: time_str = str(last_seen)

            s_text = "PRESENT" if node in SAFE_ZONES else "WARNING (Bunking)"
        else:
            node, time_str, s_text = "-", "-", "ABSENT"
        rows.append((sid, name, s_text, node, time_str))
        
    return render_template('index.html', attendance=rows, subject=subject, status=status)

@app.route('/download')
def list_reports():
    files = sorted(os.listdir(CSV_FOLDER), reverse=True)
    return render_template('reports.html', files=files)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(CSV_FOLDER, filename)

if __name__ == "__main__":
    try:
        init_db()
        threading.Thread(target=start_socket_server, daemon=True).start()
        threading.Thread(target=period_monitor, daemon=True).start()
        
        print(f"🌐 Dashboard: http://localhost:{WEB_PORT}")
        # use_reloader=False prevents double-execution loops
        app.run(host='0.0.0.0', port=WEB_PORT, debug=True, use_reloader=False)
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        input("Press Enter to Exit...")
