import socket
import os
import platform
import time
from datetime import datetime

START_TIME = time.time()

def get_server_network_interfaces():
    """
    Detect real network interface IPv4 addresses using standard Python socket APIs.
    Discovers:
    - Loopback address (127.0.0.1)
    - Primary LAN IPv4 address (e.g. 192.168.x.x or 10.x.x.x)
    - Hostname
    """
    hostname = socket.gethostname()
    lan_ip = "127.0.0.1"
    all_ips = ["127.0.0.1"]
    
    # Attempt outbound UDP connect trick to find primary routing IP (does not send packets)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # 192.0.2.1 is TEST-NET-1 (RFC 5737); routing table indicates primary outbound adapter
        s.connect(('192.0.2.1', 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        # Fallback to gethostbyname
        try:
            lan_ip = socket.gethostbyname(hostname)
        except Exception:
            lan_ip = "127.0.0.1"

    try:
        _, _, ip_list = socket.gethostbyname_ex(hostname)
        for ip in ip_list:
            if ip not in all_ips and not ip.startswith("127."):
                all_ips.append(ip)
    except Exception:
        pass

    if lan_ip not in all_ips:
        all_ips.append(lan_ip)

    return {
        "hostname": hostname,
        "primary_lan_ip": lan_ip,
        "detected_ips": all_ips,
        "platform": platform.platform(),
        "python_version": platform.python_version()
    }

def get_application_health(db, port=5000):
    """
    Check application health, database connectivity, and calculate uptime.
    """
    uptime_seconds = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

    db_status = "HEALTHY"
    db_latency_ms = 0.0
    try:
        t0 = time.perf_counter()
        db.execute("SELECT 1").fetchone()
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    except Exception as e:
        db_status = f"ERROR: {e}"

    network_info = get_server_network_interfaces()

    return {
        "status": "ONLINE" if db_status == "HEALTHY" else "DEGRADED",
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
        "server_port": port,
        "database_status": db_status,
        "database_latency_ms": db_latency_ms,
        "network_info": network_info
    }

def get_recent_event_logs(db, limit=50):
    """
    Retrieve application & networking event logs stored in database.
    Distinguishes application-level events from raw packet captures.
    """
    rows = db.execute(
        "SELECT * FROM network_event_logs ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]

def get_event_statistics(db):
    """
    Summarize event counts by type and HTTP status.
    """
    rows = db.execute(
        "SELECT event_type, COUNT(*) as count FROM network_event_logs GROUP BY event_type"
    ).fetchall()
    
    summary = {r['event_type']: r['count'] for r in rows}
    
    # Count 2xx, 4xx, 5xx
    status_rows = db.execute(
        "SELECT status_code, COUNT(*) as count FROM network_event_logs WHERE status_code IS NOT NULL GROUP BY status_code"
    ).fetchall()
    status_summary = {str(r['status_code']): r['count'] for r in status_rows}

    return {
        "event_summary": summary,
        "status_summary": status_summary
    }
