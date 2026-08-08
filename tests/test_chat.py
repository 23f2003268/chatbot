import os
import sys
import io
import time
from datetime import datetime, timedelta

# Ensure parent directory is in sys.path for importing app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from PIL import Image

from app import create_app
from models import db, User, Message, Session, SystemState


from sqlalchemy.pool import StaticPool

@pytest.fixture
def app():
    os.environ['SECRET_KEY'] = 'test-secret-key-123'
    os.environ['ADMIN_USERNAME'] = 'admin'
    os.environ['ADMIN_PASSWORD'] = 'adminpass123'
    os.environ['USER_USERNAME'] = 'user'
    os.environ['USER_PASSWORD'] = 'userpass123'
    os.environ['SESSION_INACTIVITY_TIMEOUT'] = '15'
    
    test_app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'connect_args': {'check_same_thread': False},
            'poolclass': StaticPool
        }
    })
    
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()



@pytest.fixture
def client(app):
    return app.test_client()

def login_as(client, username, password):
    return client.post('/login', json={'username': username, 'password': password})

# --- TESTS ---

def test_valid_admin_login(client):
    res = login_as(client, 'admin', 'adminpass123')
    assert res.status_code == 200
    assert 'chat_session_id' in res.headers.get('Set-Cookie', '')

def test_valid_user_login(client):
    res = login_as(client, 'user', 'userpass123')
    assert res.status_code == 200
    assert 'chat_session_id' in res.headers.get('Set-Cookie', '')

def test_invalid_credentials(client):
    res = login_as(client, 'admin', 'wrongpassword')
    assert res.status_code == 401
    assert 'error' in res.get_json()

def test_user_cannot_access_admin_routes(client):
    login_as(client, 'user', 'userpass123')

    res1 = client.post('/api/admin/clear-user-screen')
    assert res1.status_code == 403

    res2 = client.post('/api/admin/delete-all')
    assert res2.status_code == 403

def test_admin_can_access_admin_routes(client):
    login_as(client, 'admin', 'adminpass123')

    res1 = client.post('/api/admin/clear-user-screen')
    assert res1.status_code == 200

    res2 = client.post('/api/admin/delete-all')
    assert res2.status_code == 200

def test_session_inactivity_expiration(client, app):
    login_as(client, 'user', 'userpass123')

    # Initial call succeeds
    res1 = client.get('/api/messages')
    assert res1.status_code == 200

    # Retrieve cookie token and set last_activity to 60 seconds ago
    cookie = client.get_cookie('chat_session_id')
    token = cookie.value

    with app.app_context():
        sess = Session.query.filter_by(token=token).first()
        sess.last_activity = datetime.utcnow() - timedelta(seconds=60)
        db.session.commit()

    # Next call fails with 401
    res2 = client.get('/api/messages')
    assert res2.status_code == 401



def test_user_max_10_messages_rule(client, app):
    login_as(client, 'admin', 'adminpass123')

    # Send 15 messages as admin
    for i in range(15):
        client.post('/api/messages', json={'text': f'Message {i+1}'})

    # Log in as user and fetch messages
    login_as(client, 'user', 'userpass123')
    res = client.get('/api/messages')
    assert res.status_code == 200
    data = res.get_json()
    assert len(data['messages']) == 10
    # Should be the latest 10 (Message 6 to Message 15)
    assert data['messages'][0]['text'] == 'Message 6'
    assert data['messages'][-1]['text'] == 'Message 15'

def test_rolling_3_minute_rule_for_user(client, app):
    with app.app_context():
        u_admin = User.query.filter_by(role='ADMIN').first()
        u_user = User.query.filter_by(role='USER').first()

        # Create message 4 minutes ago
        old_msg = Message(
            sender_role='ADMIN',
            sender_username=u_admin.username,
            message_type='text',
            text_content='Old Message',
            created_at=datetime.utcnow() - timedelta(minutes=4)
        )
        # Create message 1 minute ago
        new_msg = Message(
            sender_role='USER',
            sender_username=u_user.username,
            message_type='text',
            text_content='New Message',
            created_at=datetime.utcnow() - timedelta(minutes=1)
        )
        db.session.add_all([old_msg, new_msg])
        db.session.commit()

    # User only sees New Message
    login_as(client, 'user', 'userpass123')
    res_user = client.get('/api/messages')
    msgs_user = res_user.get_json()['messages']
    assert len(msgs_user) == 1
    assert msgs_user[0]['text'] == 'New Message'

    # Admin sees both Old Message and New Message
    login_as(client, 'admin', 'adminpass123')
    res_admin = client.get('/api/messages')
    msgs_admin = res_admin.get_json()['messages']
    assert len(msgs_admin) == 2

def test_admin_clear_user_screen(client, app):
    login_as(client, 'admin', 'adminpass123')
    client.post('/api/messages', json={'text': 'Msg Before Clear'})

    # Admin clears user screen
    client.post('/api/admin/clear-user-screen')

    # Admin posts new message after clear
    client.post('/api/messages', json={'text': 'Msg After Clear'})

    # User checks messages
    login_as(client, 'user', 'userpass123')
    res_user = client.get('/api/messages')
    msgs_user = res_user.get_json()['messages']
    assert len(msgs_user) == 1
    assert msgs_user[0]['text'] == 'Msg After Clear'

    # Admin checks messages -> sees both
    login_as(client, 'admin', 'adminpass123')
    res_admin = client.get('/api/messages')
    msgs_admin = res_admin.get_json()['messages']
    assert len(msgs_admin) == 2

def test_admin_delete_all_permanently(client, app):
    login_as(client, 'admin', 'adminpass123')
    client.post('/api/messages', json={'text': 'Persistent Message'})

    # Execute permanent delete
    res_del = client.post('/api/admin/delete-all')
    assert res_del.status_code == 200

    # Verify database is empty
    with app.app_context():
        assert Message.query.count() == 0

    res_admin = client.get('/api/messages')
    assert len(res_admin.get_json()['messages']) == 0

def test_image_upload_and_serving(client, app):
    login_as(client, 'admin', 'adminpass123')

    # Create dummy PNG image in memory
    img = Image.new('RGB', (100, 100), color='blue')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    # Upload image
    res = client.post(
        '/api/upload-image',
        data={'file': (img_byte_arr, 'test.png')},
        content_type='multipart/form-data'
    )
    assert res.status_code == 201
    msg_data = res.get_json()['message']
    image_url = msg_data['image_url']

    # Serve image as admin
    img_res = client.get(image_url)
    assert img_res.status_code == 200
    assert img_res.content_type == 'image/png'

def test_logout_invalidation(client):
    login_as(client, 'user', 'userpass123')
    res_msg = client.get('/api/messages')
    assert res_msg.status_code == 200

    # Logout
    client.post('/logout')

    # Try accessing API again with old session
    res_after = client.get('/api/messages')
    assert res_after.status_code == 401

def test_export_chat_json(client, app):
    # User cannot export
    login_as(client, 'user', 'userpass123')
    res_user = client.get('/api/admin/export-json')
    assert res_user.status_code == 403

    # Admin can export JSON
    login_as(client, 'admin', 'adminpass123')
    client.post('/api/messages', json={'text': 'Test Export Message'})
    
    res_admin = client.get('/api/admin/export-json')
    assert res_admin.status_code == 200
    assert res_admin.content_type == 'application/json'
    data = res_admin.get_json()
    assert 'messages' in data
    assert len(data['messages']) >= 1
    assert data['messages'][-1]['text'] == 'Test Export Message'

