import socket
import asyncio
from bleak import BleakScanner

# --- CONFIGURATION (EDIT THIS FOR EACH LAPTOP) ---
SERVER_IP = "10.242.183.173"   # <--- REPLACE 'X' WITH LAPTOP 1's ACTUAL IP
SERVER_PORT = 12000
NODE_NAME = "Client_Node_1" # <--- Change to "Node_2", "Node_3", etc.

async def run_client():
    print(f"📡 Starting {NODE_NAME}...")
    try:
        # 1. Connect to Server
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((SERVER_IP, SERVER_PORT))
        
        # 2. Send our Name to Server
        s.sendall(NODE_NAME.encode())
        print(f"✅ Connected to Server at {SERVER_IP}")
        
        # 3. Receive Allowed IDs
        raw_ids = s.recv(1024).decode()
        allowed_ids = [int(x) for x in raw_ids.split(",")]
        print(f"🎯 Tracking IDs: {allowed_ids}")

        # 4. Scanning Logic
        def callback(device, adv):
            if 0x004c in adv.manufacturer_data:
                data = adv.manufacturer_data[0x004c]
                if len(data) >= 23:
                    minor = int.from_bytes(data[20:22], byteorder='big')
                    rssi = adv.rssi
                    
                    if minor in allowed_ids:
                        # Send data: "ID,RSSI"
                        msg = f"{minor},{rssi}"
                        s.sendall(msg.encode())
                        print(f"📤 Sent: Student {minor} (Signal: {rssi})")

        async with BleakScanner(callback):
            print("🔍 Scanning for Beacons...")
            while True:
                await asyncio.sleep(1)

    except ConnectionRefusedError:
        print("❌ Error: Server not found! Check IP address or Firewall.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_client())
