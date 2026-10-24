import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash
from config import Config

def seed():
    db_path = Config.DATABASE_PATH
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    print("[*] Seeding demonstration users...")
    demo_users = [
        ("admin", "admin123", "Network Administrator", "admin"),
        ("student1", "pass123", "Alice Sharma (STD-2026-001)", "student"),
        ("student2", "pass123", "Bob Verma (STD-2026-002)", "student"),
        ("student3", "pass123", "Charlie Gupta (STD-2026-003)", "student")
    ]

    for username, password, full_name, role in demo_users:
        existing = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not existing:
            pwd_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                (username, pwd_hash, full_name, role)
            )
            print(f"  [+] Created user: {username} ({role})")
        else:
            print(f"  [-] User '{username}' already exists. Skipping.")

    print("[*] Seeding sample examination...")
    exam_title = "Computer Networks Mid-Term Examination 2026"
    existing_exam = cursor.execute("SELECT id FROM examinations WHERE title = ?", (exam_title,)).fetchone()
    
    if not existing_exam:
        cursor.execute(
            """INSERT INTO examinations (title, description, duration_minutes, total_marks, pass_marks, is_active)
               VALUES (?, ?, 15, 10, 5, 1)""",
            (exam_title, "Comprehensive assessment evaluating TCP/IP architecture, Subnetting, DHCP, DNS, HTTP, and Client-Server networking concepts.")
        )
        exam_id = cursor.lastrowid
        print(f"  [+] Created Examination: '{exam_title}' (ID: {exam_id})")
    else:
        exam_id = existing_exam['id']
        print(f"  [-] Examination '{exam_title}' already exists (ID: {exam_id}).")

    print("[*] Seeding networking examination questions...")
    sample_questions = [
        (
            "What sequence of packets constitutes the standard TCP three-way handshake used to establish a reliable connection?",
            "SYN -> ACK -> SYN-ACK",
            "SYN -> SYN-ACK -> ACK",
            "FIN -> ACK -> FIN-ACK",
            "PING -> PONG -> ACK",
            "B",
            1,
            "TCP uses a 3-way handshake: 1. Client sends SYN (Synchronize Sequence Number), 2. Server responds with SYN-ACK, 3. Client acknowledges with ACK before data transmission begins."
        ),
        (
            "Which transport layer protocol and UDP port numbers are utilized during a standard DHCP address allocation exchange?",
            "TCP ports 80 and 443",
            "UDP Server port 67 and Client port 68",
            "UDP Server port 53 and Client port 53",
            "TCP ports 20 and 21",
            "B",
            1,
            "DHCP operates over UDP. The DHCP Server listens on destination port 67, while DHCP Clients listen and receive replies on destination port 68."
        ),
        (
            "For the IPv4 network 192.168.10.0/26, what is the total number of usable host addresses and the broadcast address?",
            "62 usable hosts; Broadcast: 192.168.10.63",
            "64 usable hosts; Broadcast: 192.168.10.64",
            "30 usable hosts; Broadcast: 192.168.10.31",
            "126 usable hosts; Broadcast: 192.168.10.127",
            "A",
            1,
            "A /26 prefix has 32 - 26 = 6 host bits. Total addresses = 2^6 = 64. Usable hosts = 64 - 2 = 62. Network is 192.168.10.0, first host is .1, last host is .62, and broadcast is .63."
        ),
        (
            "What is the primary function of the Domain Name System (DNS) in computer networking?",
            "Assigning dynamic IP addresses to connecting workstations automatically",
            "Translating human-readable hostnames (e.g. exam.local) into machine-routable IP addresses",
            "Encrypting transport layer data packets using asymmetric cryptography",
            "Filtering MAC addresses at Layer 2 Ethernet switches",
            "B",
            1,
            "DNS acts as the distributed directory service of the Internet/Intranet, resolving alphanumeric domain names into numerical IP addresses."
        ),
        (
            "Why is the Hypertext Transfer Protocol (HTTP) described as a 'stateless' application layer protocol?",
            "It cannot transmit binary media files such as images or videos",
            "Each HTTP request is executed independently without the server retaining automatic state across multiple requests",
            "It operates exclusively over UDP connectionless datagrams",
            "It prevents clients from caching static assets locally",
            "B",
            1,
            "HTTP is stateless because each request-response pair is treated independently. Modern web apps use cookies and server-side sessions to maintain user login state."
        ),
        (
            "Which of the following IPv4 address blocks is reserved for private intranets under RFC 1918?",
            "8.8.8.0/24",
            "192.168.0.0/16",
            "1.1.1.0/24",
            "128.0.0.0/16",
            "B",
            1,
            "RFC 1918 reserves three private address ranges: 10.0.0.0/8, 172.16.0.0/12, and 192.168.0.0/16. These addresses are not routable on the global public Internet."
        ),
        (
            "According to RFC 3021, how many usable host IP addresses are available in a /31 subnet prefix?",
            "0 usable hosts (only network and broadcast)",
            "2 usable hosts (used for point-to-point links without standard broadcast)",
            "4 usable hosts",
            "1 usable host",
            "B",
            1,
            "RFC 3021 permits using /31 subnets for point-to-point router links. Both addresses (e.g. .0 and .1) are treated as host addresses, eliminating dedicated network and broadcast overhead."
        ),
        (
            "What fundamental design difference distinguishes TCP from UDP at the Transport Layer?",
            "TCP is connection-oriented with guaranteed delivery and flow control; UDP is connectionless and low-overhead",
            "TCP transmits at Layer 2, while UDP transmits at Layer 4",
            "UDP guarantees packet retransmission; TCP drops unacknowledged segments",
            "TCP only supports multicast; UDP only supports unicast",
            "A",
            1,
            "TCP guarantees ordered, error-checked packet delivery through sequence numbers and acknowledgments. UDP trades reliability for low latency and zero connection overhead."
        ),
        (
            "What is the role of a Default Gateway in an IPv4 local area network?",
            "It acts as a physical repeater amplifying radio frequency signals",
            "It is the local router interface IP that forwards traffic destined for remote subnets outside the local broadcast domain",
            "It assigns MAC addresses to network interface cards during boot",
            "It converts IPv4 packets directly into IPv6 packets",
            "B",
            1,
            "When a host's subnet calculation determines the destination IP is outside its local subnet, the host forwards the packet to its Default Gateway's MAC address for routing."
        ),
        (
            "At which OSI layers do an Ethernet Network Switch and an IP Router primarily operate, respectively?",
            "Switch operates at Layer 1; Router operates at Layer 2",
            "Switch operates at Layer 2 (Data Link); Router operates at Layer 3 (Network)",
            "Switch operates at Layer 4; Router operates at Layer 7",
            "Switch operates at Layer 3; Router operates at Layer 1",
            "B",
            1,
            "Standard Ethernet switches operate at Layer 2 (forwarding frames using MAC address tables). Routers operate at Layer 3 (forwarding packets using IP routing tables)."
        )
    ]

    for q_text, opt_a, opt_b, opt_c, opt_d, correct, marks, expl in sample_questions:
        q_exist = cursor.execute(
            "SELECT id FROM questions WHERE exam_id = ? AND question_text = ?",
            (exam_id, q_text)
        ).fetchone()
        if not q_exist:
            cursor.execute(
                """INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks, explanation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (exam_id, q_text, opt_a, opt_b, opt_c, opt_d, correct, marks, expl)
            )
            print(f"  [+] Added Question: '{q_text[:40]}...'")
        else:
            print(f"  [-] Question '{q_text[:40]}...' already exists.")

    print("[*] Seeding simulated DNS Zone records...")
    dns_seeds = [
        ("exam.local", "A", "192.168.10.50", 300),
        ("router.local", "A", "192.168.10.1", 300),
        ("dns.local", "A", "192.168.10.10", 300),
        ("switch.local", "A", "192.168.10.2", 300)
    ]
    for hostname, rtype, target, ttl in dns_seeds:
        cursor.execute(
            """INSERT INTO dns_records (hostname, record_type, target_value, ttl_seconds, is_active)
               VALUES (?, ?, ?, ?, 1)
               ON CONFLICT(hostname) DO UPDATE SET target_value = excluded.target_value""",
            (hostname, rtype, target, ttl)
        )
        print(f"  [+] DNS record configured: {hostname} -> {target}")

    conn.commit()
    conn.close()
    print("[+] Database seeding completed successfully!")

if __name__ == '__main__':
    seed()
