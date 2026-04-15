from collections import Counter
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response, abort
import json
import os
import random
from functools import wraps
from andulisia import andulisia_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database Paths
SCHOOL_DB = os.environ.get(
    'SCHOOL_DB_PATH',
    os.path.join(BASE_DIR, 'templates', 'school', 'database.json'),
)
EMAIL_DB = os.environ.get(
    'EMAIL_DB_PATH',
    os.path.join(BASE_DIR, 'templates', 'emails', 'database.json'),
)
KINGDOM_DB = os.environ.get(
    'KINGDOM_DB_PATH',
    os.path.join(BASE_DIR, 'templates', 'kingdom', 'database.json'),
)
ADMIN_DB = os.environ.get(
    'ADMIN_DB_PATH',
    os.path.join(BASE_DIR, 'templates', 'admin', 'database.json'),
)


app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-school-admin-change-me')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=14)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.register_blueprint(andulisia_bp, url_prefix='/andulisa')
MASTER_ADMIN_PASS = "XyZ9#kP2$mQv8L3wR5tN7bJ!"

EMAIL_ADMIN_PASS = "spyyoyo" 
EMAIL_CREDITS = 500  
DEFAULT_KINGDOM_DB = {
    "users": [],
    "heroes": {},
    "pending_verifications": [],
    "logs": [],
}
DEFAULT_EMAIL_DB = {
    "accounts": [],
}

def empty_kingdom_db():
    return {
        "users": [],
        "heroes": {},
        "user_stats": {},
        "battles": [],
        "pending_verifications": [],
        "logs": [],
    }

def empty_email_db():
    return {
        "accounts": [],
    }

def empty_school_db():
    return {
        "news": {},
        "exams": [],
        "timetables": {},
    }

def empty_admin_db():
    return {
        "links": [],
        "notes": [],
        "banned_ips": [],
        "banned_users": [],
        "logs": [],
    }

def default_db_for(path):
    if path == SCHOOL_DB:
        return empty_school_db()
    if path == KINGDOM_DB:
        return empty_kingdom_db()
    if path == EMAIL_DB:
        return empty_email_db()
    if path == ADMIN_DB:
        return empty_admin_db()
    return {}

class DatabasePermissionError(PermissionError):
    pass

def permission_error_message(path, action):
    return f"Permission denied while trying to {action} database file: {path}"

def ensure_db_parent(path):
    parent = os.path.dirname(path)
    if parent:
        try:
            os.makedirs(parent, exist_ok=True)
        except PermissionError as exc:
            raise DatabasePermissionError(permission_error_message(path, "prepare")) from exc

def ensure_db_file(path):
    ensure_db_parent(path)
    if os.path.exists(path):
        return
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(default_db_for(path), f, indent=4)
    except PermissionError as exc:
        raise DatabasePermissionError(permission_error_message(path, "create")) from exc

# --- DATABASE HELPERS ---

def init_dbs():
    """Initializes JSON databases if they don't exist."""
    for path in (SCHOOL_DB, EMAIL_DB, KINGDOM_DB, ADMIN_DB):
        ensure_db_file(path)

def get_db(path):
    ensure_db_file(path)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except PermissionError as exc:
        raise DatabasePermissionError(permission_error_message(path, "read")) from exc
    except (json.JSONDecodeError, OSError):
        data = default_db_for(path)
        save_db(path, data)
    if path == KINGDOM_DB:
        data.setdefault("users", [])
        data.setdefault("heroes", {})
        data.setdefault("user_stats", {})
        data.setdefault("battles", [])
        data.setdefault("pending_verifications", [])
        data.setdefault("logs", [])
    elif path == SCHOOL_DB:
        data.setdefault("news", {})
        data.setdefault("exams", [])
        data.setdefault("timetables", {})
    elif path == EMAIL_DB:
        data.setdefault("accounts", [])
    elif path == ADMIN_DB:
        data.setdefault("links", [])
        data.setdefault("notes", [])
        data.setdefault("banned_ips", [])
        data.setdefault("banned_users", [])
        data.setdefault("logs", [])
    return data

def save_db(path, data):
    ensure_db_parent(path)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except PermissionError as exc:
        raise DatabasePermissionError(permission_error_message(path, "write")) from exc

def normalize_username(value):
    return (value or '').strip()

def normalize_email(value):
    return (value or '').strip().lower()

def normalize_key(value):
    return normalize_username(value).lower()

def get_kingdom_users():
    return get_db(KINGDOM_DB).get('users', [])

def get_kingdom_db():
    db = get_db(KINGDOM_DB)
    db.setdefault("user_stats", {})
    db.setdefault("battles", [])
    db.setdefault("users", [])
    db.setdefault("heroes", {})
    db.setdefault("pending_verifications", [])
    db.setdefault("logs", [])
    return db

def get_email_db():
    return get_db(EMAIL_DB)

def parse_note_tags(raw_value):
    return [tag.strip() for tag in (raw_value or '').split(',') if tag.strip()]

def parse_note_checklist(raw_value):
    items = []
    for line in (raw_value or '').splitlines():
        cleaned = line.strip()
        if cleaned:
            items.append(cleaned)
    return items

def build_note_from_form(form, existing_note=None):
    now = now_utc_iso()
    note_id = existing_note.get('id') if existing_note else str(int(datetime.now().timestamp() * 1000))
    created_at = existing_note.get('created_at') if existing_note else now
    return {
        "id": note_id,
        "title": (form.get('title') or '').strip() or "Untitled note",
        "content": (form.get('content') or '').strip(),
        "category": (form.get('category') or 'General').strip() or "General",
        "color": (form.get('color') or 'aurora').strip() or "aurora",
        "tags": parse_note_tags(form.get('tags')),
        "checklist": parse_note_checklist(form.get('checklist')),
        "reminder": (form.get('reminder') or '').strip(),
        "is_pinned": existing_note.get('is_pinned', False) if existing_note else bool(form.get('pin_on_save')),
        "is_favorite": existing_note.get('is_favorite', False) if existing_note else False,
        "is_archived": existing_note.get('is_archived', False) if existing_note else False,
        "created_at": created_at,
        "updated_at": now,
    }

def sort_notes(notes):
    def note_key(note):
        return (
            0 if note.get('is_pinned') else 1,
            0 if note.get('is_favorite') else 1,
            note.get('updated_at', ''),
        )
    return sorted(notes, key=note_key, reverse=True)

def note_matches_filters(note, query, status_filter, category_filter):
    haystack = " ".join([
        note.get('title', ''),
        note.get('content', ''),
        " ".join(note.get('tags', [])),
        " ".join(note.get('checklist', [])),
        note.get('category', ''),
    ]).lower()

    if query and query not in haystack:
        return False

    if category_filter and note.get('category', '').lower() != category_filter:
        return False

    if status_filter == 'pinned' and not note.get('is_pinned'):
        return False
    if status_filter == 'favorites' and not note.get('is_favorite'):
        return False
    if status_filter == 'archived' and not note.get('is_archived'):
        return False
    if status_filter == 'active' and note.get('is_archived'):
        return False

    return True

def find_email_account(username):
    normalized_username = normalize_username(username)
    if not normalized_username:
        return None
    db = get_email_db()
    for account in db.get('accounts', []):
        if normalize_username(account.get('username')).lower() == normalized_username.lower():
            return account
    return None

def generate_otp():
    return f"{random.randint(100000, 999999)}"

def now_utc_iso():
    return datetime.now(timezone.utc).isoformat()

def otp_expiry_iso(minutes=10):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()

def is_expired(iso_value):
    if not iso_value:
        return True
    try:
        return datetime.now(timezone.utc) > datetime.fromisoformat(iso_value)
    except ValueError:
        return True

@app.errorhandler(DatabasePermissionError)
def handle_database_permission_error(error):
    message = str(error)
    if request.path.startswith('/api/') or request.accept_mimetypes.accept_json:
        return jsonify({"status": "error", "message": message}), 500
    return Response(message, status=500, mimetype='text/plain')

def clean_pending_verifications(db):
    pending = db.get('pending_verifications', [])
    db['pending_verifications'] = [
        item for item in pending
        if not is_expired(item.get('expires_at'))
    ]
    return db['pending_verifications']

def find_pending_verification(db, email):
    normalized_email = normalize_email(email)
    for item in db.get('pending_verifications', []):
        if normalize_email(item.get('email')) == normalized_email:
            return item
    return None

def find_kingdom_user(identifier):
    normalized_identifier = normalize_email(identifier)
    raw_identifier = normalize_username(identifier)
    if not raw_identifier:
        return None

    for user in get_kingdom_users():
        username = normalize_username(user.get('username'))
        email = normalize_email(user.get('email'))
        if username.lower() == raw_identifier.lower() or email == normalized_identifier:
            return user
    return None

def get_logged_in_kingdom_user():
    username = session.get('kingdom_user')
    if not username:
        return None
    return find_kingdom_user(username)

@app.context_processor
def inject_kingdom_auth():
    user = get_logged_in_kingdom_user()
    return {
        'kingdom_user': user,
        'kingdom_username': user.get('username') if user else None,
    }

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('master_admin'):
            return redirect(url_for('admin_index', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def track_and_check_bans():
    # 1. IP Ban Check
    db = get_db(ADMIN_DB)
    if request.remote_addr in db.get('banned_ips', []):
        abort(403)
    
    # 2. Kingdom User Ban Check
    k_user = get_logged_in_kingdom_user()
    if k_user and k_user.get('username') in db.get('banned_users', []):
        session.pop('kingdom_user', None)
        return redirect(url_for('kingdom_login'))

    # 3. Log the visit (Ignore static files)
    if not request.path.startswith('/static'):
        log_entry = {
            "ip": request.remote_addr,
            "path": request.path,
            "timestamp": now_utc_iso(),
            "user": k_user.get('username') if k_user else "Guest"
        }
        db['logs'].append(log_entry)
        # Keep only last 1000 logs
        if len(db['logs']) > 1000:
            db['logs'] = db['logs'][-1000:]
        save_db(ADMIN_DB, db)

try:
    init_dbs()
except DatabasePermissionError as exc:
    app.logger.error(str(exc))

# --- PAGE ROUTES ---

def request_host_name():
    return request.host.split(':', 1)[0].lower()


def is_app_site_request():
    return request_host_name() == 'app.spyyoyo.xyz'

@app.route('/robots.txt')
def robots():
    """Tells Google and other search engines how to crawl the site."""
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {request.url_root.rstrip('/')}/sitemap.xml"
    ]
    return Response("\n".join(lines), mimetype="text/plain")

@app.route('/sitemap.xml')
def sitemap():
    """Provides a map of all important pages to Google."""
    pages = [
        '/', '/emails', '/kingdom', '/school', '/andulisa',
        '/school/exams', '/school/timetables'
    ]
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for page in pages:
        xml += f'  <url><loc>{request.url_root.rstrip("/")}{page}</loc></url>\n'
    xml += '</urlset>'
    return Response(xml, mimetype='application/xml')

@app.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='favicon.ico')) 


@app.errorhandler(404)
def page_not_found(error):

    if request.path.endswith('/'):
        return redirect(request.path[:-1])

    return redirect('/')


@app.route('/school')
def school():
    return render_template('school/index.html')



@app.route('/school/exams')
def exams_page():
    data = get_db(SCHOOL_DB)
    return render_template('school/exams.html', exams=data.get('exams', []))


@app.route('/school/admin')
def schooladmin():
    admin_unlocked = bool(session.get('master_admin'))
    return render_template(
        'school/admin.html',
        data=get_db(SCHOOL_DB) if admin_unlocked else empty_school_db(),
        admin_unlocked=admin_unlocked,
        next_target=request.path,
    )


@app.route('/school/timetables')
def timetables_page():
    return render_template('school/timetables.html')


@app.route('/')
def index():
    if is_app_site_request():
        return render_template('app/index.html')
    return render_template('index.html')

# --- NEW ADMIN FOLDER ROUTES ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == MASTER_ADMIN_PASS:
            session.permanent = True
            session['master_admin'] = True
            return redirect(url_for('admin_index'))
        return render_template('admin/login.html', error="Access Denied")
    return render_template('admin/login.html')

@app.route('/admin')
def admin_index():
    next_target = request.args.get('next', '').strip()
    if not next_target.startswith('/'):
        next_target = ''
    return render_template(
        'admin/index.html',
        admin_unlocked=bool(session.get('master_admin')),
        next_target=next_target,
    )

@app.route('/admin/notes', methods=['GET', 'POST'])
def admin_notes():
    if request.method == 'POST' and not session.get('master_admin'):
        return redirect(url_for('admin_index', next=request.path))

    admin_unlocked = bool(session.get('master_admin'))
    db = get_db(ADMIN_DB)
    notes = db.get('notes', [])

    if request.method == 'POST':
        action = request.form.get('action')
        note_id = request.form.get('id')
        target_note = next((note for note in notes if note.get('id') == note_id), None)

        if action == 'create':
            notes.append(build_note_from_form(request.form))
        elif action == 'update' and target_note:
            updated_note = build_note_from_form(request.form, target_note)
            target_note.update(updated_note)
        elif action == 'delete' and target_note:
            db['notes'] = [note for note in notes if note.get('id') != note_id]
            notes = db['notes']
        elif action == 'toggle_pin' and target_note:
            target_note['is_pinned'] = not target_note.get('is_pinned', False)
            target_note['updated_at'] = now_utc_iso()
        elif action == 'toggle_favorite' and target_note:
            target_note['is_favorite'] = not target_note.get('is_favorite', False)
            target_note['updated_at'] = now_utc_iso()
        elif action == 'toggle_archive' and target_note:
            target_note['is_archived'] = not target_note.get('is_archived', False)
            target_note['updated_at'] = now_utc_iso()

        db['notes'] = sort_notes(notes)
        save_db(ADMIN_DB, db)
        return redirect(url_for('admin_notes'))

    query = (request.args.get('q') or '').strip().lower()
    status_filter = (request.args.get('status') or 'all').strip().lower()
    category_filter = (request.args.get('category') or '').strip().lower()
    filtered_notes = [
        note for note in sort_notes(notes)
        if note_matches_filters(note, query, status_filter, category_filter)
    ]

    edit_note_id = request.args.get('edit')
    editing_note = next((note for note in notes if note.get('id') == edit_note_id), None)
    categories = sorted({(note.get('category') or 'General').strip() for note in notes if (note.get('category') or '').strip()})

    stats = {
        "total": len(notes),
        "active": len([note for note in notes if not note.get('is_archived')]),
        "pinned": len([note for note in notes if note.get('is_pinned')]),
        "favorites": len([note for note in notes if note.get('is_favorite')]),
        "archived": len([note for note in notes if note.get('is_archived')]),
    }

    return render_template(
        'admin/notes.html',
        notes=filtered_notes if admin_unlocked else [],
        editing_note=editing_note if admin_unlocked else None,
        editing_tags=', '.join(editing_note.get('tags', [])) if editing_note and admin_unlocked else '',
        editing_checklist='\n'.join(editing_note.get('checklist', [])) if editing_note and admin_unlocked else '',
        categories=categories if admin_unlocked else [],
        filters={
            "q": request.args.get('q', '') if admin_unlocked else '',
            "status": status_filter if admin_unlocked else 'all',
            "category": request.args.get('category', '') if admin_unlocked else '',
        },
        stats=stats if admin_unlocked else {
            "total": 0,
            "active": 0,
            "pinned": 0,
            "favorites": 0,
            "archived": 0,
        },
        admin_unlocked=admin_unlocked,
        next_target=request.path,
    )

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if request.method == 'POST' and not session.get('master_admin'):
        return redirect(url_for('admin_index', next=request.path))

    admin_unlocked = bool(session.get('master_admin'))
    db = get_db(ADMIN_DB)
    k_db = get_kingdom_db()

    if request.method == 'POST':
        action = normalize_key(request.form.get('action'))
        ip_value = normalize_key(request.form.get('ip'))
        username_value = normalize_username(request.form.get('username'))

        if action == 'ban-ip' and ip_value and ip_value not in db['banned_ips']:
            db['banned_ips'].append(ip_value)
        elif action == 'unban-ip' and ip_value:
            db['banned_ips'] = [ip for ip in db['banned_ips'] if ip != ip_value]
        elif action == 'ban-user' and username_value and username_value not in db['banned_users']:
            db['banned_users'].append(username_value)
        elif action == 'unban-user' and username_value:
            db['banned_users'] = [user for user in db['banned_users'] if user != username_value]

        save_db(ADMIN_DB, db)
        return redirect(url_for('admin_dashboard'))

    logs = db.get('logs', [])
    recent_logs = logs[::-1]
    path_counts = Counter(log.get('path') or '/' for log in logs)
    ip_counts = Counter(log.get('ip') or 'Unknown' for log in logs)
    recent_paths = []
    for path, visits in path_counts.most_common(8):
        recent_paths.append({
            "path": path,
            "visits": visits,
            "url": request.url_root.rstrip('/') + path,
        })

    tracked_users = []
    for user in k_db.get('users', []):
        username = user.get('username')
        hero = k_db.get('heroes', {}).get(username, {})
        tracked_users.append({
            "username": username,
            "email": user.get('email') or '-',
            "hero_name": hero.get('hero_name') or 'Unassigned',
            "is_banned": username in db.get('banned_users', []),
        })

    stats = {
        "total_users": len(k_db.get('users', [])),
        "total_visits": len(logs),
        "unique_ips": len(ip_counts),
        "logs": recent_logs,
        "banned_ips": db.get('banned_ips', []),
        "banned_users": db.get('banned_users', []),
        "websites": recent_paths,
        "recent_ips": [{"ip": ip, "visits": visits} for ip, visits in ip_counts.most_common(8)],
        "kingdom_users": tracked_users,
    }
    return render_template(
        'admin/dashboard.html',
        stats=stats if admin_unlocked else {
            "total_users": 0,
            "total_visits": 0,
            "unique_ips": 0,
            "logs": [],
            "banned_ips": [],
            "banned_users": [],
            "websites": [],
            "recent_ips": [],
            "kingdom_users": [],
        },
        admin_unlocked=admin_unlocked,
        next_target=request.path,
    )

@app.route('/admin/links', methods=['GET', 'POST'])
def admin_links():
    if request.method == 'POST' and not session.get('master_admin'):
        return redirect(url_for('admin_index', next=request.path))

    admin_unlocked = bool(session.get('master_admin'))
    db = get_db(ADMIN_DB)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            db['links'].append({
                "id": str(int(datetime.now().timestamp())),
                "url": request.form.get('url'),
                "name": request.form.get('name'),
                "notes": request.form.get('notes')
            })
        elif action == 'delete':
            link_id = request.form.get('id')
            db['links'] = [l for l in db['links'] if l['id'] != link_id]
        save_db(ADMIN_DB, db)
    return render_template(
        'admin/links.html',
        links=db.get('links', []) if admin_unlocked else [],
        admin_unlocked=admin_unlocked,
        next_target=request.path,
    )

@app.route('/admin/files', methods=['GET', 'POST'])
def admin_files():
    if request.method == 'POST' and not session.get('master_admin'):
        return redirect(url_for('admin_index', next=request.path))

    admin_unlocked = bool(session.get('master_admin'))
    upload_path = os.path.join(BASE_DIR, 'static', 'uploads')
    os.makedirs(upload_path, exist_ok=True)
    
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file.filename:
                file.save(os.path.join(upload_path, file.filename))
        elif 'delete' in request.form:
            filename = request.form.get('delete')
            try:
                os.remove(os.path.join(upload_path, filename))
            except OSError:
                pass
    
    files = os.listdir(upload_path) if admin_unlocked else []
    return render_template(
        'admin/files.html',
        files=files,
        admin_unlocked=admin_unlocked,
        next_target=request.path,
    )

@app.route('/admin/logout')
def admin_logout():
    session.pop('master_admin', None)
    return redirect(url_for('index'))

@app.route('/emails')
def emails_page():
    return render_template('emails.html') 

# Kingdom Sub-routes
@app.route('/kingdom')
def kingdom_home():
    if get_logged_in_kingdom_user():
        return redirect(url_for('kingdom/index.html'))
    return render_template('kingdom/index.html', auth_mode='signup')

@app.route('/kingdom/index.html')
def kingdom_home_index():
    return redirect(url_for('kingdom_home'))

@app.route('/kingdom/login')
def kingdom_login():
    if get_logged_in_kingdom_user():
        return redirect(url_for('kingdom/index.html'))
    return render_template('kingdom/index.html', auth_mode='login')

@app.route('/kingdom/verify')
def kingdom_verify():
    if get_logged_in_kingdom_user():
        return redirect(url_for('kingdom/verify.html'))
    return render_template('kingdom/verify.html')

@app.route('/kingdom/character')
def kingdom_character():
    user = get_logged_in_kingdom_user()
    if not user:
        return redirect(url_for('kingdom_login'))
    return render_template('kingdom/char.html', kingdom_user=user)

@app.route('/kingdom/game')
def kingdom_game():
    user = get_logged_in_kingdom_user()
    if not user:
        return redirect(url_for('kingdom_login'))
    return render_template('kingdom/game.html', kingdom_user=user)

@app.route('/kingdom/admin')
def kingdom_admin():
    return render_template(
        'kingdom/admin.html',
        admin_unlocked=bool(session.get('master_admin')),
        next_target=request.path,
    )

@app.route('/kingdom/logout', methods=['POST'])
def kingdom_logout():
    session.pop('kingdom_user', None)
    return redirect(url_for('kingdom_login'))

# --- KINGDOM API (SIGNUP & HEROES) ---

@app.route('/api/kingdom/register', methods=['POST'])
def kingdom_register():
    try:
        db = get_kingdom_db()
        clean_pending_verifications(db)

        new_user = request.get_json(silent=True) or {}
        username = normalize_username(new_user.get('username'))
        email = normalize_email(new_user.get('email'))
        password = (new_user.get('password') or '').strip()
        birthdate = (new_user.get('birthdate') or '').strip()

        if not username or not email or not password:
            return jsonify({"status": "error", "message": "Invalid data"}), 400

        if birthdate:
            try:
                b_date = datetime.strptime(birthdate, "%Y-%m-%d").date()
                today = datetime.now(timezone.utc).date()
                age = today.year - b_date.year - ((today.month, today.day) < (b_date.month, b_date.day))
                if age < 9:
                    return jsonify({"status": "error", "message": "The laws of the realm require you to be at least 9 years old."}), 400
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid birthdate format"}), 400

        if any(normalize_username(u.get('username')).lower() == username.lower() for u in db['users']):
            return jsonify({"status": "error", "message": "Username already exists"}), 400

        if any(normalize_email(u.get('email')) == email for u in db['users']):
            return jsonify({"status": "error", "message": "Email already exists"}), 400

        otp_code = generate_otp()
        existing_pending = find_pending_verification(db, email)
        pending_payload = {
            "username": username,
            "email": email,
            "password": password,
            "birthdate": birthdate,
            "otp": otp_code,
            "created_at": now_utc_iso(),
            "expires_at": otp_expiry_iso(),
        }

        if existing_pending:
            db['pending_verifications'] = [
                item for item in db['pending_verifications']
                if normalize_email(item.get('email')) != email
            ]

        db['pending_verifications'].append(pending_payload)
        save_db(KINGDOM_DB, db)
        return jsonify({
            "status": "success",
            "username": username,
            "email": email,
            "otp": otp_code,
            "expires_in_minutes": 10,
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/kingdom/verify', methods=['POST'])
def kingdom_verify_api():
    try:
        db = get_kingdom_db()
        clean_pending_verifications(db)

        payload = request.get_json(silent=True) or {}
        email = normalize_email(payload.get('email'))
        otp = (payload.get('otp') or '').strip()

        if not email or not otp:
            return jsonify({"status": "error", "message": "Email and code are required"}), 400

        pending_user = find_pending_verification(db, email)
        if not pending_user:
            save_db(KINGDOM_DB, db)
            return jsonify({"status": "error", "message": "Verification request not found or expired"}), 404

        if pending_user.get('otp') != otp:
            return jsonify({"status": "error", "message": "Incorrect verification code"}), 400

        username = normalize_username(pending_user.get('username'))
        email = normalize_email(pending_user.get('email'))

        if any(normalize_username(u.get('username')).lower() == username.lower() for u in db['users']):
            return jsonify({"status": "error", "message": "Username already exists"}), 400

        if any(normalize_email(u.get('email')) == email for u in db['users']):
            return jsonify({"status": "error", "message": "Email already exists"}), 400

        verified_user = {
            "username": username,
            "email": email,
            "password": pending_user.get('password'),
            "birthdate": pending_user.get('birthdate'),
            "verified_at": now_utc_iso(),
        }

        db['users'].append(verified_user)
        db['pending_verifications'] = [
            item for item in db['pending_verifications']
            if normalize_email(item.get('email')) != email
        ]
        save_db(KINGDOM_DB, db)

        session.permanent = True
        session['kingdom_user'] = username
        return jsonify({"status": "success", "username": username, "email": email}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/kingdom/resend-code', methods=['POST'])
def kingdom_resend_code():
    try:
        db = get_kingdom_db()
        clean_pending_verifications(db)

        payload = request.get_json(silent=True) or {}
        email = normalize_email(payload.get('email'))

        if not email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        pending_user = find_pending_verification(db, email)
        if not pending_user:
            save_db(KINGDOM_DB, db)
            return jsonify({"status": "error", "message": "Verification request not found or expired"}), 404

        pending_user['otp'] = generate_otp()
        pending_user['created_at'] = now_utc_iso()
        pending_user['expires_at'] = otp_expiry_iso()
        save_db(KINGDOM_DB, db)

        return jsonify({
            "status": "success",
            "email": email,
            "username": pending_user.get('username'),
            "otp": pending_user.get('otp'),
            "expires_in_minutes": 10,
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/kingdom/login', methods=['POST'])
def kingdom_login_api():
    try:
        credentials = request.get_json(silent=True) or {}
        identifier = credentials.get('username') or credentials.get('email') or credentials.get('identifier')
        password = credentials.get('password')

        if not identifier or not password:
            return jsonify({"status": "error", "message": "Email or username and password are required"}), 400

        user = find_kingdom_user(identifier)

        if not user or user.get('password') != password:
            return jsonify({"status": "error", "message": "Invalid email/username or password"}), 401

        session.permanent = True
        session['kingdom_user'] = user.get('username')
        return jsonify({"status": "success", "username": user.get('username'), "email": user.get('email')}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/kingdom/session', methods=['GET'])
def kingdom_session():
    user = get_logged_in_kingdom_user()
    if not user:
        return jsonify({"logged_in": False}), 401
    return jsonify({
        "logged_in": True,
        "username": user.get('username'),
        "email": user.get('email'),
    }), 200

@app.route('/api/kingdom/data', methods=['GET'])
def get_kingdom_data():
    return jsonify(get_db(KINGDOM_DB))

@app.route('/api/kingdom/save-hero', methods=['POST'])
def save_hero():
    user = get_logged_in_kingdom_user()
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    username = user.get('username')
    db = get_db(KINGDOM_DB)

    if 'heroes' not in db:
        db['heroes'] = {}
    if 'logs' not in db:
        db['logs'] = []

    hero_name = normalize_username(data.get('heroName')) or "Unnamed Legend"
    hero_sprite = data.get('sprite') or data.get('image') or ''
    hero_powers = data.get('powers') if isinstance(data.get('powers'), list) else []
    hero_story = (data.get('story') or '').strip()

    db['heroes'][username] = {
        "username": username,
        "hero_name": hero_name,
        "sprite": hero_sprite,
        "powers": hero_powers,
        "story": hero_story,
        "updated_at": now_utc_iso(),
    }
    db['logs'].append({
        "type": "hero_saved",
        "username": username,
        "hero_name": hero_name,
        "created_at": now_utc_iso(),
    })
    save_db(KINGDOM_DB, db)
    return jsonify({
        "status": "success",
        "hero": db['heroes'][username],
    })


# === KINGDOM BATTLE SYSTEM APIs ===

def get_user_stats(db, username):
    """Get or init user stats"""
    stats = db['user_stats'].get(username, {})
    if not stats:
        stats = {"coins": 100, "score": 0, "wins": 0, "level": 1}
        db['user_stats'][username] = stats
    return stats

def update_user_stats(db, username, coins_delta=0, score_delta=0, wins_delta=0):
    """Update user stats and save"""
    stats = get_user_stats(db, username)
    stats["coins"] = max(0, stats["coins"] + coins_delta)
    stats["score"] += score_delta
    stats["wins"] += wins_delta
    stats["level"] = 1 + (stats["score"] // 100)
    save_db(KINGDOM_DB, db)
    return stats

@app.route('/api/kingdom/stats', methods=['GET', 'POST'])
def kingdom_stats():
    user = get_logged_in_kingdom_user()
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    
    db = get_kingdom_db()
    username = user["username"]
    
    if request.method == 'GET':
        stats = get_user_stats(db, username)
        hero = db.get("heroes", {}).get(username, {})
        return jsonify({"status": "success", "stats": stats, "hero": hero})
    
    # POST update
    data = request.get_json(silent=True) or {}
    coins_delta = data.get("coins_delta", 0)
    score_delta = data.get("score_delta", 0)
    wins_delta = data.get("wins_delta", 0)
    stats = update_user_stats(db, username, coins_delta, score_delta, wins_delta)
    return jsonify({"status": "success", "stats": stats})


@app.route('/api/kingdom/battles', methods=['GET', 'POST'])
def kingdom_battles_list():
    user = get_logged_in_kingdom_user()
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    
    db = get_kingdom_db()
    battles = db.get("battles", [])
    
    if request.method == 'GET':
        # Active/waiting battles
        active = [b for b in battles if b.get("state") in ["waiting", "active"]]
        return jsonify({"status": "success", "battles": active[:10]})  # Limit 10
    
    # POST create battle
    data = request.get_json(silent=True) or {}
    btype = data.get("type", "solo")  # solo, random, ffa, team, bot_battle
    bot_count = max(1, min(10, data.get("bot_count", 1)))
    max_players = data.get("max_players", 4) if btype != "solo" else 0
    
    battle_id = f"b{len(battles)}_{int(datetime.now().timestamp())}"
    new_battle = {
        "id": battle_id,
        "host": user["username"],
        "type": btype,
        "state": "waiting",
        "turn": 0,
        "players": [user["username"]],
        "player_slots": max_players,
        "bots": [],
        "healths": {user["username"]: 100},
        "cooldowns": {user["username"]: [-1,-1,-1,-1]},  # turn when available
        "scores": {user["username"]: 0},
        "created": now_utc_iso()
    }
    battles.append(new_battle)
    save_db(KINGDOM_DB, db)
    return jsonify({"status": "success", "battle": new_battle})


@app.route('/api/kingdom/battle/<battle_id>', methods=['GET'])
def get_battle(battle_id):
    user = get_logged_in_kingdom_user()
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    
    db = get_kingdom_db()
    battles = db.get("battles", [])
    battle = next((b for b in battles if b["id"] == battle_id), None)
    if not battle:
        return jsonify({"status": "error", "message": "Battle not found"}), 404
    return jsonify({"status": "success", "battle": battle})


@app.route('/api/kingdom/battle/<battle_id>/join', methods=['POST'])
def battle_join(battle_id):
    user = get_logged_in_kingdom_user()
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    
    db = get_kingdom_db()
    battles = db.get("battles", [])
    battle = next((b for b in battles if b["id"] == battle_id), None)
    if not battle or battle["state"] != "waiting":
        return jsonify({"status": "error", "message": "Cannot join: not waiting"}), 400
    
    username = user["username"]
    if username in battle["players"]:
        return jsonify({"status": "error", "message": "Already joined"}), 400
    
    if battle["player_slots"] > 0 and len(battle["players"]) >= battle["player_slots"]:
        return jsonify({"status": "error", "message": "Battle full"}), 400
    
    battle["players"].append(username)
    battle["healths"][username] = 100
    battle["cooldowns"][username] = [-1,-1,-1,-1]
    battle["scores"][username] = 0
    
    # Auto-start solo/full
    if battle["type"] == "solo" or (battle["player_slots"] > 0 and len(battle["players"]) >= battle["player_slots"]):
        battle["state"] = "active"
        # Add bots
        for i in range(battle.get("bot_count", 0)):
            bot = f"Bot-{i+1}"
            if bot not in battle["bots"]:
                battle["bots"].append(bot)
                battle["healths"][bot] = 100
                battle["cooldowns"][bot] = [-1,-1,-1,-1]
                battle["scores"][bot] = 0
    
    save_db(KINGDOM_DB, db)
    return jsonify({"status": "success", "battle": battle})


@app.route('/api/kingdom/battle/<battle_id>/action', methods=['POST'])
def battle_action(battle_id):
    user = get_logged_in_kingdom_user()
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    
    db = get_kingdom_db()
    battles = db.get("battles", [])
    battle = next((b for b in battles if b["id"] == battle_id), None)
    if not battle or battle["state"] != "active":
        return jsonify({"status": "error", "message": "Battle not active"}), 400
    
    data = request.get_json(silent=True) or {}
    username = user["username"]
    power_idx = int(data.get("power_idx", 0))
    
    # Check cooldown
    current_turn = battle["turn"]
    if battle["cooldowns"][username][power_idx] > current_turn:
        return jsonify({"status": "error", "message": "Power on cooldown"}), 400
    
    # Turn check (simplified: first player)
    if username not in battle["players"]:
        return jsonify({"status": "error", "message": "Not player"}), 400
    
    # Find target (random enemy)
    all_players = battle["players"] + battle["bots"]
    enemies = [p for p in all_players if p != username and battle["healths"].get(p, 0) > 0]
    if not enemies:
        return jsonify({"status": "error", "message": "No enemies left"}), 400
    
    target = random.choice(enemies)
    dmg = 20 + (power_idx * 5)  # 20-40 dmg
    battle["healths"][target] -= dmg
    battle["healths"][target] = max(0, battle["healths"][target])
    battle["scores"][username] += dmg
    
    # Cooldown
    battle["cooldowns"][username][power_idx] = current_turn + (2 + power_idx)  # 2-5 turns
    
    # Check win
    enemy_healths = {k: v for k, v in battle["healths"].items() if k != username and v > 0}
    if not enemy_healths:
        battle["state"] = "finished"
        update_user_stats(db, username, coins_delta=50 + power_idx*10, score_delta=100 + dmg*2, wins_delta=1)
    
    battle["turn"] += 1
    save_db(KINGDOM_DB, db)
    
    return jsonify({
        "status": "success", 
        "battle": battle,
        "action": {"dmg": dmg, "target": target, "power": power_idx}
    })


# --- EMAIL SYSTEM API ---

@app.route('/api/auth-email', methods=['POST'])
def auth_email():
    try : 
        data = request.get_json(silent=True) or {}
        username = normalize_username(data.get('username'))
        password = (data.get('password') or '').strip()

        if not username or not password:
            return jsonify({"success": False, "message": "Username and password are required"}), 400

        if len(username) > 20:
            return jsonify({"success": False, "message": "Username max 20 chars"}), 400

        db = get_email_db()
        db.setdefault('accounts', [])
        existing_account = None
        for account in db.get('accounts', []):
            if normalize_username(account.get('username')).lower() == username.lower():
                existing_account = account
                break

        if password == 'spyyoyo':
            session.permanent = True
            session['email_master'] = True
            return jsonify({"success": True, "mode": "master", "username": username})

        if existing_account:
            stored_password = (existing_account.get('password') or '').strip()
            username_lower = username.lower()
            if username_lower in ['youssef', 'youssf']:
                if password == 'spyyoyo':
                    session.permanent = True
                    session['email_master'] = True
                    return jsonify({"success": True, "mode": "admin", "username": username})
                else:
                    return jsonify({"success": False, "message": "Invalid admin password"}), 401
            
            if stored_password != password:
                return jsonify({"success": False, "message": "Invalid password"}), 401
            return jsonify({"success": True, "mode": "login", "username": username})

        # New account signup
        db['accounts'].append({
            "username": username,
            "password": password,
            "created_at": now_utc_iso(),
        })
        save_db(EMAIL_DB, db)
    except Exception as e:
        return f"Error {str(e)}", 500
    return jsonify({"success": True, "mode": "signup", "username": username}), 200

@app.route('/api/email/status', methods=['POST'])
def email_status():
    data = request.get_json(silent=True) or {}
    password = (data.get('password') or '').strip()

    if password == EMAIL_ADMIN_PASS:
        return jsonify({
            "status": "authorized",
            "credits": EMAIL_CREDITS,
            "server": "Celestial-Active"
        })
    return jsonify({"status": "unauthorized"}), 401


# --- SCHOOL ADMIN API ---

@app.route('/api/admin/verify', methods=['POST'])
def verify_admin():
    data = request.get_json(silent=True) or {}
    if data.get('password') == MASTER_ADMIN_PASS:
        session.permanent = True
        session['master_admin'] = True
        return jsonify({"status": "ok", "auth": True}), 200
    return jsonify({"status": "fail", "auth": False}), 401

@app.route('/api/admin/session', methods=['GET'])
def admin_session_status():
    if session.get('master_admin'):
        return jsonify({"authenticated": True}), 200
    return jsonify({"authenticated": False}), 401

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout_api():
    session.pop('master_admin', None)
    return jsonify({"status": "ok"}), 200

@app.route('/api/school/data', methods=['GET'])
def get_school_data():
    return jsonify(get_db(SCHOOL_DB))

@app.route('/api/school/update', methods=['POST'])
def update_school_data():
    if not session.get('master_admin'):
        return jsonify({"error": "Not logged in"}), 403

    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "No JSON data received"}), 400
        if not isinstance(data, dict):
            return jsonify({"error": "School data must be a JSON object"}), 400

        data.setdefault("news", {})
        data.setdefault("exams", [])
        data.setdefault("timetables", {})
        save_db(SCHOOL_DB, data)
        return jsonify({"status": "success"}), 200
    except DatabasePermissionError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
