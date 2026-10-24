-- Online Examination Network Database Schema (SQLite)
-- Designed for Academic Computer Networks Demonstration

PRAGMA foreign_keys = ON;

-- 1. Users Table (Authentication & Role-Based Access)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student', 'admin')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Examinations Table
CREATE TABLE IF NOT EXISTS examinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    duration_minutes INTEGER NOT NULL DEFAULT 15,
    total_marks INTEGER NOT NULL DEFAULT 10,
    pass_marks INTEGER NOT NULL DEFAULT 5,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Questions Table (Networking MCQ Bank)
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL CHECK(correct_option IN ('A', 'B', 'C', 'D')),
    marks INTEGER NOT NULL DEFAULT 1,
    explanation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exam_id) REFERENCES examinations(id) ON DELETE CASCADE
);

-- 4. Exam Attempts Table
CREATE TABLE IF NOT EXISTS exam_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP,
    score INTEGER DEFAULT 0,
    total_possible INTEGER DEFAULT 0,
    percentage REAL DEFAULT 0.0,
    status TEXT NOT NULL CHECK(status IN ('in_progress', 'completed', 'timed_out')),
    client_ip TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id) REFERENCES examinations(id) ON DELETE CASCADE
);

-- 5. Submitted Answers Table
CREATE TABLE IF NOT EXISTS submitted_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    selected_option TEXT CHECK(selected_option IN ('A', 'B', 'C', 'D')),
    is_correct INTEGER NOT NULL DEFAULT 0 CHECK(is_correct IN (0, 1)),
    marks_awarded INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    UNIQUE(attempt_id, question_id)
);

-- 6. DHCP Simulation Leases Table
CREATE TABLE IF NOT EXISTS dhcp_leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mac_address TEXT UNIQUE NOT NULL,
    hostname TEXT NOT NULL,
    ip_address TEXT UNIQUE NOT NULL,
    subnet_mask TEXT NOT NULL,
    gateway TEXT NOT NULL,
    dns_server TEXT NOT NULL,
    lease_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lease_end TIMESTAMP NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active', 'released', 'expired'))
);

-- 7. DNS Simulation Records Table
CREATE TABLE IF NOT EXISTS dns_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname TEXT UNIQUE NOT NULL,
    record_type TEXT NOT NULL DEFAULT 'A' CHECK(record_type IN ('A', 'CNAME')),
    target_value TEXT NOT NULL,
    ttl_seconds INTEGER NOT NULL DEFAULT 300,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. DNS Simulation Cache Table
CREATE TABLE IF NOT EXISTS dns_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname TEXT UNIQUE NOT NULL,
    resolved_ip TEXT NOT NULL,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 1
);

-- 9. Network Event Logs Table
CREATE TABLE IF NOT EXISTS network_event_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    client_ip TEXT NOT NULL,
    description TEXT NOT NULL,
    status_code INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. Performance Benchmark Records Table
CREATE TABLE IF NOT EXISTS performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_name TEXT NOT NULL,
    request_count INTEGER NOT NULL,
    successful_requests INTEGER NOT NULL,
    failed_requests INTEGER NOT NULL,
    avg_response_ms REAL NOT NULL,
    min_response_ms REAL NOT NULL,
    max_response_ms REAL NOT NULL,
    median_response_ms REAL NOT NULL,
    p95_response_ms REAL NOT NULL,
    throughput_rps REAL NOT NULL,
    total_duration_sec REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Fast Querying and Network Integrity
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_attempts_user_exam ON exam_attempts(user_id, exam_id);
CREATE INDEX IF NOT EXISTS idx_dhcp_mac ON dhcp_leases(mac_address);
CREATE INDEX IF NOT EXISTS idx_dns_hostname ON dns_records(hostname);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON network_event_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_perf_timestamp ON performance_metrics(timestamp);
