from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import mysql.connector
import os
import uuid
from functools import wraps

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Enable CORS so frontend can run on a separate port/server (e.g. live-server on 8080 while backend on 5000)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'png', 'jpg', 'jpeg', 'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── DB CONFIG ──────────────────────────────────────────────
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 25060)),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'ssl_ca': 'ca.pem',          # Important for Aiven
    'ssl_verify_cert': True
}

# Production settings
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True

def get_db():
    config = DB_CONFIG.copy()
    if 'ssl_ca' in config and os.path.exists(config['ssl_ca']):
        config['ssl'] = {'ca': config['ssl_ca']}
    return mysql.connector.connect(**{k: v for k, v in config.items() if k != 'ssl_ca'})


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── AUTH ───────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        cur.close(); db.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id']  = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        error = 'Invalid email or password.'
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not username or not email or not password:
            error = 'All fields are required.'
        else:
            db = get_db(); cur = db.cursor(dictionary=True)
            cur.execute('SELECT id FROM users WHERE email = %s OR username = %s', (email, username))
            if cur.fetchone():
                error = 'Email or username already taken.'
            else:
                cur.execute('INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)',
                            (username, email, generate_password_hash(password)))
                db.commit()
                cur.close(); db.close()
                return redirect(url_for('login', registered=1))
            cur.close(); db.close()
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── DASHBOARD ──────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session['username'])

# ── API: MY CHANNELS ───────────────────────────────────────
@app.route('/api/my-channels')
@login_required
def api_my_channels():
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('''
        SELECT c.id, c.name, c.channel_code, c.is_public, c.max_members,
               cm.role,
               (SELECT COUNT(*) FROM channel_members WHERE channel_id = c.id) AS member_count,
               (SELECT COUNT(*) FROM documents        WHERE channel_id = c.id) AS doc_count,
               c.created_at
        FROM channels c
        JOIN channel_members cm ON c.id = cm.channel_id
        WHERE cm.user_id = %s
        ORDER BY c.created_at DESC
    ''', (session['user_id'],))
    rows = cur.fetchall()
    cur.close(); db.close()
    for r in rows:
        r['created_at'] = r['created_at'].strftime('%d %b %Y') if r['created_at'] else ''
        r['is_public'] = bool(r['is_public'])
    return jsonify(rows)

# ── API: SEARCH CHANNELS (NOW SUPPORTS CODE OR NAME) ───────
@app.route('/api/search-channels')
@login_required
def api_search_channels():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': 'Enter a search query (code or name).'}), 400

    db = get_db(); cur = db.cursor(dictionary=True)
    # Search by exact code OR partial name match
    cur.execute('''
        SELECT c.*, u.username AS creator_name,
               (SELECT COUNT(*) FROM channel_members WHERE channel_id = c.id) AS member_count
        FROM channels c
        JOIN users u ON c.creator_id = u.id
        WHERE c.channel_code = %s OR c.name LIKE %s
        LIMIT 20
    ''', (q.upper(), f'%{q}%'))
    chs = cur.fetchall()

    results = []
    for ch in chs:
        cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s',
                    (ch['id'], session['user_id']))
        mem = cur.fetchone()
        cur.execute("SELECT id FROM join_requests WHERE channel_id=%s AND user_id=%s AND status='pending'",
                    (ch['id'], session['user_id']))
        pending = cur.fetchone()

        ch['is_member']          = mem is not None
        ch['membership_role']    = mem['role'] if mem else None
        ch['has_pending_request']= pending is not None
        ch['is_public']          = bool(ch['is_public'])
        ch['created_at']         = ch['created_at'].strftime('%d %b %Y') if ch['created_at'] else ''
        results.append(ch)

    cur.close(); db.close()
    return jsonify(results)

# ── API: JOIN CHANNEL ──────────────────────────────────────
@app.route('/api/join-channel', methods=['POST'])
@login_required
def api_join_channel():
    channel_id = request.json.get('channel_id')
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT * FROM channels WHERE id = %s', (channel_id,))
    ch = cur.fetchone()
    if not ch:
        cur.close(); db.close()
        return jsonify({'error': 'Channel not found.'}), 404

    cur.execute('SELECT COUNT(*) AS cnt FROM channel_members WHERE channel_id=%s', (channel_id,))
    cnt = cur.fetchone()['cnt']
    if ch['max_members'] and cnt >= ch['max_members']:
        cur.close(); db.close()
        return jsonify({'error': 'Channel is full.'}), 400

    if ch['is_public']:
        try:
            cur.execute("INSERT INTO channel_members (channel_id, user_id, role) VALUES (%s, %s, 'member')",
                        (channel_id, session['user_id']))
            db.commit()
        except Exception:
            pass
        cur.close(); db.close()
        return jsonify({'success': True, 'message': 'You joined the channel!'})
    else:
        cur.execute("SELECT id FROM join_requests WHERE channel_id=%s AND user_id=%s AND status='pending'",
                    (channel_id, session['user_id']))
        if cur.fetchone():
            cur.close(); db.close()
            return jsonify({'error': 'Request already pending.'}), 400
        cur.execute("INSERT INTO join_requests (channel_id, user_id, status) VALUES (%s, %s, 'pending')",
                    (channel_id, session['user_id']))
        db.commit()
        cur.close(); db.close()
        return jsonify({'success': True, 'message': 'Join request sent to admin!'})

# ── API: CREATE CHANNEL ────────────────────────────────────
@app.route('/api/create-channel', methods=['POST'])
@login_required
def api_create_channel():
    data        = request.json
    name        = data.get('name', '').strip()
    is_public   = data.get('is_public', True)
    max_members = data.get('max_members') or None

    if not name:
        return jsonify({'error': 'Channel name is required.'}), 400

    db = get_db(); cur = db.cursor(dictionary=True)
    while True:
        code = str(uuid.uuid4())[:8].upper()
        cur.execute('SELECT id FROM channels WHERE channel_code=%s', (code,))
        if not cur.fetchone():
            break

    cur.execute('''
        INSERT INTO channels (name, channel_code, is_public, max_members, creator_id)
        VALUES (%s, %s, %s, %s, %s)
    ''', (name, code, is_public, max_members, session['user_id']))
    cid = cur.lastrowid
    cur.execute("INSERT INTO channel_members (channel_id, user_id, role) VALUES (%s, %s, 'admin')",
                (cid, session['user_id']))
    db.commit()
    cur.close(); db.close()
    return jsonify({'success': True, 'channel_id': cid, 'channel_code': code})

# ── CHANNEL PAGE ───────────────────────────────────────────
@app.route('/channel/<int:channel_id>')
@login_required
def channel_view(channel_id):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s',
                (channel_id, session['user_id']))
    mem = cur.fetchone()
    if not mem:
        cur.close(); db.close()
        return redirect(url_for('dashboard'))
    cur.execute('SELECT * FROM channels WHERE id=%s', (channel_id,))
    ch = cur.fetchone()
    cur.close(); db.close()
    return render_template('channel.html',
                           channel=ch,
                           role=mem['role'],
                           username=session['username'],
                           user_id=session['user_id'])

# ── API: DOCUMENTS ─────────────────────────────────────────
@app.route('/api/channel/<int:cid>/documents')
@login_required
def api_get_documents(cid):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s',
                (cid, session['user_id']))
    if not cur.fetchone():
        cur.close(); db.close()
        return jsonify({'error': 'Unauthorized'}), 403

    cur.execute('''
        SELECT d.id, d.filename, d.filepath, d.filetype, d.description, d.uploaded_at,
               u.username AS uploader_name,
               (SELECT COUNT(*)          FROM reactions WHERE document_id=d.id) AS reaction_count,
               (SELECT reaction_type     FROM reactions WHERE document_id=d.id AND user_id=%s LIMIT 1) AS user_reaction
        FROM documents d
        JOIN users u ON d.uploaded_by = u.id
        WHERE d.channel_id = %s
        ORDER BY d.uploaded_at DESC
    ''', (session['user_id'], cid))
    docs = cur.fetchall()
    cur.close(); db.close()
    for d in docs:
        d['uploaded_at'] = d['uploaded_at'].strftime('%d %b %Y, %H:%M') if d['uploaded_at'] else ''
    return jsonify(docs)

# ── API: UPLOAD ────────────────────────────────────────────
@app.route('/api/channel/<int:cid>/upload', methods=['POST'])
@login_required
def api_upload(cid):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s',
                (cid, session['user_id']))
    mem = cur.fetchone()
    if not mem or mem['role'] != 'admin':
        cur.close(); db.close()
        return jsonify({'error': 'Only admins can upload documents.'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided.'}), 400
    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed.'}), 400

    original  = secure_filename(file.filename)
    unique_fn = f"{uuid.uuid4().hex}_{original}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_fn))
    filetype    = original.rsplit('.', 1)[1].lower()
    description = request.form.get('description', '').strip() or None

    cur.execute('''
        INSERT INTO documents (channel_id, uploaded_by, filename, filepath, filetype, description)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (cid, session['user_id'], original, f'uploads/{unique_fn}', filetype, description))
    db.commit()
    cur.close(); db.close()
    return jsonify({'success': True})

# ── API: REACT ─────────────────────────────────────────────
@app.route('/api/document/<int:did>/react', methods=['POST'])
@login_required
def api_react(did):
    emoji = request.json.get('reaction', '👍')
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT id, reaction_type FROM reactions WHERE document_id=%s AND user_id=%s',
                (did, session['user_id']))
    ex = cur.fetchone()
    if ex:
        if ex['reaction_type'] == emoji:
            cur.execute('DELETE FROM reactions WHERE id=%s', (ex['id'],))
        else:
            cur.execute('UPDATE reactions SET reaction_type=%s WHERE id=%s', (emoji, ex['id']))
    else:
        cur.execute('INSERT INTO reactions (document_id, user_id, reaction_type) VALUES (%s,%s,%s)',
                    (did, session['user_id'], emoji))
    db.commit()
    cur.execute('SELECT reaction_type, COUNT(*) AS cnt FROM reactions WHERE document_id=%s GROUP BY reaction_type', (did,))
    counts = {r['reaction_type']: r['cnt'] for r in cur.fetchall()}
    cur.execute('SELECT reaction_type FROM reactions WHERE document_id=%s AND user_id=%s', (did, session['user_id']))
    ur = cur.fetchone()
    cur.close(); db.close()
    return jsonify({'success': True, 'counts': counts, 'user_reaction': ur['reaction_type'] if ur else None})

# ── NEW: REMOVE ADMIN PERMISSION (DEMOTE) ─────────────────
@app.route('/api/channel/<int:cid>/demote-admin', methods=['POST'])
@login_required
def api_demote_admin(cid):
    target = request.json.get('user_id')
    if not target:
        return jsonify({'error': 'User ID required.'}), 400
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s', (cid, session['user_id']))
    mem = cur.fetchone()
    if not mem or mem['role'] != 'admin':
        cur.close(); db.close()
        return jsonify({'error': 'Unauthorized'}), 403
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s', (cid, target))
    tmem = cur.fetchone()
    if not tmem or tmem['role'] != 'admin':
        cur.close(); db.close()
        return jsonify({'error': 'Target is not an admin.'}), 400
    if target == session['user_id']:
        cur.close(); db.close()
        return jsonify({'error': 'Cannot demote yourself.'}), 400
    cur.execute("SELECT COUNT(*) AS cnt FROM channel_members WHERE channel_id=%s AND role='admin'", (cid,))
    if cur.fetchone()['cnt'] <= 1:
        cur.close(); db.close()
        return jsonify({'error': 'Cannot demote the last admin.'}), 400
    cur.execute("UPDATE channel_members SET role='member' WHERE channel_id=%s AND user_id=%s", (cid, target))
    db.commit()
    cur.close(); db.close()
    return jsonify({'success': True})

# ── NEW: REMOVE MEMBER ─────────────────────────────────────
@app.route('/api/channel/<int:cid>/remove-member', methods=['POST'])
@login_required
def api_remove_member(cid):
    target = request.json.get('user_id')
    if not target:
        return jsonify({'error': 'User ID required.'}), 400
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s', (cid, session['user_id']))
    mem = cur.fetchone()
    if not mem or mem['role'] != 'admin':
        cur.close(); db.close()
        return jsonify({'error': 'Admin only'}), 403
    if target == session['user_id']:
        cur.close(); db.close()
        return jsonify({'error': 'Use "Exit Channel" to leave.'}), 400
    cur.execute('DELETE FROM channel_members WHERE channel_id=%s AND user_id=%s', (cid, target))
    db.commit()
    cur.close(); db.close()
    return jsonify({'success': True})

# ── NEW: EXIT / LEAVE CHANNEL ─────────────────────────────
@app.route('/api/channel/<int:cid>/leave', methods=['POST'])
@login_required
def api_leave_channel(cid):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s', (cid, session['user_id']))
    mem = cur.fetchone()
    if not mem:
        cur.close(); db.close()
        return jsonify({'error': 'Not a member.'}), 400
    if mem['role'] == 'admin':
        cur.execute("SELECT COUNT(*) AS cnt FROM channel_members WHERE channel_id=%s AND role='admin'", (cid,))
        if cur.fetchone()['cnt'] <= 1:
            cur.close(); db.close()
            return jsonify({'error': 'Cannot leave as the last admin. Demote another admin first.'}), 400
    cur.execute('DELETE FROM channel_members WHERE channel_id=%s AND user_id=%s', (cid, session['user_id']))
    db.commit()
    cur.close(); db.close()
    return jsonify({'success': True, 'message': 'You have left the channel.'})

# ── NEW: DELETE DOCUMENT ───────────────────────────────────
@app.route('/api/document/<int:did>/delete', methods=['POST'])
@login_required
def api_delete_document(did):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT channel_id, filepath FROM documents WHERE id=%s', (did,))
    doc = cur.fetchone()
    if not doc:
        cur.close(); db.close()
        return jsonify({'error': 'Document not found.'}), 404
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s', (doc['channel_id'], session['user_id']))
    mem = cur.fetchone()
    if not mem or mem['role'] != 'admin':
        cur.close(); db.close()
        return jsonify({'error': 'Admin only'}), 403
    # Delete physical file
    file_path = os.path.join(app.root_path, 'static', doc['filepath'])
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except:
            pass
    cur.execute('DELETE FROM reactions WHERE document_id=%s', (did,))
    cur.execute('DELETE FROM documents WHERE id=%s', (did,))
    db.commit()
    cur.close(); db.close()
    return jsonify({'success': True})

# ── API: MEMBERS ───────────────────────────────────────────
@app.route('/api/channel/<int:cid>/members')
@login_required
def api_members(cid):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s',
                (cid, session['user_id']))
    mem = cur.fetchone()
    if not mem or mem['role'] != 'admin':
        cur.close(); db.close()
        return jsonify({'error': 'Admin only'}), 403
    cur.execute('''
        SELECT u.id, u.username, u.email, cm.role, cm.joined_at
        FROM channel_members cm
        JOIN users u ON cm.user_id = u.id
        WHERE cm.channel_id = %s
        ORDER BY cm.role='admin' DESC, cm.joined_at
    ''', (cid,))
    rows = cur.fetchall()
    cur.close(); db.close()
    for r in rows:
        r['joined_at'] = r['joined_at'].strftime('%d %b %Y') if r['joined_at'] else ''
    return jsonify(rows)

@app.route('/api/channel/<int:cid>/make-admin', methods=['POST'])
@login_required
def api_make_admin(cid):
    target = request.json.get('user_id')
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s',
                (cid, session['user_id']))
    mem = cur.fetchone()
    if not mem or mem['role'] != 'admin':
        cur.close(); db.close()
        return jsonify({'error': 'Unauthorized'}), 403
    cur.execute("UPDATE channel_members SET role='admin' WHERE channel_id=%s AND user_id=%s", (cid, target))
    db.commit()
    cur.close(); db.close()
    return jsonify({'success': True})

# ── API: JOIN REQUESTS ─────────────────────────────────────
@app.route('/api/channel/<int:cid>/requests')
@login_required
def api_requests(cid):
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s',
                (cid, session['user_id']))
    mem = cur.fetchone()
    if not mem or mem['role'] != 'admin':
        cur.close(); db.close()
        return jsonify({'error': 'Admin only'}), 403
    cur.execute('''
        SELECT jr.id, u.username, u.email, jr.created_at
        FROM join_requests jr
        JOIN users u ON jr.user_id = u.id
        WHERE jr.channel_id=%s AND jr.status='pending'
        ORDER BY jr.created_at
    ''', (cid,))
    rows = cur.fetchall()
    cur.close(); db.close()
    for r in rows:
        r['created_at'] = r['created_at'].strftime('%d %b %Y') if r['created_at'] else ''
    return jsonify(rows)

@app.route('/api/channel/<int:cid>/handle-request', methods=['POST'])
@login_required
def api_handle_request(cid):
    data       = request.json
    request_id = data.get('request_id')
    action     = data.get('action')
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT role FROM channel_members WHERE channel_id=%s AND user_id=%s',
                (cid, session['user_id']))
    mem = cur.fetchone()
    if not mem or mem['role'] != 'admin':
        cur.close(); db.close()
        return jsonify({'error': 'Unauthorized'}), 403
    cur.execute('SELECT * FROM join_requests WHERE id=%s', (request_id,))
    req = cur.fetchone()
    if not req:
        cur.close(); db.close()
        return jsonify({'error': 'Request not found'}), 404
    if action == 'approve':
        try:
            cur.execute("INSERT INTO channel_members (channel_id, user_id, role) VALUES (%s,%s,'member')",
                        (cid, req['user_id']))
        except Exception:
            pass
        cur.execute("UPDATE join_requests SET status='approved' WHERE id=%s", (request_id,))
    else:
        cur.execute("UPDATE join_requests SET status='rejected' WHERE id=%s", (request_id,))
    db.commit()
    cur.close(); db.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, port=5000)