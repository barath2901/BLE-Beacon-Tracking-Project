import socket
import asyncio
from datetime import datetime
from bleak import BleakScanner

# --- EDIT THIS FOR EACH LAPTOP ---
SERVER_IP = "10.242.183.173"   # <--- REPLACE WITH LAPTOP 1 IP
SERVER_PORT = 12000
NODE_NAME = "Classroom"     # <--- Change this (e.g., 'Library')

async def run_client():
    print(f"📡 Starting Scanner Node: {NODE_NAME}")
    print(f"🎯 Connecting to Server at {SERVER_IP}...")
    
    s = None
    try:
        # 1. Connect to Server
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(15) # Wait 15 seconds for connection
        s.connect((SERVER_IP, SERVER_PORT))
        s.settimeout(None) # Reset timeout for normal operation
        
        # 2. Send our Location Name
        s.sendall(NODE_NAME.encode()) 
        
        # 3. Receive Student List
        raw_ids = s.recv(4096).decode()
        if not raw_ids:
            print("❌ Error: Server sent empty student list.")
            return

        allowed_ids = [int(x) for x in raw_ids.split(",")]
        print(f"✅ Connected! Tracking {len(allowed_ids)} students.")

        # 4. Scanning Loop
        def callback(device, adv):
            if 0x004c in adv.manufacturer_data:
                data = adv.manufacturer_data[0x004c]
                if len(data) >= 23:
                    minor = int.from_bytes(data[20:22], byteorder='big')
                    if minor in allowed_ids:
                        try:
                            s.sendall(f"{minor},{adv.rssi}".encode())
                            print(f"\r✨ Live: Detected {minor} (Signal: {adv.rssi})   ", end="")
                        except: pass

        print("🔍 Scanning started... (Press Ctrl+C to stop)")
        async with BleakScanner(callback):
            while True:
                # Auto-Stop at 4:45 PM
                now = datetime.now()
                if now.hour >= 16 and now.minute >= 45:
                    print("\n🌙 Day Over. Stopping Scanner.")
                    break
                await asyncio.sleep(1)

    except TimeoutError:
        print(f"\n❌ Timeout: Could not find Server at {SERVER_IP}.")
        print("   -> Check if IP is correct.")
        print("   -> Check if Server Firewall is allowing Port 12000.")
    except ConnectionRefusedError:
        print(f"\n❌ Refused: Server rejected connection.")
        print("   -> Is server.py running?")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        if s: s.close()
        input("\n🔌 Disconnected. Press Enter to exit...")

if __name__ == "__main__":
    try:
        asyncio.run(run_client())
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
