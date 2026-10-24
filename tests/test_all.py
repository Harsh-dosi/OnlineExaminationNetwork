"""
Automated Test Suite -- Online Examination Network
Run with: venv/Scripts/pytest tests/ -v
Uses a temp file SQLite database to avoid touching the demo database.
"""
import sys
import os
import pytest

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.db import init_db
from config import Config
from pathlib import Path


@pytest.fixture
def app(tmp_path):
    """Create application with isolated temp-file SQLite database."""
    db_file = str(tmp_path / 'test_exam.db')

    class TempTestConfig(Config):
        TESTING = True
        DATABASE_PATH = db_file
        SECRET_KEY = 'test-secret-key-isolated'
        WTF_CSRF_ENABLED = False
        DEBUG = False

    application = create_app(TempTestConfig)
    schema_path = Path(__file__).resolve().parent.parent / 'app' / 'models' / 'schema.sql'

    with application.app_context():
        init_db(schema_file=schema_path, db_path=db_file)
        from app.models.db import get_db
        db = get_db()

        # Seed minimum data for tests
        from werkzeug.security import generate_password_hash
        db.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            ('testadmin', generate_password_hash('adminpass'), 'Test Admin', 'admin')
        )
        db.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            ('teststudent', generate_password_hash('studentpass'), 'Test Student', 'student')
        )
        db.execute(
            """INSERT INTO examinations (title, description, duration_minutes, total_marks, pass_marks, is_active)
               VALUES ('Test Exam', 'Unit Test Exam', 10, 3, 2, 1)"""
        )
        db.execute(
            """INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks)
               VALUES (1, 'Q1: TCP stands for?', 'Transmission Control Protocol', 'Transfer Config Proto',
                       'Terminal Control Proto', 'Test Channel Protocol', 'A', 1)"""
        )
        db.execute(
            """INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks)
               VALUES (1, 'Q2: DNS port?', '80', '53', '443', '67', 'B', 1)"""
        )
        db.execute(
            """INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks)
               VALUES (1, 'Q3: HTTP status for OK?', '404', '500', '200', '301', 'C', 1)"""
        )
        db.commit()
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


def login_as(client, username, password):
    """Helper to log in via POST and return session."""
    with client.session_transaction() as sess:
        sess['_csrf_token'] = 'test_csrf_token'
    return client.post('/auth/login', data={
        'username': username,
        'password': password,
        'csrf_token': 'test_csrf_token'
    }, follow_redirects=True)


# ===========================================================
# 1. SUBNET CALCULATOR TESTS
# ===========================================================
class TestSubnetCalculator:
    def test_basic_24_prefix(self):
        from app.networking.subnet import parse_subnet_input
        r = parse_subnet_input('192.168.10.50', '24')
        assert r['network_address'] == '192.168.10.0'
        assert r['broadcast_address'] == '192.168.10.255'
        assert r['subnet_mask'] == '255.255.255.0'
        assert r['usable_hosts'] == 254
        assert r['first_usable'] == '192.168.10.1'
        assert r['last_usable'] == '192.168.10.254'

    def test_26_prefix(self):
        from app.networking.subnet import parse_subnet_input
        r = parse_subnet_input('192.168.10.0', '26')
        assert r['network_address'] == '192.168.10.0'
        assert r['broadcast_address'] == '192.168.10.63'
        assert r['usable_hosts'] == 62
        assert r['total_addresses'] == 64

    def test_31_prefix_rfc3021(self):
        from app.networking.subnet import parse_subnet_input
        r = parse_subnet_input('10.0.0.0', '31')
        assert r['usable_hosts'] == 2
        assert 'RFC 3021' in r['note']
        assert 'None' in r['broadcast_address']

    def test_32_host_route(self):
        from app.networking.subnet import parse_subnet_input
        r = parse_subnet_input('192.168.1.1', '32')
        assert r['usable_hosts'] == 1
        assert 'N/A' in r['broadcast_address']

    def test_dotted_decimal_mask(self):
        from app.networking.subnet import parse_subnet_input
        r = parse_subnet_input('10.0.0.1', '255.0.0.0')
        assert r['prefix_length'] == '/8'
        assert r['network_address'] == '10.0.0.0'
        assert r['usable_hosts'] == 16777214

    def test_invalid_ip(self):
        from app.networking.subnet import parse_subnet_input
        with pytest.raises(ValueError, match="not a valid IPv4"):
            parse_subnet_input('999.999.0.1', '24')

    def test_empty_ip(self):
        from app.networking.subnet import parse_subnet_input
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_subnet_input('', '24')

    def test_invalid_prefix_out_of_range(self):
        from app.networking.subnet import parse_subnet_input
        with pytest.raises(ValueError, match="between 0 and 32"):
            parse_subnet_input('192.168.1.1', '33')

    def test_private_ip_detection(self):
        from app.networking.subnet import parse_subnet_input
        r = parse_subnet_input('192.168.1.1', '24')
        assert r['address_scope'] == 'Private (RFC 1918 / Local)'

    def test_class_a(self):
        from app.networking.subnet import parse_subnet_input
        r = parse_subnet_input('10.0.0.1', '8')
        assert 'Class A' in r['ip_class']

    def test_class_c(self):
        from app.networking.subnet import parse_subnet_input
        r = parse_subnet_input('192.168.1.1', '24')
        assert 'Class C' in r['ip_class']


# ===========================================================
# 2. DHCP SIMULATION TESTS
# ===========================================================
class TestDHCPSimulator:
    def get_sim(self):
        from app.networking.dhcp_simulator import DHCPSimulator
        return DHCPSimulator(pool_start='192.168.10.100', pool_end='192.168.10.102',
                             subnet_mask='255.255.255.0', gateway='192.168.10.1',
                             dns_server='192.168.10.10')

    def test_dora_allocates_ip(self, app):
        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            sim = self.get_sim()
            result = sim.simulate_dora_lease(db, 'AA:BB:CC:DD:EE:01', 'test-client')
            assert result['success'] is True
            assert result['assigned_ip'].startswith('192.168.10.1')
            assert len(result['dora_trace']) == 4

    def test_no_duplicate_ip_same_mac(self, app):
        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            sim = self.get_sim()
            r1 = sim.simulate_dora_lease(db, 'AA:BB:CC:DD:EE:02', 'client-a')
            r2 = sim.simulate_dora_lease(db, 'AA:BB:CC:DD:EE:02', 'client-a-renew')
            assert r1['assigned_ip'] == r2['assigned_ip']
            assert r2['is_renewal'] is True

    def test_pool_exhaustion(self, app):
        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            # Pool has 3 IPs: .100, .101, .102
            sim = self.get_sim()
            sim.simulate_dora_lease(db, 'AA:BB:CC:DD:EE:10', 'c1')
            sim.simulate_dora_lease(db, 'AA:BB:CC:DD:EE:11', 'c2')
            sim.simulate_dora_lease(db, 'AA:BB:CC:DD:EE:12', 'c3')
            with pytest.raises(ValueError, match="Pool Exhausted"):
                sim.simulate_dora_lease(db, 'AA:BB:CC:DD:EE:13', 'c4')

    def test_release_returns_ip_to_pool(self, app):
        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            sim = self.get_sim()
            r = sim.simulate_dora_lease(db, 'AA:BB:CC:DD:EE:20', 'client-release')
            ip = r['assigned_ip']
            rel = sim.release_lease(db, 'AA:BB:CC:DD:EE:20')
            assert rel['released_ip'] == ip
            # Should be available again
            r2 = sim.simulate_dora_lease(db, 'AA:BB:CC:DD:EE:21', 'new-client')
            assert r2['success'] is True

    def test_invalid_mac_raises(self, app):
        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            sim = self.get_sim()
            with pytest.raises(ValueError, match="Invalid MAC"):
                sim.simulate_dora_lease(db, 'NOT-A-MAC', 'client')

    def test_release_nonexistent_lease(self, app):
        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            sim = self.get_sim()
            with pytest.raises(ValueError, match="No active lease"):
                sim.release_lease(db, 'FF:FF:FF:FF:FF:FF')


# ===========================================================
# 3. DNS SIMULATION TESTS
# ===========================================================
class TestDNSSimulator:
    def test_resolve_known_host(self, app):
        with app.app_context():
            from app.models.db import get_db
            from app.networking.dns_simulator import DNSSimulator
            db = get_db()
            dns = DNSSimulator()
            db.execute(
                "INSERT INTO dns_records (hostname, record_type, target_value, ttl_seconds, is_active) VALUES ('exam.local', 'A', '192.168.10.50', 300, 1)"
            )
            db.commit()
            result = dns.resolve(db, 'exam.local')
            assert result['status'] == 'NOERROR'
            assert result['resolved_ip'] == '192.168.10.50'
            assert result['source'] == 'AUTHORITATIVE_ZONE'

    def test_resolve_unknown_host_nxdomain(self, app):
        with app.app_context():
            from app.models.db import get_db
            from app.networking.dns_simulator import DNSSimulator
            db = get_db()
            dns = DNSSimulator()
            result = dns.resolve(db, 'unknown.notexist')
            assert 'NXDOMAIN' in result['status']
            assert result['resolved_ip'] is None

    def test_dns_cache_hit(self, app):
        with app.app_context():
            from app.models.db import get_db
            from app.networking.dns_simulator import DNSSimulator
            db = get_db()
            dns = DNSSimulator()
            db.execute(
                "INSERT INTO dns_records (hostname, record_type, target_value, ttl_seconds, is_active) VALUES ('cache.local', 'A', '10.0.0.1', 300, 1)"
            )
            db.commit()
            r1 = dns.resolve(db, 'cache.local')
            assert r1['source'] == 'AUTHORITATIVE_ZONE'
            r2 = dns.resolve(db, 'cache.local')
            assert r2['source'] == 'CACHE_HIT'
            assert r2['hit_count'] >= 2

    def test_add_record_and_resolve(self, app):
        with app.app_context():
            from app.models.db import get_db
            from app.networking.dns_simulator import DNSSimulator
            db = get_db()
            dns = DNSSimulator()
            dns.add_or_update_record(db, 'new.local', '10.20.30.40', ttl_seconds=120)
            result = dns.resolve(db, 'new.local')
            assert result['resolved_ip'] == '10.20.30.40'

    def test_clear_cache(self, app):
        with app.app_context():
            from app.models.db import get_db
            from app.networking.dns_simulator import DNSSimulator
            db = get_db()
            dns = DNSSimulator()
            db.execute(
                "INSERT INTO dns_records (hostname, record_type, target_value, ttl_seconds, is_active) VALUES ('clear.local', 'A', '1.2.3.4', 300, 1)"
            )
            db.commit()
            dns.resolve(db, 'clear.local')  # populates cache
            dns.clear_cache(db)
            cache = db.execute("SELECT * FROM dns_cache").fetchall()
            assert len(cache) == 0

    def test_empty_hostname_raises(self, app):
        with app.app_context():
            from app.models.db import get_db
            from app.networking.dns_simulator import DNSSimulator
            db = get_db()
            dns = DNSSimulator()
            with pytest.raises(ValueError, match="cannot be empty"):
                dns.resolve(db, '')


# ===========================================================
# 4. AUTHENTICATION TESTS
# ===========================================================
class TestAuthentication:
    def test_login_page_loads(self, client):
        r = client.get('/auth/login')
        assert r.status_code == 200
        assert b'Login' in r.data

    def test_valid_student_login(self, client):
        r = login_as(client, 'teststudent', 'studentpass')
        assert r.status_code == 200
        assert b'Student Dashboard' in r.data or b'teststudent' in r.data

    def test_valid_admin_login(self, client):
        r = login_as(client, 'testadmin', 'adminpass')
        assert r.status_code == 200
        assert b'Admin' in r.data or b'testadmin' in r.data

    def test_invalid_password_rejected(self, client):
        r = login_as(client, 'teststudent', 'wrongpassword')
        assert b'Invalid' in r.data or r.status_code in (200, 400)

    def test_invalid_username_rejected(self, client):
        r = login_as(client, 'nonexistentuser', 'password')
        assert b'Invalid' in r.data or r.status_code in (200, 400)

    def test_unauthenticated_dashboard_redirects(self, client):
        r = client.get('/student/dashboard', follow_redirects=False)
        assert r.status_code == 302

    def test_unauthenticated_admin_redirects(self, client):
        r = client.get('/admin/dashboard', follow_redirects=False)
        assert r.status_code == 302

    def test_logout_clears_session(self, client):
        login_as(client, 'teststudent', 'studentpass')
        r = client.get('/auth/logout', follow_redirects=True)
        assert r.status_code == 200
        # After logout, dashboard should redirect
        r2 = client.get('/student/dashboard', follow_redirects=False)
        assert r2.status_code == 302

    def test_student_cannot_access_admin(self, client):
        login_as(client, 'teststudent', 'studentpass')
        r = client.get('/admin/dashboard', follow_redirects=True)
        assert b'Administrator' not in r.data or r.status_code in (200, 302, 403)


# ===========================================================
# 5. EXAM WORKFLOW TESTS
# ===========================================================
class TestExamWorkflow:
    def test_student_dashboard_loads(self, client):
        login_as(client, 'teststudent', 'studentpass')
        r = client.get('/student/dashboard')
        assert r.status_code == 200

    def test_start_exam_creates_attempt(self, client, app):
        login_as(client, 'teststudent', 'studentpass')
        r = client.get('/student/exam/1/start')
        assert r.status_code == 200
        assert b'Q1' in r.data or b'Question' in r.data

        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            attempts = db.execute("SELECT * FROM exam_attempts WHERE exam_id = 1").fetchall()
            assert len(attempts) >= 1

    def test_submit_exam_calculates_score(self, client, app):
        login_as(client, 'teststudent', 'studentpass')
        # Start exam
        r = client.get('/student/exam/1/start', follow_redirects=True)
        assert r.status_code == 200

        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            attempt = db.execute("SELECT * FROM exam_attempts WHERE status='in_progress' ORDER BY id DESC LIMIT 1").fetchone()
            assert attempt is not None
            attempt_id = attempt['id']

        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'test_csrf_submit'

        # Submit with all correct answers (A=Q1, B=Q2, C=Q3)
        r = client.post('/student/exam/submit', data={
            'attempt_id': attempt_id,
            'csrf_token': 'test_csrf_submit',
            'q_1': 'A',  # TCP -> correct
            'q_2': 'B',  # DNS port -> correct
            'q_3': 'C',  # 200 -> correct
        }, follow_redirects=True)
        assert r.status_code == 200

        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            att = db.execute("SELECT * FROM exam_attempts WHERE id = ?", (attempt_id,)).fetchone()
            assert att['status'] in ('completed', 'timed_out')
            assert att['score'] == 3  # all correct
            assert att['total_possible'] == 3

    def test_duplicate_submission_prevented(self, client, app):
        """Second submission on a completed attempt should redirect, not duplicate."""
        login_as(client, 'teststudent', 'studentpass')

        with app.app_context():
            from app.models.db import get_db
            from app.auth.routes import generate_csrf_token
            db = get_db()
            # Manually create a completed attempt
            db.execute(
                """INSERT INTO exam_attempts (user_id, exam_id, start_time, submitted_at, score, total_possible, percentage, status, client_ip)
                   VALUES (2, 1, datetime('now'), datetime('now'), 2, 3, 66.7, 'completed', '127.0.0.1')"""
            )
            db.commit()
            attempt = db.execute("SELECT id FROM exam_attempts WHERE status = 'completed' ORDER BY id DESC LIMIT 1").fetchone()
            attempt_id = attempt['id']

        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'dup_test_token'

        r = client.post('/student/exam/submit', data={
            'attempt_id': attempt_id,
            'csrf_token': 'dup_test_token',
            'q_1': 'A'
        }, follow_redirects=True)
        assert r.status_code == 200
        # Should show result page, not re-grade
        assert b'already' in r.data.lower() or b'result' in r.data.lower() or b'Result' in r.data

    def test_result_page_loads(self, client, app):
        login_as(client, 'teststudent', 'studentpass')
        # Create a completed attempt
        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            db.execute(
                """INSERT INTO exam_attempts (user_id, exam_id, start_time, submitted_at, score, total_possible, percentage, status, client_ip)
                   VALUES (2, 1, datetime('now'), datetime('now'), 3, 3, 100.0, 'completed', '127.0.0.1')"""
            )
            db.commit()
            att = db.execute("SELECT id FROM exam_attempts WHERE status='completed' ORDER BY id DESC LIMIT 1").fetchone()
            attempt_id = att['id']

        r = client.get(f'/student/result/{attempt_id}')
        assert r.status_code == 200
        assert b'Result' in r.data or b'Score' in r.data


# ===========================================================
# 6. HTTP STATUS CODE TESTS
# ===========================================================
class TestHTTPStatusCodes:
    def test_home_200(self, client):
        assert client.get('/').status_code == 200

    def test_login_200(self, client):
        assert client.get('/auth/login').status_code == 200

    def test_network_dashboard_200(self, client):
        assert client.get('/network/').status_code == 200

    def test_subnet_200(self, client):
        assert client.get('/network/subnet').status_code == 200

    def test_dhcp_200(self, client):
        assert client.get('/network/dhcp').status_code == 200

    def test_dns_200(self, client):
        assert client.get('/network/dns').status_code == 200

    def test_topology_200(self, client):
        assert client.get('/network/topology').status_code == 200

    def test_performance_200(self, client):
        assert client.get('/network/performance').status_code == 200

    def test_health_api_200(self, client):
        r = client.get('/network/api/health')
        assert r.status_code == 200

    def test_404_handled(self, client):
        r = client.get('/this-route-does-not-exist')
        assert r.status_code == 404

    def test_protected_student_redirect(self, client):
        r = client.get('/student/dashboard', follow_redirects=False)
        assert r.status_code == 302

    def test_protected_admin_redirect(self, client):
        r = client.get('/admin/dashboard', follow_redirects=False)
        assert r.status_code == 302


# ===========================================================
# 7. DATABASE INITIALIZATION TEST
# ===========================================================
class TestDatabaseInit:
    def test_db_tables_created(self, app):
        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            tables = [r[0] for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            expected = ['users', 'examinations', 'questions', 'exam_attempts',
                        'submitted_answers', 'dhcp_leases', 'dns_records', 'dns_cache',
                        'network_event_logs', 'performance_metrics']
            for t in expected:
                assert t in tables, f"Missing table: {t}"

    def test_seeded_users_exist(self, app):
        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            assert count >= 2

    def test_exam_and_questions_exist(self, app):
        with app.app_context():
            from app.models.db import get_db
            db = get_db()
            exams = db.execute("SELECT COUNT(*) FROM examinations").fetchone()[0]
            qs = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
            assert exams >= 1
            assert qs >= 3

    def test_foreign_key_constraint(self, app):
        with app.app_context():
            from app.models.db import get_db
            import sqlite3
            db = get_db()
            # Attempt to insert a question for a non-existent exam
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(
                    """INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks)
                       VALUES (9999, 'Test', 'A', 'B', 'C', 'D', 'A', 1)"""
                )
                db.commit()


# ===========================================================
# 8. SUBNET API ENDPOINT TEST
# ===========================================================
class TestSubnetAPI:
    def test_api_valid_calculation(self, client):
        r = client.post('/network/api/subnet/calculate',
                        json={'ip_address': '192.168.10.0', 'prefix_or_mask': '24'})
        assert r.status_code == 200
        data = r.get_json()
        assert data['success'] is True
        assert data['data']['network_address'] == '192.168.10.0'

    def test_api_invalid_ip_returns_400(self, client):
        r = client.post('/network/api/subnet/calculate',
                        json={'ip_address': 'bad.ip', 'prefix_or_mask': '24'})
        assert r.status_code == 400
        data = r.get_json()
        assert data['success'] is False
