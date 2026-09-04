import os
import time
from functools import wraps
from datetime import datetime, timedelta
from flask import session, request, redirect, url_for, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

# ==============================================================================
# 1. ENVIRONMENT CONFIG LOADER
# ==============================================================================

def load_env_file(env_path=".env", override=True):
    """Load key-value pairs from .env file into os.environ."""
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if override or key not in os.environ:
                os.environ[key] = val

# Automatically load on module import
load_env_file()

def get_secret_key():
    """Retrieve secret key for Flask session signing."""
    load_env_file()
    return os.environ.get("SECRET_KEY", "tirexxz_fallback_secret_key_default_2026")

def get_admin_credentials():
    """Retrieve admin username and password dynamically from environment / .env."""
    load_env_file()
    username = os.environ.get("ADMIN_USERNAME", "admin").strip()
    password = os.environ.get("ADMIN_PASSWORD", "admin123").strip()
    return username, password

def get_session_durations():
    """Retrieve session lifetime in days for standard and remember-me logins."""
    try:
        standard_days = int(os.environ.get("SESSION_LIFETIME_DAYS", 7))
    except ValueError:
        standard_days = 7
    try:
        remember_days = int(os.environ.get("REMEMBER_ME_DAYS", 30))
    except ValueError:
        remember_days = 30
    return standard_days, remember_days

# ==============================================================================
# 2. BRUTE-FORCE RATE LIMITER (IN-MEMORY)
# ==============================================================================

# Structure: { ip_address: [timestamp1, timestamp2, ...] }
_failed_attempts = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 15 * 60  # 15 minutes

def is_rate_limited(client_ip):
    """Check if the client IP has exceeded maximum failed login attempts."""
    now = time.time()
    attempts = _failed_attempts.get(client_ip, [])
    
    # Filter attempts within the lockout window
    valid_attempts = [t for t in attempts if now - t < LOCKOUT_WINDOW_SECONDS]
    _failed_attempts[client_ip] = valid_attempts

    return len(valid_attempts) >= MAX_FAILED_ATTEMPTS

def record_failed_attempt(client_ip):
    """Record a failed login attempt for the client IP."""
    now = time.time()
    if client_ip not in _failed_attempts:
        _failed_attempts[client_ip] = []
    _failed_attempts[client_ip].append(now)

def clear_failed_attempts(client_ip):
    """Clear failed login attempts upon successful login."""
    if client_ip in _failed_attempts:
        del _failed_attempts[client_ip]

def get_remaining_lockout_seconds(client_ip):
    """Calculate remaining seconds until lockout expires."""
    now = time.time()
    attempts = _failed_attempts.get(client_ip, [])
    if not attempts:
        return 0
    oldest_valid = min(attempts)
    remaining = int(LOCKOUT_WINDOW_SECONDS - (now - oldest_valid))
    return max(0, remaining)

# ==============================================================================
# 3. CREDENTIAL VERIFICATION
# ==============================================================================

def verify_credentials(input_username, input_password):
    """
    Verify admin credentials against environment config.
    Supports both plaintext passwords and werkzeug password hashes.
    """
    admin_user, admin_pass = get_admin_credentials()

    if input_username.strip() != admin_user:
        return False

    # Check if stored password is a hash (scrypt: or pbkdf2:)
    if admin_pass.startswith(("scrypt:", "pbkdf2:")):
        return check_password_hash(admin_pass, input_password)
    else:
        # Direct string equality for plaintext in .env
        return input_password == admin_pass

# ==============================================================================
# 4. AUTHENTICATION DECORATOR (@admin_required)
# ==============================================================================

def admin_required(f):
    """Decorator to enforce admin authentication on view functions and API endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            # If AJAX or API call, return JSON 401 Unauthorized
            if request.path.startswith("/api/") or request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                return jsonify({
                    "status": "error",
                    "code": "UNAUTHORIZED",
                    "message": "Autentikasi diperlukan. Sesi login telah berakhir."
                }), 401
            
            # For standard page views, redirect to login with 'next' parameter
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function
