# -*- coding: utf-8 -*-
import os
import random
import shutil # Folder delete panna thevai
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
try:
    from flask_mail import Mail, Message
except ImportError:
    Mail = None; Message = None
    print("\nWARNING: Flask-Mail not installed. Email features won't work.\nRun: pip install Flask-Mail\n")
try:
    from itsdangerous import URLSafeTimedSerializer
except ImportError:
    URLSafeTimedSerializer = None
    print("\nWARNING: itsdangerous not installed. Password reset won't work.\nRun: pip install itsdangerous\n")
from urllib.parse import urlparse, parse_qs
from werkzeug.utils import secure_filename
from functools import wraps
from sqlalchemy import extract

# --- App Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-strong-secret-key-replace-me-123456789')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///../instance/church.db') # Render-ku
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# --- Flask-Mail Configuration ---
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'True').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', ('CSI Ulaga Ratchagar Aalayam', app.config['MAIL_USERNAME']))

mail = Mail(app) if Mail else None
s = URLSafeTimedSerializer(app.config['SECRET_KEY']) if URLSafeTimedSerializer else None

# --- Gallery Upload Configuration ---
UPLOAD_FOLDER = os.path.join(app.static_folder, 'images', 'gallery')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return self.password_hash and check_password_hash(self.password_hash, password)

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(50), default='Member', nullable=False)
    join_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    dob = db.Column(db.Date, nullable=True)
    marriage_date = db.Column(db.Date, nullable=True)
    Baptism_date = db.Column(db.Date, nullable=True)
    Confirmation_date = db.Column(db.Date, nullable=True)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(150), default='Church Auditorium', nullable=False)

class Sermon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    preacher = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    youtube_embed_url = db.Column(db.String(255), nullable=True)

# === VideoClip MODEL DELETE PANNITOM ===

class PrayerRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    message = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_answered = db.Column(db.Boolean, default=False, nullable=False)

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    message = db.Column(db.String(255), nullable=False)

class WeeklyService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(100), nullable=False)
    timing = db.Column(db.String(100), nullable=False)
    display_order = db.Column(db.Integer, default=0)

class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    reason = db.Column(db.String(150), nullable=True)
    method = db.Column(db.String(50), nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

# --- Helper Functions ---
def convert_to_embed_url(url_str): # Video link-ku ithu theva
    if not url_str: return None
    try:
        if not url_str.startswith(('http://', 'https://')): url_str = 'https://' + url_str
        parsed_url = urlparse(url_str); video_id = None; hostname = parsed_url.hostname.lower() if parsed_url.hostname else ''
        if "youtube.com" in hostname:
            if parsed_url.path == "/watch": video_id = parse_qs(parsed_url.query).get("v", [None])[0]
            elif parsed_url.path.startswith("/embed/"): video_id = parsed_url.path.split('/embed/')[1].split('/')[0].split('?')[0]
            elif parsed_url.path.startswith("/shorts/"): video_id = parsed_url.path.split('/shorts/')[1].split('/')[0].split('?')[0]
        elif "youtu.be" in hostname: video_id = parsed_url.path[1:].split('/')[0].split('?')[0]
        elif "vimeo.com" in hostname:
            video_id = parsed_url.path.split('/')[-1]
            if video_id.isdigit(): return f"https://player.vimeo.com/video/{video_id}"
        
        if video_id and len(video_id) >= 11 and all(c.isalnum() or c in ['-', '_'] for c in video_id): return f"https://www.youtube.com/embed/{video_id}"
        elif 'player.vimeo.com' in url_str: return url_str
        else: print(f"Invalid YT/Vimeo ID: {url_str}"); return None
    except Exception as e: print(f"YT/Vimeo Parse Error '{url_str}': {e}"); return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_daily_bible_verse():
    verses = [
        {"ref": "John 3:16", "text": "For God so loved the world that he gave his one and only Son, that whoever believes in him shall not perish but have eternal life."},
        {"ref": "Philippians 4:13", "text": "I can do all this through him who gives me strength."},
        {"ref": "Proverbs 3:5-6", "text": "Trust in the LORD with all your heart and lean not on your own understanding; in all your ways submit to him, and he will make your paths straight."}
    ]
    return random.choice(verses) if verses else {"ref": "Info", "text": "Verse unavailable."}

def get_birthday_verse():
    verses = [{"ref": "Numbers 6:24-26", "text": "The LORD bless you and keep you..."}, {"ref": "Psalm 118:24", "text": "This is the day the LORD has made..."}]
    return random.choice(verses) if verses else None

def get_marriage_verse():
    verses = [{"ref": "1 Corinthians 13:4-7", "text": "Love is patient, love is kind..."}, {"ref": "Ephesians 4:2-3", "text": "Be completely humble and gentle..."}]
    return random.choice(verses) if verses else None

def parse_date_or_none(date_str):
    if not date_str: return None
    try: return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError: return None

def log_activity(message):
    try:
        if db.inspect(db.engine).has_table('activity_log'):
            log = ActivityLog(message=message)
            db.session.add(log); db.session.commit()
        else:
            print(f"Log Info: ActivityLog table not found. Skipping log: {message}")
    except Exception as e: db.session.rollback(); print(f"!!! Log Error: {e}")

def get_gallery_data():
    gallery_data = []
    base_path = app.config.get('UPLOAD_FOLDER')
    if not base_path: print("UPLOAD_FOLDER error."); return []
    if not os.path.exists(base_path):
        try: os.makedirs(base_path, exist_ok=True)
        except OSError as e: print(f"Gallery path creation error: {e}"); return []
    try:
        main_folders = sorted([d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))], reverse=True)
        for main_folder in main_folders:
            main_folder_path = os.path.join(base_path, main_folder)
            event_folders_data = []
            sub_folders = sorted([d for d in os.listdir(main_folder_path) if os.path.isdir(os.path.join(main_folder_path, d))])
            for sub_folder in sub_folders:
                sub_folder_path = os.path.join(main_folder_path, sub_folder)
                images = sorted([f for f in os.listdir(sub_folder_path) if os.path.isfile(os.path.join(sub_folder_path, f)) and allowed_file(f)])
                if images:
                    event_folders_data.append({'event_name': sub_folder, 'images': images})
            if event_folders_data:
                gallery_data.append({'main_folder': main_folder, 'events': event_folders_data})
    except Exception as e: print(f"Gallery read error: {e}"); flash('Error loading gallery.', 'warning')
    return gallery_data

# --- PWA Routes ---
@app.route('/manifest.json')
def manifest(): return send_from_directory('static', 'manifest.json')

@app.route('/service-worker.js')
def service_worker():
    response = send_from_directory('static', 'service-worker.js')
    response.headers['Cache-Control'] = 'no-cache'; response.headers['Pragma'] = 'no-cache'; response.headers['Expires'] = '0'
    return response

# --- Frontend Routes ---
@app.route('/')
def home():
    active_notices = []; birthday_members_today = []; recent_activity = []; marriage_members_today = []
    birthday_verse = None; marriage_verse = None
    try:
        if db.inspect(db.engine).has_table('notice'):
            active_notices = Notice.query.filter_by(is_active=True).order_by(Notice.created_at.desc()).limit(3).all()
        today = datetime.utcnow().date()
        if db.inspect(db.engine).has_table('member') and hasattr(Member, 'dob') and Member.dob is not None:
             birthday_members_today = Member.query.filter(extract('month', Member.dob) == today.month, extract('day', Member.dob) == today.day).all()
             if birthday_members_today: birthday_verse = get_birthday_verse()
        if db.inspect(db.engine).has_table('member') and hasattr(Member, 'marriage_date') and Member.marriage_date is not None:
            marriage_members_today = Member.query.filter(extract('month', Member.marriage_date) == today.month, extract('day', Member.marriage_date) == today.day).all()
            if marriage_members_today: marriage_verse = get_marriage_verse()
        if db.inspect(db.engine).has_table('activity_log'):
             recent_activity = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(5).all()
    except Exception as e: print(f"Home page data error: {e}")
    return render_template('index.html', 
                           verse=get_daily_bible_verse(), 
                           notices=active_notices, 
                           birthday_members=birthday_members_today, 
                           birthday_verse=birthday_verse,
                           marriage_members=marriage_members_today,
                           marriage_verse=marriage_verse,
                           activities=recent_activity)

@app.route('/about')
def about(): return render_template('about.html')

@app.route('/services')
def services():
    upcoming_events = []; weekly_services = []
    try:
        now = datetime.utcnow()
        if db.inspect(db.engine).has_table('event'):
            upcoming_events = Event.query.filter(Event.date >= now).order_by(Event.date.asc()).all()
        if db.inspect(db.engine).has_table('weekly_service'):
            weekly_services = WeeklyService.query.order_by(WeeklyService.display_order, WeeklyService.service_name).all()
    except Exception as e: print(f"Services fetch error: {e}"); flash('Error loading schedule.', 'warning')
    return render_template('services.html', events=upcoming_events, weekly_services=weekly_services)

@app.route('/sermons')
def sermons():
    try: sermons = Sermon.query.order_by(Sermon.date.desc()).all()
    except Exception as e: print(f"Sermons fetch error: {e}"); sermons = []; flash('Error loading sermons.', 'warning')
    return render_template('sermons.html', sermons=sermons)

@app.route('/prayer', methods=['GET', 'POST'])
def prayer():
    if request.method == 'POST':
        try:
            name=request.form.get('name'); message=request.form.get('message')
            if not name or not message: flash('Name/message required.', 'warning'); return render_template('prayer.html')
            new_req = PrayerRequest(name=name, email=request.form.get('email'), message=message)
            db.session.add(new_req); db.session.commit()
            flash('Request submitted!', 'success'); return redirect(url_for('prayer'))
        except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Prayer error: {e}")
    return render_template('prayer.html')

@app.route('/donate')
def donate(): return render_template('donate.html')

@app.route('/submit-donation-info', methods=['POST'])
def submit_donation_info():
    try:
        name = request.form.get('donor_name')
        if not name: flash('Please enter your name.', 'warning'); return redirect(url_for('donate'))
        reason = request.form.get('donation_reason')
        method = request.form.get('donation_method')
        new_info = Donation(name=name, reason=reason, method=method)
        db.session.add(new_info); db.session.commit()
        flash(f'Thank you, {name}, for submitting your info!', 'success')
        log_activity(f"Donation info: Name={name}, Reason={reason}, Method={method}")
    except Exception as e: db.session.rollback(); flash(f'Error submitting info: {e}', 'danger'); print(f"Donation info error: {e}")
    return redirect(url_for('donate'))

@app.route('/gallery')
def gallery():
    gallery_data = get_gallery_data()
    # === VIDEO CLIP CODE DELETE PANNITOM ===
    return render_template('gallery.html', gallery_data=gallery_data)

@app.route('/contact')
def contact(): return render_template('contact.html')

@app.route('/directory')
def member_directory():
    try: members = Member.query.order_by(Member.name).all()
    except Exception as e: members = []; flash(f'Error: {e}', 'danger'); print(f"Directory error: {e}")
    return render_template('directory.html', members=members)

# --- Admin Authentication & Decorator ---
def is_admin():
    admin_id = session.get('admin_id')
    if admin_id and db.inspect(db.engine).has_table('user'):
        return User.query.get(admin_id) is not None
    return False

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin(): flash('Login required.', 'warning'); return redirect(url_for('admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# --- Admin Routes ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if is_admin(): return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username'); password = request.form.get('password')
        if not username or not password: flash('Username/password required.', 'warning'); return render_template('admin/login.html')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['admin_id'] = user.id; session.permanent = True
            flash(f'Welcome, {user.username}!', 'success')
            next_url = request.args.get('next'); return redirect(next_url or url_for('admin_dashboard'))
        else: flash('Invalid credentials.', 'danger')
    return render_template('admin/login.html')

@app.route('/admin/logout')
@admin_required
def admin_logout():
    session.pop('admin_id', None); flash('Logged out.', 'info'); return redirect(url_for('admin_login'))

@app.route('/admin/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if not s or not mail: flash('Password reset unavailable.', 'warning'); return redirect(url_for('admin_login'))
    if is_admin(): return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        if not email: flash('Email required.', 'warning'); return render_template('admin/forgot_password.html')
        user = User.query.filter_by(email=email).first()
        flash('If account exists, reset link sent.', 'info')
        if user:
            try:
                token = s.dumps(email, salt='password-reset-salt')
                reset_url = url_for('reset_password', token=token, _external=True)
                msg = Message('Password Reset - CSI URA Church', recipients=[email])
                msg.body = f'Hello {user.username},\n\nClick link to reset password (expires 1 hour):\n{reset_url}\n\nIgnore if not requested.\n\nCSI URA Admin'
                mail.send(msg)
            except Exception as e: print(f"Mail error: {e}"); flash('Error sending email.', 'danger')
        return redirect(url_for('admin_login'))
    return render_template('admin/forgot_password.html')

@app.route('/admin/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if not s: flash('Password reset unavailable.', 'warning'); return redirect(url_for('admin_login'))
    if is_admin(): return redirect(url_for('admin_dashboard'))
    try: email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except: flash('Link invalid/expired.', 'danger'); return redirect(url_for('admin_login'))
    user = User.query.filter_by(email=email).first()
    if not user: flash('User not found.', 'danger'); return redirect(url_for('admin_login'))
    if request.method == 'POST':
        password = request.form.get('password'); confirm = request.form.get('confirm_password')
        if not password or len(password) < 8: flash('Password >= 8 chars.', 'warning'); return render_template('admin/reset_password.html', token=token)
        if password != confirm: flash('Passwords mismatch.', 'warning'); return render_template('admin/reset_password.html', token=token)
        user.set_password(password)
        try: db.session.commit(); flash('Password updated!', 'success'); return redirect(url_for('admin_login'))
        except Exception as e: db.session.rollback(); flash(f'DB error: {e}', 'danger'); print(f"PW Update error: {e}")
    return render_template('admin/reset_password.html', token=token)

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    try:
        counts = {'member': Member.query.count(), 'event': Event.query.count(), 'sermon': Sermon.query.count(), 'prayer': PrayerRequest.query.filter_by(is_answered=False).count()}
    except Exception as e: print(f"Dashboard error: {e}"); flash(f'Error: {e}', 'danger'); counts = {'member': 'N/A', 'event': 'N/A', 'sermon': 'N/A', 'prayer': 'N/A'}
    return render_template('admin/dashboard.html', member_count=counts['member'], event_count=counts['event'], sermon_count=counts['sermon'], prayer_count=counts['prayer'])

# --- Admin CRUD Operations ---
@app.route('/admin/events')
@admin_required
def admin_events():
    try: events = Event.query.order_by(Event.date.desc()).all()
    except Exception as e: events = []; flash(f'Error: {e}', 'danger'); print(f"Events load error: {e}")
    return render_template('admin/events.html', events=events)

@app.route('/admin/events/add', methods=['POST'])
@admin_required
def add_event():
    try:
        title=request.form.get('title'); date_str=request.form.get('date')
        if not title or not date_str: flash('Title/date required.', 'warning'); return redirect(url_for('admin_events'))
        date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        new = Event(title=title, description=request.form.get('description'), date=date, location=request.form.get('location', 'Church Auditorium'))
        db.session.add(new); db.session.commit(); flash('Event added!', 'success')
        log_activity(f"Event added: '{title}'")
    except ValueError: flash('Invalid date format.', 'danger')
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Add event error: {e}")
    return redirect(url_for('admin_events'))

@app.route('/admin/events/edit/<int:id>', methods=['POST'])
@admin_required
def edit_event(id):
    event = Event.query.get_or_404(id)
    try:
        title=request.form.get('title'); date_str=request.form.get('date')
        if not title or not date_str: flash('Title/date required.', 'warning'); return redirect(url_for('admin_events'))
        event.title = title; event.description = request.form.get('description')
        event.date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        event.location = request.form.get('location', 'Church Auditorium')
        db.session.commit(); flash('Event updated!', 'success')
        log_activity(f"Event updated: '{title}'")
    except ValueError: flash('Invalid date format.', 'danger')
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Edit event error: {e}")
    return redirect(url_for('admin_events'))

@app.route('/admin/events/delete/<int:id>')
@admin_required
def delete_event(id):
    event = Event.query.get_or_404(id); title = event.title
    try:
        db.session.delete(event); db.session.commit(); flash('Event deleted!', 'success')
        log_activity(f"Event deleted: '{title}'")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Delete event error: {e}")
    return redirect(url_for('admin_events'))

@app.route('/admin/members')
@admin_required
def admin_members():
    try: members = Member.query.order_by(Member.name).all()
    except Exception as e: members = []; flash(f'Error: {e}', 'danger'); print(f"Members load error: {e}")
    return render_template('admin/members.html', members=members)

@app.route('/admin/members/add', methods=['POST'])
@admin_required
def add_member():
    try:
        name = request.form.get('name'); email = request.form.get('email')
        if not name or not email: flash('Name/email required.', 'warning'); return redirect(url_for('admin_members'))
        if Member.query.filter_by(email=email).first(): flash(f'Email "{email}" exists.', 'danger'); return redirect(url_for('admin_members'))
        dob = parse_date_or_none(request.form.get('dob'))
        marriage = parse_date_or_none(request.form.get('marriage_date'))
        baptism = parse_date_or_none(request.form.get('Baptism_date'))
        confirmation = parse_date_or_none(request.form.get('Confirmation_date'))
        new = Member(name=name, email=email, phone=request.form.get('phone'), role=request.form.get('role', 'Member'),
                     join_date=datetime.utcnow().date(), dob=dob, marriage_date=marriage,
                     Baptism_date=baptism, Confirmation_date=confirmation)
        db.session.add(new); db.session.commit(); flash(f'Member "{name}" added!', 'success')
        log_activity(f"Member added: {name} ({email})")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Add member error: {e}")
    return redirect(url_for('admin_members'))

@app.route('/admin/members/edit/<int:id>', methods=['POST'])
@admin_required
def edit_member(id):
    member = Member.query.get_or_404(id)
    try:
        name = request.form.get('name'); new_email = request.form.get('email')
        if not name or not new_email: flash('Name/email required.', 'warning'); return redirect(url_for('admin_members'))
        if Member.query.filter(Member.email == new_email, Member.id != id).first(): flash(f'Email "{new_email}" exists.', 'danger'); return redirect(url_for('admin_members'))
        member.name = name; member.email = new_email
        member.phone = request.form.get('phone'); member.role = request.form.get('role', 'Member')
        member.dob = parse_date_or_none(request.form.get('dob'))
        member.marriage_date = parse_date_or_none(request.form.get('marriage_date'))
        member.Baptism_date = parse_date_or_none(request.form.get('Baptism_date'))
        member.Confirmation_date = parse_date_or_none(request.form.get('Confirmation_date'))
        db.session.commit(); flash(f'Member "{member.name}" updated!', 'success')
        log_activity(f"Member updated: {name} ({new_email})")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Edit member error: {e}")
    return redirect(url_for('admin_members'))

@app.route('/admin/members/delete/<int:id>')
@admin_required
def delete_member(id):
    member = Member.query.get_or_404(id); name = member.name; email = member.email
    try:
        db.session.delete(member); db.session.commit(); flash(f'Member "{name}" deleted!', 'success')
        log_activity(f"Member deleted: {name} ({email})")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Delete member error: {e}")
    return redirect(url_for('admin_members'))

@app.route('/admin/sermons')
@admin_required
def admin_sermons():
    try: sermons = Sermon.query.order_by(Sermon.date.desc()).all()
    except Exception as e: sermons = []; flash(f'Error: {e}', 'danger'); print(f"Sermons load error: {e}")
    return render_template('admin/sermons.html', sermons=sermons)

@app.route('/admin/sermons/add', methods=['POST'])
@admin_required
def add_sermon():
    try:
        title=request.form.get('title'); preacher=request.form.get('preacher'); date_str=request.form.get('date'); raw_url=request.form.get('youtube_embed_url')
        if not all([title, preacher, date_str, raw_url]): flash('All fields required.', 'warning'); return redirect(url_for('admin_sermons'))
        url = convert_to_embed_url(raw_url)
        if not url: flash(f'Invalid YouTube URL: "{raw_url}".', 'danger'); return redirect(url_for('admin_sermons'))
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        new = Sermon(title=title, preacher=preacher, date=date, youtube_embed_url=url)
        db.session.add(new); db.session.commit(); flash('Sermon added!', 'success')
        log_activity(f"Sermon added: '{title}' by {preacher}")
    except ValueError: flash('Invalid date format.', 'danger')
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Add sermon error: {e}")
    return redirect(url_for('admin_sermons'))

@app.route('/admin/sermons/edit/<int:id>', methods=['POST'])
@admin_required
def edit_sermon(id):
    sermon = Sermon.query.get_or_404(id)
    try:
        title=request.form.get('title'); preacher=request.form.get('preacher'); date_str=request.form.get('date'); raw_url=request.form.get('youtube_embed_url')
        if not all([title, preacher, date_str, raw_url]): flash('All fields required.', 'warning'); return redirect(url_for('admin_sermons'))
        url = convert_to_embed_url(raw_url)
        if not url: flash(f'Invalid YouTube URL: "{raw_url}".', 'danger'); return redirect(url_for('admin_sermons'))
        sermon.title = title; sermon.preacher = preacher
        sermon.date = datetime.strptime(date_str, '%Y-%m-%d').date()
        sermon.youtube_embed_url = url
        db.session.commit(); flash('Sermon updated!', 'success')
        log_activity(f"Sermon updated: '{title}'")
    except ValueError: flash('Invalid date format.', 'danger')
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Edit sermon error: {e}")
    return redirect(url_for('admin_sermons'))

@app.route('/admin/sermons/delete/<int:id>')
@admin_required
def delete_sermon(id):
    sermon = Sermon.query.get_or_404(id); title = sermon.title
    try:
        db.session.delete(sermon); db.session.commit(); flash(f'Sermon "{title}" deleted!', 'success')
        log_activity(f"Sermon deleted: '{title}'")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Delete sermon error: {e}")
    return redirect(url_for('admin_sermons'))

@app.route('/admin/gallery')
@admin_required
def admin_gallery():
    gallery_data = get_gallery_data()
    return render_template('admin/manage_gallery.html', gallery_data=gallery_data)

@app.route('/admin/gallery/upload', methods=['POST'])
@admin_required
def upload_gallery_image():
    if 'photos' not in request.files: flash('No file part.', 'warning'); return redirect(url_for('admin_gallery'))
    main_folder = request.form.get('main_folder', '').strip()
    sub_folder = request.form.get('sub_folder', '').strip()
    if not main_folder or not sub_folder: flash('Main & Sub-Folder names required.', 'danger'); return redirect(url_for('admin_gallery'))
    safe_main_folder = secure_filename(main_folder.replace(' ', '_'))
    safe_sub_folder = secure_filename(sub_folder.replace(' ', '_'))
    if not safe_main_folder or not safe_sub_folder: flash('Invalid folder name(s).', 'danger'); return redirect(url_for('admin_gallery'))
    target_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_main_folder, safe_sub_folder)
    files = request.files.getlist('photos')
    up_count, err_count = 0, 0
    if not files or files[0].filename == '': flash('No files selected.', 'warning'); return redirect(url_for('admin_gallery'))
    if not os.path.exists(target_path):
        try: os.makedirs(target_path, exist_ok=True)
        except OSError as e: flash(f'Cannot create dir: {e}', 'danger'); return redirect(url_for('admin_gallery'))
    uploaded_filenames = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            try:
                filepath = os.path.join(target_path, filename); base, ext = os.path.splitext(filename); count = 1
                while os.path.exists(filepath): filename = f"{base}_{count}{ext}"; filepath = os.path.join(target_path, filename); count += 1
                file.save(filepath); up_count += 1; uploaded_filenames.append(filename)
            except Exception as e: flash(f'Error saving {filename}: {e}', 'danger'); err_count += 1; print(f"File save error: {e}")
        elif file.filename != '': flash(f'Invalid type: {file.filename}', 'warning'); err_count += 1
    if up_count > 0:
        flash(f'{up_count} image(s) uploaded to "{safe_main_folder} / {safe_sub_folder}"!', 'success')
        log_activity(f"{up_count} image(s) added to gallery: '{safe_main_folder}/{safe_sub_folder}'.")
    if err_count > 0 and up_count == 0: flash(f'No valid images uploaded. Allowed: {", ".join(ALLOWED_EXTENSIONS)}', 'warning')
    elif err_count == 0 and up_count == 0: flash('No images processed.', 'warning')
    return redirect(url_for('admin_gallery'))

@app.route('/admin/gallery/delete/<main_folder>/<sub_folder>/<filename>')
@admin_required
def delete_gallery_image(main_folder, sub_folder, filename):
    safe_main_folder=secure_filename(main_folder.replace(' ', '_')); safe_sub_folder=secure_filename(sub_folder.replace(' ', '_')); safe_filename=secure_filename(filename)
    if safe_main_folder != main_folder.replace(' ', '_') or safe_sub_folder != sub_folder.replace(' ', '_') or safe_filename != filename:
        flash('Invalid name.', 'danger'); return redirect(url_for('admin_gallery'))
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_main_folder, safe_sub_folder, safe_filename)
        if os.path.exists(filepath) and os.path.isfile(filepath):
            os.remove(filepath); flash(f'Deleted "{safe_filename}".', 'success')
            log_activity(f"Image deleted: '{safe_main_folder}/{safe_sub_folder}/{safe_filename}'")
            sub_folder_path = os.path.dirname(filepath)
            if not os.listdir(sub_folder_path):
                try: os.rmdir(sub_folder_path); flash(f'Removed empty folder "{safe_sub_folder}".', 'info')
                except OSError as e: print(f"Could not remove dir {sub_folder_path}: {e}")
                main_folder_path = os.path.dirname(sub_folder_path)
                if not os.listdir(main_folder_path):
                    try: os.rmdir(main_folder_path); flash(f'Removed empty folder "{safe_main_folder}".', 'info')
                    except OSError as e: print(f"Could not remove dir {main_folder_path}: {e}")
        else: flash('Image not found.', 'warning')
    except Exception as e: flash(f'Error deleting: {e}', 'danger'); print(f"Delete image error: {e}")
    return redirect(url_for('admin_gallery'))

@app.route('/admin/gallery/delete_folder/<main_folder>/<sub_folder>')
@admin_required
def delete_gallery_folder(main_folder, sub_folder):
    safe_main_folder = secure_filename(main_folder.replace(' ', '_'))
    safe_sub_folder = secure_filename(sub_folder.replace(' ', '_'))
    if safe_main_folder != main_folder.replace(' ', '_') or safe_sub_folder != sub_folder.replace(' ', '_'):
        flash('Invalid folder name.', 'danger'); return redirect(url_for('admin_gallery'))
    try:
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_main_folder, safe_sub_folder)
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            flash(f'Folder "{safe_sub_folder}" deleted successfully.', 'success')
            log_activity(f"Gallery folder deleted: '{safe_main_folder}/{safe_sub_folder}'")
            main_folder_path = os.path.dirname(folder_path)
            if not os.listdir(main_folder_path):
                try: os.rmdir(main_folder_path); flash(f'Removed empty folder "{safe_main_folder}".', 'info')
                except OSError as e: print(f"Could not remove dir {main_folder_path}: {e}")
        else:
            flash('Folder not found.', 'warning')
    except Exception as e:
        flash(f'Error deleting folder: {e}', 'danger'); print(f"Delete folder error: {e}")
    return redirect(url_for('admin_gallery'))

@app.route('/admin/prayers')
@admin_required
def admin_prayers():
    try: reqs = PrayerRequest.query.order_by(PrayerRequest.is_answered.asc(), PrayerRequest.submitted_at.desc()).all()
    except Exception as e: reqs = []; flash(f'Error: {e}', 'danger'); print(f"Admin Prayers error: {e}")
    return render_template('admin/prayers.html', requests=reqs)

# === PUTHU ROUTE (Prayer-a Notice-a Maathurathu) ===
@app.route('/admin/prayers/to_notice/<int:id>')
@admin_required
def prayer_to_notice(id):
    req = PrayerRequest.query.get_or_404(id)
    try:
        # Puthu notice create pannurom
        notice_message = f"Prayer Request: Please pray for {req.name}. ({req.message[:50]}...)" # Message-a short-a podurom
        new_notice = Notice(message=notice_message, is_active=True)
        db.session.add(new_notice)
        db.session.commit()
        flash('Prayer request added to home page notices!', 'success')
        log_activity(f"Prayer request from '{req.name}' added to notices.")
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding prayer to notice: {e}', 'danger')
        print(f"Prayer to notice error: {e}")
    return redirect(url_for('admin_prayers'))
# ==================================================

@app.route('/admin/prayers/toggle_answered/<int:id>')
@admin_required
def toggle_prayer_answered(id):
    req = PrayerRequest.query.get_or_404(id)
    try:
        req.is_answered = not req.is_answered; db.session.commit()
        status = "answered" if req.is_answered else "unanswered"
        flash(f'Request marked as {status}.', 'success')
        log_activity(f"Prayer request from {req.name} marked as {status}.")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Toggle prayer error: {e}")
    return redirect(url_for('admin_prayers'))

@app.route('/admin/notices')
@admin_required
def admin_notices():
    try: notices = Notice.query.order_by(Notice.created_at.desc()).all()
    except Exception as e: notices = []; flash(f'Error: {e}', 'danger'); print(f"Notices load error: {e}")
    return render_template('admin/notices.html', notices=notices)

@app.route('/admin/notices/add', methods=['POST'])
@admin_required
def add_notice():
    msg_txt = request.form.get('message')
    if not msg_txt: flash('Message empty.', 'warning'); return redirect(url_for('admin_notices'))
    try:
        new = Notice(message=msg_txt, is_active=True); db.session.add(new); db.session.commit(); flash('Notice added!', 'success')
        log_activity(f"Notice added: '{msg_txt[:30]}...'")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Add notice error: {e}")
    return redirect(url_for('admin_notices'))

@app.route('/admin/notices/toggle/<int:id>')
@admin_required
def toggle_notice(id):
    notice = Notice.query.get_or_404(id)
    try:
        notice.is_active = not notice.is_active; db.session.commit()
        status = "activated" if notice.is_active else "deactivated"
        flash(f'Notice {status}.', 'success')
        log_activity(f"Notice '{notice.message[:30]}...' {status}.")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Toggle notice error: {e}")
    return redirect(url_for('admin_notices'))

@app.route('/admin/notices/delete/<int:id>')
@admin_required
def delete_notice(id):
    notice = Notice.query.get_or_404(id); msg_txt = notice.message[:30]
    try:
        db.session.delete(notice); db.session.commit(); flash('Notice deleted.', 'success')
        log_activity(f"Notice deleted: '{msg_txt}...'")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Delete notice error: {e}")
    return redirect(url_for('admin_notices'))

@app.route('/admin/send-birthday-wishes')
@admin_required
def send_birthday_wishes():
    if not mail: flash('Email not configured.', 'danger'); return redirect(url_for('admin_dashboard'))
    today = datetime.utcnow().date()
    birthdays = []
    try:
        if hasattr(Member, 'dob') and Member.dob is not None:
            birthdays = Member.query.filter(extract('month', Member.dob) == today.month, extract('day', Member.dob) == today.day).all()
        sent, errors = 0, 0
        if not birthdays: flash('No birthdays today.', 'info'); return redirect(url_for('admin_dashboard'))
        verse = get_birthday_verse()
        if not verse: verse = {"ref": "Psalm 118:24", "text": "This is the day the LORD has made; let us rejoice and be glad in it."}
        for member in birthdays:
            if member.email:
                try:
                    subject = f"Happy Birthday, {member.name}!"; body = f"Dear {member.name},\n\nWishing you a blessed birthday!\n\n---\n\"{verse['text']}\"\n- {verse['ref']}\n---\n\nCSI URA Church"
                    msg = Message(subject, recipients=[member.email], body=body)
                    mail.send(msg); sent += 1
                except Exception as e: print(f"Email error to {member.email}: {e}"); errors += 1
            else: print(f"Skipping {member.name} (no email).")
        if sent > 0: flash(f'Sent {sent} wishes.', 'success'); log_activity(f"Sent {sent} birthday wish email(s).")
        if errors > 0: flash(f'Failed {errors} emails.', 'danger')
    except Exception as e: flash(f'Error fetching birthdays: {e}', 'danger'); print(f"Birthday check error: {e}")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/send-marriage-wishes')
@admin_required
def send_marriage_wishes():
    if not mail: flash('Email not configured.', 'danger'); return redirect(url_for('admin_dashboard'))
    today = datetime.utcnow().date()
    anniversaries = []
    try:
        if hasattr(Member, 'marriage_date') and Member.marriage_date is not None:
            anniversaries = Member.query.filter(extract('month', Member.marriage_date) == today.month, extract('day', Member.marriage_date) == today.day).all()
        sent, errors = 0, 0
        if not anniversaries: flash('No marriage anniversaries today.', 'info'); return redirect(url_for('admin_dashboard'))
        verse = get_marriage_verse()
        if not verse: verse = {"ref": "1 Cor 13:13", "text": "And now these three remain: faith, hope and love. But the greatest of these is love."}
        for member in anniversaries:
            if member.email:
                try:
                    subject = f"Happy Anniversary, {member.name}!"; body = f"Dear {member.name},\n\nWishing you a blessed anniversary!\n\n---\n\"{verse['text']}\"\n- {verse['ref']}\n---\n\nCSI URA Church"
                    msg = Message(subject, recipients=[member.email], body=body)
                    mail.send(msg); sent += 1
                except Exception as e: print(f"Email error to {member.email}: {e}"); errors += 1
            else: print(f"Skipping {member.name} (no email).")
        if sent > 0: flash(f'Sent {sent} anniversary wishes.', 'success'); log_activity(f"Sent {sent} marriage wish email(s).")
        if errors > 0: flash(f'Failed {errors} emails.', 'danger')
    except Exception as e: flash(f'Error fetching anniversaries: {e}', 'danger'); print(f"Anniversary check error: {e}")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/weekly-services')
@admin_required
def admin_weekly_services():
    try: services = WeeklyService.query.order_by(WeeklyService.display_order, WeeklyService.service_name).all()
    except Exception as e: services = []; flash(f'Error: {e}', 'danger'); print(f"Weekly Services load error: {e}")
    return render_template('admin/weekly_services.html', services=services)

@app.route('/admin/weekly-services/add', methods=['POST'])
@admin_required
def add_weekly_service():
    name = request.form.get('service_name'); timing = request.form.get('timing')
    order = request.form.get('display_order', 0, type=int)
    if not name or not timing: flash('Name and Timing required.', 'warning'); return redirect(url_for('admin_weekly_services'))
    try:
        new = WeeklyService(service_name=name, timing=timing, display_order=order)
        db.session.add(new); db.session.commit(); flash('Weekly service added!', 'success')
        log_activity(f"Weekly Service added: '{name}'")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Add weekly service error: {e}")
    return redirect(url_for('admin_weekly_services'))

@app.route('/admin/weekly-services/edit/<int:id>', methods=['POST'])
@admin_required
def edit_weekly_service(id):
    service = WeeklyService.query.get_or_404(id)
    name = request.form.get('service_name'); timing = request.form.get('timing')
    order = request.form.get('display_order', 0, type=int)
    if not name or not timing: flash('Name and Timing required.', 'warning'); return redirect(url_for('admin_weekly_services'))
    try:
        service.service_name = name; service.timing = timing; service.display_order = order
        db.session.commit(); flash('Weekly service updated!', 'success')
        log_activity(f"Weekly Service updated: '{name}'")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Edit weekly service error: {e}")
    return redirect(url_for('admin_weekly_services'))

@app.route('/admin/weekly-services/delete/<int:id>')
@admin_required
def delete_weekly_service(id):
    service = WeeklyService.query.get_or_404(id); name = service.service_name
    try:
        db.session.delete(service); db.session.commit(); flash(f'Weekly service "{name}" deleted!', 'success')
        log_activity(f"Weekly Service deleted: '{name}'")
    except Exception as e: db.session.rollback(); flash(f'Error: {e}', 'danger'); print(f"Delete weekly service error: {e}")
    return redirect(url_for('admin_weekly_services'))

@app.route('/admin/donations')
@admin_required
def admin_donations():
    try: donations = Donation.query.order_by(Donation.submitted_at.desc()).all()
    except Exception as e: donations = []; flash(f'Error: {e}', 'danger'); print(f"Admin Donations load error: {e}")
    return render_template('admin/donations.html', donations=donations)

# === VIDEO ROUTES DELETE PANNITOM ===

# --- Database Initialization Command ---
@app.cli.command('init-db')
def init_db_command():
    """Creates/updates database tables and default admin."""
    with app.app_context():
        instance_path = os.path.join(app.root_path, '..', 'instance')
        db_file = os.path.join(instance_path, 'church.db')
        db_exists = os.path.exists(db_file)
        schema_ok = True

        if db_exists:
            try:
                inspector = db.inspect(db.engine)
                # === 'video_clip' TABLE-A DELETE PANNITOM ===
                required_tables = {'user', 'member', 'event', 'sermon', 'prayer_request', 'notice', 'activity_log', 'weekly_service', 'donation'}
                existing_tables = set(inspector.get_table_names())
                if not required_tables.issubset(existing_tables):
                    print(f"\nDB Schema Error: Missing tables: {required_tables - existing_tables}"); schema_ok = False
                else:
                    user_cols = {c['name'] for c in inspector.get_columns('user')}
                    member_cols = {c['name'] for c in inspector.get_columns('member')}
                    if 'email' not in user_cols: print("DB Schema Error: User table missing 'email'."); schema_ok = False
                    if 'dob' not in member_cols or 'marriage_date' not in member_cols or 'Baptism_date' not in member_cols or 'Confirmation_date' not in member_cols:
                        print("DB Schema Error: Member table missing 'dob'/'marriage_date'/'Baptism_date'/'Confirmation_date'."); schema_ok = False
            except Exception as inspect_e:
                print(f"\nDB Inspect Error: {inspect_e}"); schema_ok = False

        if not schema_ok:
            print("\nACTION REQUIRED: Stop app, delete 'instance/church.db', re-run 'flask init-db'.\n"); return

        if not os.path.exists(instance_path): os.makedirs(instance_path)
        try: db.create_all(); print("DB tables created/verified.")
        except Exception as e: print(f"Error db.create_all(): {e}"); return

        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            try: os.makedirs(upload_folder, exist_ok=True); print(f"Created gallery folder: {upload_folder}")
            except OSError as e: print(f"Error creating gallery folder: {e}")

        if not User.query.filter_by(username='admin').first():
            admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
            admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
            if admin_email == 'admin@example.com': print("\nWARN: Using default admin email."); print("Set ADMIN_EMAIL env var.\n")
            if admin_password == 'admin123': print("\nWARN: Using default/insecure admin password!"); print("Set ADMIN_PASSWORD env var.\n")
            try:
                admin = User(username='admin', email=admin_email)
                admin.set_password(admin_password)
                db.session.add(admin); db.session.commit()
                print(f'Created admin user (admin) email {admin_email}.'); print("Change default password!")
            except Exception as e: db.session.rollback(); print(f"Error creating admin: {e}")
        else:
            print('Admin user already exists.')

# --- Main Run ---
if __name__ == '__main__':
    instance_path = os.path.join(app.root_path, '..', 'instance')
    if not os.path.exists(instance_path): os.makedirs(instance_path, exist_ok=True)
    if not os.path.exists(app.config['UPLOAD_FOLDER']): os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() in ['true', '1', 't']
    print(f"Starting Flask app: http://0.0.0.0:{port}/ | Debug: {debug_mode}")
    app.run(debug=debug_mode, host='0.0.0.0', port=port, threaded=True)