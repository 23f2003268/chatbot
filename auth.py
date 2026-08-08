import secrets
from datetime import datetime
from functools import wraps
from flask import request, jsonify, redirect, url_for, g, current_app
from models import db, User, Session

SESSION_COOKIE_NAME = 'chat_session_id'

def get_current_session():
    """
    Verifies session token from HTTP-only cookie and checks server-side 15-second inactivity timeout.
    Updates last_activity timestamp on valid active requests.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None

    sess = Session.query.filter_by(token=token).first()
    if not sess:
        return None

    db.session.refresh(sess)

    now = datetime.utcnow()

    inactivity_seconds = (now - sess.last_activity).total_seconds()
    timeout = current_app.config.get('SESSION_INACTIVITY_TIMEOUT', 15)

    if inactivity_seconds > timeout:
        # Session expired due to inactivity -> remove from database
        db.session.delete(sess)
        db.session.commit()
        return None

    # Renew session activity timer
    sess.last_activity = now
    db.session.commit()
    return sess

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        sess = get_current_session()
        if not sess:
            if request.path.startswith('/api/'):
                response = jsonify({'error': 'Session expired or unauthorized'})
                response.status_code = 401
                return response
            return redirect(url_for('login_page'))
        
        g.current_session = sess
        g.current_user = sess.user
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        sess = get_current_session()
        if not sess or sess.user.role != 'ADMIN':
            if request.path.startswith('/api/'):
                response = jsonify({'error': 'Access denied. Admin required.'})
                response.status_code = 403
                return response
            return redirect(url_for('chat_page'))
        
        g.current_session = sess
        g.current_user = sess.user
        return f(*args, **kwargs)
    return decorated_function

def create_session_for_user(user_id):
    """Creates a new session record in DB and returns unpredictable token."""
    token = secrets.token_hex(32)
    sess = Session(user_id=user_id, token=token, last_activity=datetime.utcnow())
    db.session.add(sess)
    db.session.commit()
    return token

def revoke_session(token):
    """Deletes session from database."""
    if not token:
        return
    sess = Session.query.filter_by(token=token).first()
    if sess:
        db.session.delete(sess)
        db.session.commit()
