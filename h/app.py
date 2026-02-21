import os
import sys
import uuid
from copy import deepcopy
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
import mysql.connector
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import jwt
from functools import wraps
import json

# Add modul directory to path BEFORE importing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modul'))

# Now import the question modules
try:
    from modules.computer_questions import get_questions as get_computer_questions
    from modules.mathematics_questions import get_questions as get_math_questions
    from modules.science_questions import get_questions as get_science_questions
    from modules.english_questions import get_questions as get_english_questions
    from modules.gujarati_questions import get_questions as get_gujarati_questions
    from modules.social_science_questions import get_questions as get_social_science_questions
except ImportError as e:
    print(f"Warning: Could not import question modules: {e}")
    # Provide dummy functions if imports fail
    def get_computer_questions():
        return []
    def get_math_questions():
        return []
    def get_science_questions():
        return []
    def get_english_questions():
        return []
    def get_gujarati_questions():
        return []
    def get_social_science_questions():
        return []

# Initialize Flask app
app = Flask(__name__, 
    template_folder='templates',  # Ensure templates are in a 'templates' folder
    static_folder='static'        # Static files folder
)

# Configure Flask app
app.secret_key = "dhaval@2004"

# Configure Jinja2
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Enable CORS
CORS(app, supports_credentials=True)

# Simple User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = ""
        self.grade = ""
        self.school = ""
        self.joined_at = datetime.utcnow()
        self.is_admin = False
        self.progress = {}

# Store users in memory (for demo purposes - use database in production)
users = {}
ADMIN_EMAILS = {"pandordhaval05@gmail.com"}
DEFAULT_ADMIN_PASSWORD = "Admin@123"
DEFAULT_USER_EMAIL = "dhaval@gmail.com"
DEFAULT_USER_PASSWORD = "dhaval@2004"
ADMIN_VIEW_ONLY = False
SHOW_ADMIN_PANEL = False

QUIZ_SUBJECTS = {
    'computer': 'Computer',
    'math': 'Mathematics',
    'mathematics': 'Mathematics',
    'science': 'Science',
    'english': 'English',
    'gujarati': 'Gujarati',
    'social-science': 'Social Science',
    'social_science': 'Social Science',
}
ADMIN_SUBJECT_KEYS = ['computer', 'math', 'science', 'english', 'gujarati', 'social-science']
QUESTIONS_STORE_PATH = os.path.join(app.instance_path, 'admin_questions.json')
MARKS_STORE_PATH = os.path.join(app.instance_path, 'marks_store.json')

# Track whether a subject quiz is active (admin can toggle this at runtime).
quiz_enabled = {key: True for key in QUIZ_SUBJECTS.keys()}


def ensure_default_admin():
    if find_user_by_email('admin@schoollearn.com'):
        return

    admin_user = User('admin-1', 'Admin', 'admin@schoollearn.com')
    admin_user.password_hash = generate_password_hash(DEFAULT_ADMIN_PASSWORD)
    admin_user.grade = 'N/A'
    admin_user.school = 'SchoolLearn'
    admin_user.joined_at = datetime.utcnow()
    admin_user.is_admin = True
    users[admin_user.id] = admin_user


def ensure_default_user():
    existing_user = find_user_by_email(DEFAULT_USER_EMAIL)
    if existing_user:
        existing_user.is_admin = False
        existing_user.password_hash = generate_password_hash(DEFAULT_USER_PASSWORD)
        ADMIN_EMAILS.discard(DEFAULT_USER_EMAIL)
        return

    demo_user = User('user-1', 'Dhaval', DEFAULT_USER_EMAIL)
    demo_user.password_hash = generate_password_hash(DEFAULT_USER_PASSWORD)
    demo_user.grade = '10th'
    demo_user.school = 'SchoolLearn'
    demo_user.joined_at = datetime.utcnow()
    demo_user.is_admin = False
    ADMIN_EMAILS.discard(DEFAULT_USER_EMAIL)
    users[demo_user.id] = demo_user


# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'student_login'

def find_user_by_email(email):
    for user in users.values():
        if user.email.lower() == email.lower():
            return user
    return None


def is_admin_user(user):
    return bool(user and getattr(user, 'is_admin', False))


def normalize_subject(subject):
    return subject.lower().strip()


def canonical_subject(subject):
    normalized = normalize_subject(subject)
    if normalized == 'mathematics':
        return 'math'
    if normalized == 'social_science':
        return 'social-science'
    return normalized


def ensure_user_progress(user):
    if not isinstance(user.progress, dict):
        user.progress = {}
    user.progress.setdefault('attempts', [])
    user.progress.setdefault('by_subject', {})
    return user.progress


def parse_iso_datetime(value):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.utcnow()


def default_marks_store():
    return {'entries': []}


def load_marks_store():
    os.makedirs(app.instance_path, exist_ok=True)
    if not os.path.exists(MARKS_STORE_PATH):
        store = default_marks_store()
        with open(MARKS_STORE_PATH, 'w', encoding='utf-8') as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
        return store

    with open(MARKS_STORE_PATH, 'r', encoding='utf-8') as f:
        try:
            store = json.load(f)
        except json.JSONDecodeError:
            store = default_marks_store()

    if not isinstance(store.get('entries'), list):
        store['entries'] = []
    return store


def save_marks_store(store):
    os.makedirs(app.instance_path, exist_ok=True)
    with open(MARKS_STORE_PATH, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def percentage_from_marks(score, total):
    if total <= 0:
        return 0
    return round((score / total) * 100, 1)


def get_marks_for_user(user):
    store = load_marks_store()
    results = [
        item for item in store.get('entries', [])
        if str(item.get('student_id')) == str(user.id)
    ]
    return sorted(results, key=lambda item: item.get('recorded_at', ''), reverse=True)


def calculate_result_analytics_for_user(user):
    entries = get_marks_for_user(user)
    total_records = len(entries)
    if not total_records:
        return {
            'total_records': 0,
            'average_percentage': 0,
            'best_percentage': 0,
            'total_scored': 0,
            'total_possible': 0,
            'subject_summary': [],
            'recent_results': [],
        }

    total_scored = sum(float(item.get('score', 0)) for item in entries)
    total_possible = sum(float(item.get('total', 0)) for item in entries)
    percentages = [float(item.get('percentage', 0)) for item in entries]
    average_percentage = round(sum(percentages) / total_records, 1)
    best_percentage = round(max(percentages), 1)

    subject_rollup = {}
    for item in entries:
        subject = item.get('subject', 'General')
        row = subject_rollup.setdefault(subject, {
            'subject': subject,
            'attempts': 0,
            'total_percentage': 0.0,
            'best_percentage': 0.0,
        })
        pct = float(item.get('percentage', 0))
        row['attempts'] += 1
        row['total_percentage'] += pct
        row['best_percentage'] = max(row['best_percentage'], pct)

    subject_summary = []
    for row in subject_rollup.values():
        subject_summary.append({
            'subject': row['subject'],
            'attempts': row['attempts'],
            'average_percentage': round(row['total_percentage'] / row['attempts'], 1),
            'best_percentage': round(row['best_percentage'], 1),
        })
    subject_summary.sort(key=lambda item: item['average_percentage'], reverse=True)

    recent_results = []
    for item in entries[:8]:
        recorded_at = parse_iso_datetime(item.get('recorded_at', ''))
        recent_results.append({
            **item,
            'recorded_at_display': recorded_at.strftime('%Y-%m-%d %H:%M UTC')
        })

    return {
        'total_records': total_records,
        'average_percentage': average_percentage,
        'best_percentage': best_percentage,
        'total_scored': round(total_scored, 1),
        'total_possible': round(total_possible, 1),
        'subject_summary': subject_summary,
        'recent_results': recent_results,
    }


def calculate_admin_result_analytics():
    store = load_marks_store()
    entries = sorted(store.get('entries', []), key=lambda item: item.get('recorded_at', ''), reverse=True)
    total_records = len(entries)
    if not total_records:
        return {
            'total_records': 0,
            'unique_students': 0,
            'overall_average': 0,
            'subject_summary': [],
            'recent_entries': [],
        }

    overall_average = round(
        sum(float(item.get('percentage', 0)) for item in entries) / total_records,
        1
    )
    unique_students = len({item.get('student_id') for item in entries if item.get('student_id')})

    subject_rollup = {}
    for item in entries:
        subject = item.get('subject', 'General')
        row = subject_rollup.setdefault(subject, {
            'subject': subject,
            'records': 0,
            'total_percentage': 0.0,
            'best_percentage': 0.0,
        })
        pct = float(item.get('percentage', 0))
        row['records'] += 1
        row['total_percentage'] += pct
        row['best_percentage'] = max(row['best_percentage'], pct)

    subject_summary = []
    for row in subject_rollup.values():
        subject_summary.append({
            'subject': row['subject'],
            'records': row['records'],
            'average_percentage': round(row['total_percentage'] / row['records'], 1),
            'best_percentage': round(row['best_percentage'], 1),
        })
    subject_summary.sort(key=lambda item: item['average_percentage'], reverse=True)

    recent_entries = []
    for item in entries[:12]:
        recorded_at = parse_iso_datetime(item.get('recorded_at', ''))
        recent_entries.append({
            **item,
            'recorded_at_display': recorded_at.strftime('%Y-%m-%d %H:%M UTC')
        })

    return {
        'total_records': total_records,
        'unique_students': unique_students,
        'overall_average': overall_average,
        'subject_summary': subject_summary,
        'recent_entries': recent_entries,
    }


def calculate_student_analytics(user):
    progress = ensure_user_progress(user)
    attempts = sorted(
        progress.get('attempts', []),
        key=lambda item: item.get('attempted_at', ''),
        reverse=True
    )

    total_quizzes = len(attempts)
    total_questions = sum(int(item.get('total_questions', 0)) for item in attempts)
    total_correct = sum(int(item.get('score', 0)) for item in attempts)
    avg_score = round(
        sum(float(item.get('percentage', 0)) for item in attempts) / total_quizzes,
        1
    ) if total_quizzes else 0
    overall_accuracy = round((total_correct / total_questions) * 100, 1) if total_questions else 0

    subject_rollup = {}
    for item in attempts:
        subject = canonical_subject(item.get('subject', ''))
        if subject not in ADMIN_SUBJECT_KEYS:
            continue
        name = QUIZ_SUBJECTS[subject]
        entry = subject_rollup.setdefault(name, {
            'subject': name,
            'attempts': 0,
            'average': 0.0,
            'best': 0.0,
            'total': 0.0,
        })
        percentage = float(item.get('percentage', 0))
        entry['attempts'] += 1
        entry['total'] += percentage
        entry['best'] = max(entry['best'], percentage)

    for entry in subject_rollup.values():
        entry['average'] = round(entry['total'] / entry['attempts'], 1) if entry['attempts'] else 0

    subject_performance = sorted(
        subject_rollup.values(),
        key=lambda item: item['average'],
        reverse=True
    )

    recent_attempts = []
    for item in attempts[:8]:
        attempted_at = parse_iso_datetime(item.get('attempted_at', ''))
        recent_attempts.append({
            **item,
            'attempted_at_display': attempted_at.strftime('%Y-%m-%d %H:%M UTC')
        })

    return {
        'total_quizzes': total_quizzes,
        'total_questions': total_questions,
        'total_correct': total_correct,
        'avg_score': avg_score,
        'overall_accuracy': overall_accuracy,
        'recent_attempts': recent_attempts,
        'subject_performance': subject_performance,
    }


def default_questions_store():
    return {
        'custom': {key: [] for key in ADMIN_SUBJECT_KEYS},
        'deleted_base': {key: [] for key in ADMIN_SUBJECT_KEYS},
    }


def load_questions_store():
    os.makedirs(app.instance_path, exist_ok=True)
    if not os.path.exists(QUESTIONS_STORE_PATH):
        store = default_questions_store()
        with open(QUESTIONS_STORE_PATH, 'w', encoding='utf-8') as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
        return store

    with open(QUESTIONS_STORE_PATH, 'r', encoding='utf-8') as f:
        try:
            store = json.load(f)
        except json.JSONDecodeError:
            store = default_questions_store()

    # Backfill keys for forward compatibility.
    for key in ADMIN_SUBJECT_KEYS:
        store.setdefault('custom', {}).setdefault(key, [])
        store.setdefault('deleted_base', {}).setdefault(key, [])
    return store


def save_questions_store(store):
    os.makedirs(app.instance_path, exist_ok=True)
    with open(QUESTIONS_STORE_PATH, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def get_base_questions_for_subject(subject):
    key = canonical_subject(subject)
    if key == 'computer':
        return deepcopy(get_computer_questions())
    if key == 'math':
        return deepcopy(get_math_questions())
    if key == 'science':
        return deepcopy(get_science_questions())
    if key == 'english':
        return deepcopy(get_english_questions())
    if key == 'gujarati':
        return deepcopy(get_gujarati_questions())
    if key == 'social-science':
        return deepcopy(get_social_science_questions())
    return []


def get_merged_questions_for_subject(subject):
    key = canonical_subject(subject)
    store = load_questions_store()
    deleted_base = set(store.get('deleted_base', {}).get(key, []))

    merged = []
    base_questions = get_base_questions_for_subject(key)
    for idx, q in enumerate(base_questions):
        qid = f'base-{idx}'
        if qid in deleted_base:
            continue
        item = deepcopy(q)
        item['_qid'] = qid
        item['_source'] = 'base'
        merged.append(item)

    for custom in store.get('custom', {}).get(key, []):
        item = deepcopy(custom)
        item['_source'] = 'custom'
        merged.append(item)

    return merged


@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Authentication required'}), 401
    return redirect(url_for('student_login'))


@app.before_request
def hide_admin_panel_routes():
    if not SHOW_ADMIN_PANEL and request.path.startswith('/admin'):
        return "Not Found", 404

# Inject common template variables (e.g. current year for footer and current_user)
@app.context_processor
def inject_now_and_user():
    return {
        'now': datetime.utcnow(),
        'current_user': current_user,
        'show_admin_panel': SHOW_ADMIN_PANEL,
    }


ensure_default_admin()
ensure_default_user()

# Routes
@app.route('/')
def home():
    return render_template("index.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    return student_login()


@app.route('/student-login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = find_user_by_email(email)
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password.', 'error')
            return render_template('login.html', login_mode='student'), 401

        if is_admin_user(user):
            flash('This account is admin. Use Admin Login.', 'error')
            return render_template('login.html', login_mode='student'), 403

        login_user(user)
        flash('Logged in successfully.', 'success')
        return redirect(url_for('profile'))

    return render_template('login.html', login_mode='student')


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = find_user_by_email(email)
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password.', 'error')
            return render_template('login.html', login_mode='admin'), 401

        if not is_admin_user(user):
            flash('Admin account required.', 'error')
            return render_template('login.html', login_mode='admin'), 403

        login_user(user)
        flash('Admin login successful.', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('login.html', login_mode='admin')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('fullName', '').strip()
        email = request.form.get('email', '').strip().lower()
        grade = request.form.get('grade', '').strip()
        school = request.form.get('school', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirmPassword', '')

        if not username or not email or not password:
            flash('Name, email, and password are required.', 'error')
            return render_template('register.html'), 400

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html'), 400

        if find_user_by_email(email):
            flash('An account with this email already exists.', 'error')
            return render_template('register.html'), 409

        user_id = str(len(users) + 1)
        user = User(user_id, username, email)
        user.password_hash = generate_password_hash(password)
        user.grade = grade
        user.school = school
        user.joined_at = datetime.utcnow()
        user.is_admin = email in ADMIN_EMAILS
        users[user_id] = user

        login_user(user)
        flash('Registration successful.', 'success')
        return redirect(url_for('profile'))

    return render_template('register.html')


@app.route('/profile')
@login_required
def profile():
    analytics = calculate_student_analytics(current_user)
    result_analytics = calculate_result_analytics_for_user(current_user)
    return render_template('student_dashboard.html', analytics=analytics, result_analytics=result_analytics)


@app.route('/api/student/analytics', methods=['GET'])
@login_required
def student_analytics():
    return jsonify(calculate_student_analytics(current_user))


@app.route('/api/student/results', methods=['GET'])
@login_required
def student_results():
    return jsonify(calculate_result_analytics_for_user(current_user))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))


@app.route('/admin')
@login_required
def admin_dashboard():
    if not is_admin_user(current_user):
        flash('Admin access only.', 'error')
        return redirect(url_for('home'))

    managed_users = sorted(users.values(), key=lambda u: u.joined_at, reverse=True)
    selected_subject = canonical_subject(request.args.get('subject', 'math'))
    if selected_subject not in ADMIN_SUBJECT_KEYS:
        selected_subject = 'math'

    quiz_counts = {
        'Computer': len(get_merged_questions_for_subject('computer')),
        'Mathematics': len(get_merged_questions_for_subject('math')),
        'Science': len(get_merged_questions_for_subject('science')),
        'English': len(get_merged_questions_for_subject('english')),
        'Gujarati': len(get_merged_questions_for_subject('gujarati')),
        'Social Science': len(get_merged_questions_for_subject('social-science')),
    }
    total_questions = sum(quiz_counts.values())

    canonical_quiz_status = {
        'computer': quiz_enabled['computer'],
        'math': quiz_enabled['math'],
        'science': quiz_enabled['science'],
        'english': quiz_enabled['english'],
        'gujarati': quiz_enabled['gujarati'],
        'social-science': quiz_enabled['social-science'],
    }

    result_analytics = calculate_admin_result_analytics()

    return render_template(
        'admin.html',
        managed_users=managed_users,
        quiz_counts=quiz_counts,
        total_questions=total_questions,
        canonical_quiz_status=canonical_quiz_status,
        admin_subjects=[(k, QUIZ_SUBJECTS[k]) for k in ADMIN_SUBJECT_KEYS],
        selected_subject=selected_subject,
        selected_subject_questions=get_merged_questions_for_subject(selected_subject),
        result_analytics=result_analytics
    )


@app.route('/admin/marks/upload', methods=['POST'])
@login_required
def admin_upload_marks():
    if not is_admin_user(current_user):
        flash('Admin access only.', 'error')
        return redirect(url_for('home'))

    email = request.form.get('student_email', '').strip().lower()
    exam_name = request.form.get('exam_name', '').strip()
    subject = request.form.get('subject', '').strip() or 'General'
    exam_date = request.form.get('exam_date', '').strip()
    remarks = request.form.get('remarks', '').strip()

    try:
        score = float(request.form.get('score', '0'))
        total = float(request.form.get('total', '0'))
    except ValueError:
        flash('Score and total must be numeric.', 'error')
        return redirect(url_for('admin_dashboard'))

    if not email or not exam_name or total <= 0:
        flash('Student email, exam name, and total marks are required.', 'error')
        return redirect(url_for('admin_dashboard'))

    if score < 0 or score > total:
        flash('Score must be between 0 and total marks.', 'error')
        return redirect(url_for('admin_dashboard'))

    student = find_user_by_email(email)
    if not student:
        flash('Student not found for provided email.', 'error')
        return redirect(url_for('admin_dashboard'))

    if is_admin_user(student):
        flash('Marks can only be uploaded for student accounts.', 'error')
        return redirect(url_for('admin_dashboard'))

    recorded_at = datetime.utcnow().isoformat()
    if exam_date:
        try:
            recorded_at = datetime.fromisoformat(exam_date).isoformat()
        except ValueError:
            pass

    mark_entry = {
        'id': f'mark-{uuid.uuid4().hex[:12]}',
        'student_id': student.id,
        'student_name': student.username,
        'student_email': student.email,
        'exam_name': exam_name,
        'subject': subject,
        'score': round(score, 1),
        'total': round(total, 1),
        'percentage': percentage_from_marks(score, total),
        'remarks': remarks,
        'recorded_at': recorded_at,
        'uploaded_by': current_user.email,
        'uploaded_at': datetime.utcnow().isoformat(),
    }

    store = load_marks_store()
    store['entries'].append(mark_entry)
    store['entries'] = store['entries'][-2000:]
    save_marks_store(store)

    flash('Marks uploaded successfully.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/users/<user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not is_admin_user(current_user):
        flash('Admin access only.', 'error')
        return redirect(url_for('home'))
    if ADMIN_VIEW_ONLY:
        flash('Admin dashboard is in view-only mode.', 'error')
        return redirect(url_for('admin_dashboard'))

    if user_id == current_user.id:
        flash('You cannot delete your own admin account.', 'error')
        return redirect(url_for('admin_dashboard'))

    if user_id in users:
        del users[user_id]
        flash('User deleted.', 'success')
    else:
        flash('User not found.', 'error')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/users/<user_id>/toggle-admin', methods=['POST'])
@login_required
def admin_toggle_user_admin(user_id):
    if not is_admin_user(current_user):
        flash('Admin access only.', 'error')
        return redirect(url_for('home'))
    if ADMIN_VIEW_ONLY:
        flash('Admin dashboard is in view-only mode.', 'error')
        return redirect(url_for('admin_dashboard'))

    target = users.get(user_id)
    if not target:
        flash('User not found.', 'error')
        return redirect(url_for('admin_dashboard'))

    if target.id == current_user.id:
        flash('You cannot change your own admin role.', 'error')
        return redirect(url_for('admin_dashboard'))

    target.is_admin = not getattr(target, 'is_admin', False)
    flash('User role updated.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/quiz/<subject>/toggle', methods=['POST'])
@login_required
def admin_toggle_quiz(subject):
    if not is_admin_user(current_user):
        flash('Admin access only.', 'error')
        return redirect(url_for('home'))
    if ADMIN_VIEW_ONLY:
        flash('Admin dashboard is in view-only mode.', 'error')
        return redirect(url_for('admin_dashboard'))

    key = canonical_subject(subject)
    if key not in quiz_enabled:
        flash('Invalid subject.', 'error')
        return redirect(url_for('admin_dashboard'))

    new_value = request.form.get('enabled') == '1'
    quiz_enabled[key] = new_value

    # Keep alias keys in sync.
    if key == 'math':
        quiz_enabled['mathematics'] = new_value
    if key == 'social-science':
        quiz_enabled['social_science'] = new_value

    flash(f'Quiz status for {QUIZ_SUBJECTS[key]} updated.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/questions/add', methods=['POST'])
@login_required
def admin_add_question():
    if not is_admin_user(current_user):
        flash('Admin access only.', 'error')
        return redirect(url_for('home'))

    subject = canonical_subject(request.form.get('subject', ''))
    if subject not in ADMIN_SUBJECT_KEYS:
        flash('Invalid subject.', 'error')
        return redirect(url_for('admin_dashboard'))

    question_text = request.form.get('question', '').strip()
    options = [
        request.form.get('option_a', '').strip(),
        request.form.get('option_b', '').strip(),
        request.form.get('option_c', '').strip(),
        request.form.get('option_d', '').strip(),
    ]
    explanation = request.form.get('explanation', '').strip()
    try:
        answer = int(request.form.get('answer', '-1'))
    except ValueError:
        answer = -1

    if not question_text or any(not opt for opt in options):
        flash('Question and all 4 options are required.', 'error')
        return redirect(url_for('admin_dashboard', subject=subject))

    if answer < 0 or answer > 3:
        flash('Select a valid correct option.', 'error')
        return redirect(url_for('admin_dashboard', subject=subject))

    new_question = {
        '_qid': f'custom-{uuid.uuid4().hex[:10]}',
        'question': question_text,
        'options': options,
        'answer': answer,
        'explanation': explanation,
    }

    store = load_questions_store()
    store['custom'][subject].append(new_question)
    save_questions_store(store)

    flash('Question added successfully.', 'success')
    return redirect(url_for('admin_dashboard', subject=subject))


@app.route('/admin/questions/delete', methods=['POST'])
@login_required
def admin_delete_question():
    if not is_admin_user(current_user):
        flash('Admin access only.', 'error')
        return redirect(url_for('home'))

    subject = canonical_subject(request.form.get('subject', ''))
    qid = request.form.get('qid', '').strip()
    source = request.form.get('source', '').strip()
    if subject not in ADMIN_SUBJECT_KEYS or not qid or source not in ('base', 'custom'):
        flash('Invalid request.', 'error')
        return redirect(url_for('admin_dashboard'))

    store = load_questions_store()
    changed = False
    if source == 'base':
        if qid not in store['deleted_base'][subject]:
            store['deleted_base'][subject].append(qid)
            changed = True
    else:
        before = len(store['custom'][subject])
        store['custom'][subject] = [q for q in store['custom'][subject] if q.get('_qid') != qid]
        changed = len(store['custom'][subject]) != before

    if changed:
        save_questions_store(store)
        flash('Question deleted successfully.', 'success')
    else:
        flash('Question not found.', 'error')

    return redirect(url_for('admin_dashboard', subject=subject))


@app.route('/api/quiz/progress', methods=['POST'])
@login_required
def save_quiz_progress():
    payload = request.get_json(silent=True) or {}
    subject = canonical_subject(payload.get('subject', ''))
    if subject not in ADMIN_SUBJECT_KEYS:
        return jsonify({'error': 'Invalid subject'}), 400

    try:
        score = int(payload.get('score', 0))
        total_questions = int(payload.get('total_questions', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid score payload'}), 400

    if total_questions <= 0:
        return jsonify({'error': 'total_questions must be greater than 0'}), 400

    score = max(0, min(score, total_questions))
    percentage = round((score / total_questions) * 100, 1)

    progress = ensure_user_progress(current_user)
    attempt = {
        'id': f'attempt-{uuid.uuid4().hex[:12]}',
        'subject': subject,
        'subject_title': QUIZ_SUBJECTS[subject],
        'score': score,
        'total_questions': total_questions,
        'percentage': percentage,
        'attempted_at': datetime.utcnow().isoformat(),
    }
    progress['attempts'].append(attempt)
    progress['attempts'] = progress['attempts'][-200:]

    subject_summary = progress['by_subject'].setdefault(subject, {
        'attempts': 0,
        'best': 0,
        'latest': 0,
    })
    subject_summary['attempts'] += 1
    subject_summary['best'] = max(subject_summary['best'], percentage)
    subject_summary['latest'] = percentage

    return jsonify({
        'message': 'Quiz progress saved',
        'attempt': attempt
    }), 201

# API Endpoints for questions
@app.route('/api/questions/<subject>', methods=['GET'])
def get_questions(subject):
    try:
        subject = canonical_subject(subject)
        questions = []

        if subject in quiz_enabled and not quiz_enabled[subject]:
            return jsonify({'error': 'This quiz is disabled by admin'}), 403

        if subject not in ADMIN_SUBJECT_KEYS:
            return jsonify({'error': 'Invalid subject'}), 400

        questions = get_merged_questions_for_subject(subject)

        return jsonify(questions)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Serve quiz pages
@app.route('/quiz/<subject>')
def quiz_page(subject):
    subject = canonical_subject(subject)
    if subject not in QUIZ_SUBJECTS:
        return "Invalid subject", 404

    if not quiz_enabled.get(subject, True):
        flash('This quiz is currently disabled by admin.', 'error')
        return redirect(url_for('home'))

    return render_template(
        'quiz_template.html',
        subject=subject,
        subject_title=QUIZ_SUBJECTS[subject]
    )

if __name__ == '__main__':
    # Create necessary directories
    import os
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Run the app
    app.run(debug=True, port=5000)
