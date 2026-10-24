import os
import sys
from app import create_app
from app.networking.monitoring import get_server_network_interfaces
# CI/CD verification: automated pipeline test
app = create_app()

if __name__ == '__main__':
    interfaces = get_server_network_interfaces()
    port = app.config.get('PORT', 5000)
    host = app.config.get('HOST', '0.0.0.0')

    print("=" * 70)
    print(" ONLINE EXAMINATION NETWORK — SERVER STARTUP")
    print(" Academic Computer Networks Demonstration Project (B.Tech CSE)")
    print("=" * 70)
    print(f" [*] Hostname             : {interfaces['hostname']}")
    print(f" [*] Localhost Access     : http://127.0.0.1:{port}")
    print(f" [*] Primary LAN IP Access: http://{interfaces['primary_lan_ip']}:{port}")
    print(f" [*] Listening Address    : {host}:{port}")
    print(f" [*] Database Path        : {app.config['DATABASE_PATH']}")
    print(f" [*] Detected Interfaces  : {', '.join(interfaces['detected_ips'])}")
    print("-" * 70)
    print(" [!] Multi-Client Access Instructions:")
    print(f"     Student workstations on the same local subnet can connect to:")
    print(f"     http://{interfaces['primary_lan_ip']}:{port}")
    print("     Ensure Windows Defender Firewall allows inbound traffic on TCP port 5000.")
    print("=" * 70)
    
    app.run(host=host, port=port, debug=app.config['DEBUG'])
