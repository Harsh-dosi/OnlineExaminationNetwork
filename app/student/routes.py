import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.models.db import get_db, log_network_event
from app.auth.routes import login_required, student_required, verify_csrf_token, generate_csrf_token

bp = Blueprint('student', __name__, url_prefix='/student')

@bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    """
    Student Dashboard.
    Displays available examination, instructions, and past attempt history.
    """
    db = get_db()
    user_id = session['user_id']

    # Get active examination
    exam = db.execute(
        "SELECT * FROM examinations WHERE is_active = 1 ORDER BY id ASC LIMIT 1"
    ).fetchone()

    question_count = 0
    if exam:
        q_row = db.execute(
            "SELECT COUNT(*) as count FROM questions WHERE exam_id = ?",
            (exam['id'],)
        ).fetchone()
        question_count = q_row['count'] if q_row else 0

    # Get student's previous attempts
    attempts = db.execute(
        """SELECT a.*, e.title as exam_title 
           FROM exam_attempts a 
           JOIN examinations e ON a.exam_id = e.id 
           WHERE a.user_id = ? 
           ORDER BY a.start_time DESC""",
        (user_id,)
    ).fetchall()

    return render_template(
        'student_dashboard.html',
        exam=exam,
        question_count=question_count,
        attempts=attempts
    )

@bp.route('/exam/<int:exam_id>/start', methods=['GET', 'POST'])
@login_required
@student_required
def start_exam(exam_id):
    """
    Start or resume an examination attempt.
    Enforces server-side timer validation and prevents duplicate active attempts.
    """
    db = get_db()
    user_id = session['user_id']

    exam = db.execute("SELECT * FROM examinations WHERE id = ? AND is_active = 1", (exam_id,)).fetchone()
    if not exam:
        flash("Examination not found or currently inactive.", "danger")
        return redirect(url_for('student.dashboard'))

    # Check for an existing in-progress attempt
    attempt = db.execute(
        "SELECT * FROM exam_attempts WHERE user_id = ? AND exam_id = ? AND status = 'in_progress' ORDER BY id DESC LIMIT 1",
        (user_id, exam_id)
    ).fetchone()

    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

   
    if not attempt:
        # Create new in-progress attempt
        cursor = db.execute(
            """INSERT INTO exam_attempts (user_id, exam_id, start_time, status, client_ip)
               VALUES (?, ?, ?, 'in_progress', ?)""",
            (user_id, exam_id, now_str, request.remote_addr)
        )
        db.commit()
        attempt_id = cursor.lastrowid
        attempt_start = now
    else:
        attempt_id = attempt['id']
        raw_start_time = attempt['start_time']
        attempt_start = (
            datetime.datetime.strptime(raw_start_time, "%Y-%m-%d %H:%M:%S")
            if isinstance(raw_start_time, str)
            else raw_start_time
        )


    # Calculate remaining time in seconds based on server start_time and duration
    elapsed_seconds = int((now - attempt_start).total_seconds())
    total_allowed_seconds = exam['duration_minutes'] * 60
    remaining_seconds = max(0, total_allowed_seconds - elapsed_seconds)

    if remaining_seconds <= 0:
        # Time expired while client was away
        db.execute(
            "UPDATE exam_attempts SET status = 'timed_out', submitted_at = ? WHERE id = ?",
            (now_str, attempt_id)
        )
        db.commit()
        flash("Examination time has expired.", "warning")
        return redirect(url_for('student.result', attempt_id=attempt_id))

    # Fetch questions (WITHOUT exposing correct_option or explanation to student!)
    questions = db.execute(
        """SELECT id, exam_id, question_text, option_a, option_b, option_c, option_d, marks 
           FROM questions WHERE exam_id = ? ORDER BY id ASC""",
        (exam_id,)
    ).fetchall()

    return render_template(
        'exam.html',
        exam=exam,
        attempt_id=attempt_id,
        questions=questions,
        remaining_seconds=remaining_seconds,
        csrf_token=generate_csrf_token()
    )

@bp.route('/exam/submit', methods=['POST'])
@login_required
@student_required
def submit_exam():
    """
    Process exam submission:
    - Verifies CSRF token
    - Prevents duplicate submission
    - Validates server-side duration
    - Automatically calculates score and percentage
    - Persists answers in SQLite
    """
    if not verify_csrf_token():
        flash("Security validation failed during submission. Please try again.", "danger")
        return redirect(url_for('student.dashboard'))

    attempt_id = request.form.get('attempt_id', type=int)
    db = get_db()
    user_id = session['user_id']

    attempt = db.execute(
        "SELECT * FROM exam_attempts WHERE id = ? AND user_id = ?",
        (attempt_id, user_id)
    ).fetchone()

    if not attempt:
        flash("Invalid examination attempt record.", "danger")
        return redirect(url_for('student.dashboard'))

    if attempt['status'] in ('completed', 'timed_out'):
        flash("This examination has already been submitted.", "info")
        return redirect(url_for('student.result', attempt_id=attempt_id))

    exam = db.execute("SELECT * FROM examinations WHERE id = ?", (attempt['exam_id'],)).fetchone()
    questions = db.execute("SELECT * FROM questions WHERE exam_id = ?", (attempt['exam_id'],)).fetchall()

    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Server-side duration check (with 60-second grace buffer for network transmission latency)
    raw_start_time = attempt['start_time']
    start_time = (
        datetime.datetime.strptime(raw_start_time, "%Y-%m-%d %H:%M:%S")
        if isinstance(raw_start_time, str)
        else raw_start_time
    )
    elapsed_seconds = (now - start_time).total_seconds()
    max_allowed = (exam['duration_minutes'] * 60) + 60
    is_timed_out = elapsed_seconds > max_allowed

    total_score = 0
    total_possible = 0

    # Grade submitted answers
    for q in questions:
        q_id = q['id']
        total_possible += q['marks']
        selected = request.form.get(f'q_{q_id}')

        if selected and selected.upper() in ('A', 'B', 'C', 'D'):
            selected_option = selected.upper()
            is_correct = 1 if selected_option == q['correct_option'] else 0
            awarded = q['marks'] if is_correct else 0
        else:
            selected_option = None
            is_correct = 0
            awarded = 0

        total_score += awarded

        # Upsert submitted answer
        db.execute(
            """INSERT INTO submitted_answers (attempt_id, question_id, selected_option, is_correct, marks_awarded)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(attempt_id, question_id) DO UPDATE SET
                   selected_option = excluded.selected_option,
                   is_correct = excluded.is_correct,
                   marks_awarded = excluded.marks_awarded""",
            (attempt_id, q_id, selected_option, is_correct, awarded)
        )

    percentage = round((total_score / total_possible * 100), 2) if total_possible > 0 else 0.0
    status = 'timed_out' if is_timed_out else 'completed'

    db.execute(
        """UPDATE exam_attempts 
           SET submitted_at = ?, score = ?, total_possible = ?, percentage = ?, status = ?
           WHERE id = ?""",
        (now_str, total_score, total_possible, percentage, status, attempt_id)
    )
    db.commit()

    log_network_event(
        "EXAM_SUBMISSION",
        request.remote_addr,
        f"Student '{session['username']}' submitted Exam #{exam['id']}. Score: {total_score}/{total_possible} ({percentage}%) Status: {status}.",
        200
    )

    flash("Examination submitted successfully! Review your result below.", "success")
    return redirect(url_for('student.result', attempt_id=attempt_id))

@bp.route('/result/<int:attempt_id>')
@login_required
def result(attempt_id):
    """
    Display examination result and answer review.
    Students can view only their own attempts; administrators can view any attempt.
    """
    db = get_db()
    attempt = db.execute(
        """SELECT a.*, u.username, u.full_name, e.title as exam_title, e.pass_marks 
           FROM exam_attempts a 
           JOIN users u ON a.user_id = u.id 
           JOIN examinations e ON a.exam_id = e.id 
           WHERE a.id = ?""",
        (attempt_id,)
    ).fetchone()

    if not attempt:
        flash("Attempt record not found.", "danger")
        return redirect(url_for('student.dashboard'))

    # Authorization check
    if session.get('role') != 'admin' and attempt['user_id'] != session['user_id']:
        flash("Unauthorized access to result record.", "danger")
        return redirect(url_for('student.dashboard'))

    # Load submitted answers with full question context & explanations for educational feedback
    answers = db.execute(
        """SELECT q.id as question_id, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d,
                  q.correct_option, q.explanation, q.marks,
                  sa.selected_option, sa.is_correct, sa.marks_awarded
           FROM questions q
           LEFT JOIN submitted_answers sa ON q.id = sa.question_id AND sa.attempt_id = ?
           WHERE q.exam_id = ?
           ORDER BY q.id ASC""",
        (attempt_id, attempt['exam_id'])
    ).fetchall()

    passed = attempt['score'] >= attempt['pass_marks']

    return render_template(
        'result.html',
        attempt=attempt,
        answers=answers,
        passed=passed
    )
