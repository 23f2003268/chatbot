import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response, g
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from models import db, User, SystemState
from auth import (
    login_required,
    get_current_session,
    create_session_for_user,
    revoke_session,
    SESSION_COOKIE_NAME
)
from chat import chat_bp

def create_app(config_override=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_override:
        app.config.update(config_override)

    # Ensure dynamic environment variables are loaded at app creation time
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', app.config.get('SECRET_KEY'))
    app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', app.config.get('ADMIN_USERNAME'))
    app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', app.config.get('ADMIN_PASSWORD'))
    app.config['USER_USERNAME'] = os.environ.get('USER_USERNAME', app.config.get('USER_USERNAME'))
    app.config['USER_PASSWORD'] = os.environ.get('USER_PASSWORD', app.config.get('USER_PASSWORD'))
    if os.environ.get('SESSION_INACTIVITY_TIMEOUT'):
        app.config['SESSION_INACTIVITY_TIMEOUT'] = int(os.environ['SESSION_INACTIVITY_TIMEOUT'])

    # Initialize SQLAlchemy database
    db.init_app(app)



    # Ensure required folders exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    instance_dir = os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
    if instance_dir:
        os.makedirs(instance_dir, exist_ok=True)

    # Register chat blueprint
    app.register_blueprint(chat_bp)

    with app.app_context():
        db.create_all()

        # Provision initial accounts from environment if missing
        admin_user = User.query.filter_by(role='ADMIN').first()
        if not admin_user:
            admin_user = User(
                username=app.config['ADMIN_USERNAME'],
                password_hash=generate_password_hash(app.config['ADMIN_PASSWORD']),
                role='ADMIN'
            )
            db.session.add(admin_user)

        user_acct = User.query.filter_by(role='USER').first()
        if not user_acct:
            user_acct = User(
                username=app.config['USER_USERNAME'],
                password_hash=generate_password_hash(app.config['USER_PASSWORD']),
                role='USER'
            )
            db.session.add(user_acct)

        # Provision system state record if missing
        system_state = SystemState.query.first()
        if not system_state:
            system_state = SystemState()
            db.session.add(system_state)

        db.session.commit()

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @app.route('/')
    def index():
        sess = get_current_session()
        if sess:
            return redirect(url_for('chat_page'))
        return redirect(url_for('login_page'))

    @app.route('/login', methods=['GET'])
    def login_page():
        sess = get_current_session()
        if sess:
            return redirect(url_for('chat_page'))
        return render_template('login.html', error=None)

    @app.route('/login', methods=['POST'])
    def login_action():
        data = request.get_json(silent=True)
        if data:
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            is_json = True
        else:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            is_json = False

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            if is_json:
                return jsonify({'error': 'Invalid username or password'}), 401
            return render_template('login.html', error='Invalid username or password'), 401

        # Successful authentication -> create server-side session
        token = create_session_for_user(user.id)

        if is_json:
            response = make_response(jsonify({'status': 'ok', 'redirect': url_for('chat_page')}))
        else:
            response = make_response(redirect(url_for('chat_page')))

        # Set secure HTTP-only cookie containing only unpredictable session token
        response.set_cookie(
            SESSION_COOKIE_NAME,
            token,
            httponly=True,
            samesite='Strict',
            path='/'
        )
        return response

    @app.route('/logout', methods=['GET', 'POST'])
    def logout_action():
        token = request.cookies.get(SESSION_COOKIE_NAME)
        revoke_session(token)

        if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
            response = make_response(jsonify({'status': 'ok', 'redirect': url_for('login_page')}))
        else:
            response = make_response(redirect(url_for('login_page')))

        response.set_cookie(SESSION_COOKIE_NAME, '', expires=0, path='/')
        return response

    @app.route('/chat', methods=['GET'])
    @login_required
    def chat_page():
        user = g.current_user
        if user.role == 'ADMIN':
            return render_template('admin.html', username=user.username, role=user.role)
        return render_template('user.html', username=user.username, role=user.role)

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
