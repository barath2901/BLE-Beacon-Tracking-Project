import socket
import asyncio
from bleak import BleakScanner

SERVER_IP = "127.0.0.1" # CHANGE THIS TO YOUR SERVER IP
PORT = 12000

async def start_client():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((SERVER_IP, PORT))
        print("✅ Connected to Server")

        # Receive the allowed ID list
        raw_ids = s.recv(1024).decode()
        allowed_ids = [int(x) for x in raw_ids.split(",")]
        print(f"Tracking Students: {allowed_ids}")

        def callback(device, adv):
            if 0x004c in adv.manufacturer_data:
                data = adv.manufacturer_data[0x004c]
                if len(data) >= 23:
                    minor = int.from_bytes(data[20:22], byteorder='big')
                    if minor in allowed_ids:
                        payload = f"{minor},{adv.rssi}"
                        s.sendall(payload.encode())
                        print(f"📤 Sent: Student {minor} (RSSI: {adv.rssi})")

        async with BleakScanner(callback):
            while True:
                await asyncio.sleep(1)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(start_client())
