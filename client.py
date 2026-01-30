import socket
import asyncio
from datetime import datetime
from bleak import BleakScanner

# --- EDIT THIS FOR EACH LAPTOP ---
SERVER_IP = "192.168.1.X"   # <--- PUT LAPTOP 1 IP HERE
SERVER_PORT = 12000
NODE_NAME = "Classroom"     # <--- CHANGE TO "Library", "Canteen", etc.

async def run_client():
    print(f"📡 Starting Scanner Node: {NODE_NAME}")
    
    try:
        # Connect to Server
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((SERVER_IP, SERVER_PORT))
        s.sendall(NODE_NAME.encode()) # Identify ourselves
        
        # Get Allowed IDs
        raw_ids = s.recv(1024).decode()
        allowed_ids = [int(x) for x in raw_ids.split(",")]
        print(f"✅ Connected! Tracking {len(allowed_ids)} students.")

        def callback(device, adv):
            if 0x004c in adv.manufacturer_data:
                data = adv.manufacturer_data[0x004c]
                if len(data) >= 23:
                    minor = int.from_bytes(data[20:22], byteorder='big')
                    if minor in allowed_ids:
                        # Send Data
                        s.sendall(f"{minor},{adv.rssi}".encode())
                        # Clean Print (Overwrites the same line)
                        print(f"\r✨ Live: Detected {minor} (Signal: {adv.rssi})   ", end="")

        print("🔍 Scanning started (Ctrl+C to stop)...")
        async with BleakScanner(callback):
            while True:
                # Auto-Stop at 4:45 PM to save battery
                now = datetime.now()
                if now.hour >= 16 and now.minute >= 45:
                    print("\n🌙 Day Over. Stopping Scanner.")
                    break
                await asyncio.sleep(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    asyncio.run(run_client())
