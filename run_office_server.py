# run_office_server.py
import os
import sys
import socket
from waitress import serve
from sms_core.wsgi import application

def get_local_ip():
    """Dynamically fetches the server computer's local area network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    # Ensure Django can locate your environment paths
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    local_ip = get_local_ip()
    port = 8000
    
    print("=" * 60)
    print("        Kabiero ACADEMY - PRODUCTION OFFICE SERVER")
    print("=" * 60)
    print(f" Status:       ACTIVE & RUNNING")
    print(f" Engine:       Waitress WSGI Production Gateway")
    print(f" Host IP:      {local_ip}")
    print(f" Port:         {port}")
    print("-" * 60)
    print(f" LAN Access URL for Office Laptops:")
    print(f" >>> http://{local_ip}:{port}/")
    print("=" * 60)
    print(" Keep this terminal open. Closing it will turn off the system.")
    print(" Logging background traffic profiles below...")
    print("-" * 60)

    # Launch production server binding to all network interfaces
    serve(application, host="0.0.0.0", port=port, threads=6)
