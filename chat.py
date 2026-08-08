import os
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_from_directory, current_app, g
from PIL import Image

from models import db, Message, SystemState
from auth import login_required, admin_required

chat_bp = Blueprint('chat', __name__)

def get_user_visible_messages():
    """
    Applies the server-side visibility rules for USER:
    1. Only messages created AFTER system_state.user_visible_from (if set).
    2. Only messages created within the rolling latest 3 minutes.
    3. Maximum latest 10 messages cumulative (USER + ADMIN).
    Returns a list of Message objects in chronological order (ASC).
    """
    state = SystemState.query.first()
    user_visible_from = state.user_visible_from if state else None
    three_minutes_ago = datetime.utcnow() - timedelta(minutes=3)

    # Determine effective cutoff timestamp
    if user_visible_from and user_visible_from > three_minutes_ago:
        cutoff = user_visible_from
    else:
        cutoff = three_minutes_ago

    # Fetch latest 10 messages after cutoff, ordered DESC
    visible = Message.query.filter(Message.created_at >= cutoff)\
                           .order_by(Message.created_at.desc(), Message.id.desc())\
                           .limit(10).all()
    
    # Reverse to return in chronological order
    visible.reverse()
    return visible

@chat_bp.route('/api/messages', methods=['GET'])
@login_required
def get_messages():
    user = g.current_user

    if user.role == 'ADMIN':
        # ADMIN sees complete historical message log
        messages = Message.query.order_by(Message.created_at.asc(), Message.id.asc()).all()
    else:
        # USER sees strictly filtered subset (3-min window, 10-message max, post-clear boundary)
        messages = get_user_visible_messages()

    return jsonify({'messages': [m.to_dict() for m in messages]})

@chat_bp.route('/api/messages', methods=['POST'])
@login_required
def send_message():
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()

    if not text:
        return jsonify({'error': 'Message text cannot be empty'}), 400

    if len(text) > 5000:
        return jsonify({'error': 'Message text too long'}), 400

    msg = Message(
        sender_role=g.current_user.role,
        sender_username=g.current_user.username,
        message_type='text',
        text_content=text,
        created_at=datetime.utcnow()
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify({'status': 'ok', 'message': msg.to_dict()}), 201

@chat_bp.route('/api/upload-image', methods=['POST'])
@login_required
def upload_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'No selected image file'}), 400

    # Extension check
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    allowed = {'.' + e for e in current_app.config['ALLOWED_EXTENSIONS']}
    if ext not in allowed:
        return jsonify({'error': 'Unsupported file extension'}), 400

    # Server-side MIME & PIL image verification
    try:
        img = Image.open(file.stream)
        img.verify()
        if img.format.lower() not in ['jpeg', 'png', 'webp']:
            return jsonify({'error': 'Invalid image format'}), 400
    except Exception:
        return jsonify({'error': 'Invalid or corrupted image file'}), 400

    file.stream.seek(0)

    # Generate secure random filename
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, safe_filename)

    file.save(file_path)

    msg = Message(
        sender_role=g.current_user.role,
        sender_username=g.current_user.username,
        message_type='image',
        image_filename=safe_filename,
        created_at=datetime.utcnow()
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify({'status': 'ok', 'message': msg.to_dict()}), 201

@chat_bp.route('/api/image/<int:message_id>', methods=['GET'])
@login_required
def serve_image(message_id):
    msg = db.session.get(Message, message_id)
    if not msg or msg.message_type != 'image' or not msg.image_filename:
        return jsonify({'error': 'Image not found'}), 404


    # Enforce user authorization check for USER role
    if g.current_user.role == 'USER':
        allowed_messages = get_user_visible_messages()
        allowed_ids = {m.id for m in allowed_messages}
        if msg.id not in allowed_ids:
            return jsonify({'error': 'Access denied to this image'}), 403

    upload_folder = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_folder, msg.image_filename)

@chat_bp.route('/api/admin/clear-user-screen', methods=['POST'])
@admin_required
def clear_user_screen():
    state = SystemState.query.first()
    if not state:
        state = SystemState()
        db.session.add(state)
    
    state.user_visible_from = datetime.utcnow()
    db.session.commit()

    return jsonify({'status': 'ok', 'message': 'User screen cleared successfully'})

@chat_bp.route('/api/admin/delete-all', methods=['POST'])
@admin_required
def delete_all():
    # Remove image files
    upload_folder = current_app.config['UPLOAD_FOLDER']
    if os.path.exists(upload_folder):
        for fname in os.listdir(upload_folder):
            if fname == '.gitkeep':
                continue
            fpath = os.path.join(upload_folder, fname)
            if os.path.isfile(fpath):
                try:
                    os.remove(fpath)
                except OSError:
                    pass

    # Permanently delete all message records
    Message.query.delete()

    # Reset clear boundary
    state = SystemState.query.first()
    if state:
        state.user_visible_from = None

    db.session.commit()

    return jsonify({'status': 'ok', 'message': 'All messages deleted permanently'})
