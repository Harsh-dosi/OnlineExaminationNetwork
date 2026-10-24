import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    """Application Configuration Settings"""
    # Security: Secret key for session management and CSRF tokens
    SECRET_KEY = os.environ.get('SECRET_KEY', 'exam-network-secret-key-btech-cn-2026-safe-dev')
    
    # Database configuration
    DATABASE_PATH = os.environ.get('DATABASE_PATH', str(BASE_DIR / 'instance' / 'exam_network.db'))
    
    # Server configuration
    HOST = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_RUN_PORT', 5000))
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    
    # Session cookie security settings (safe for local HTTP classroom demo)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False  # Set to False because classroom demo is on local HTTP
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    
    # DHCP Simulation defaults
    DHCP_NETWORK = '192.168.10.0/24'
    DHCP_POOL_START = '192.168.10.100'
    DHCP_POOL_END = '192.168.10.120'
    DHCP_GATEWAY = '192.168.10.1'
    DHCP_DNS_SERVER = '192.168.10.10'
    DHCP_DEFAULT_LEASE_TIME = 3600  # seconds
    
    # DNS Simulation defaults
    DNS_SIMULATED_DOMAIN = 'exam.local'
    DNS_DEFAULT_TTL = 300  # 5 minutes

class TestingConfig(Config):
    TESTING = True
    DATABASE_PATH = ':memory:'
    SECRET_KEY = 'test-secret-key-isolated-runs'
    WTF_CSRF_ENABLED = False
