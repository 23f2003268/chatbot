from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'ADMIN' or 'USER'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role
        }

class Session(db.Model):
    __tablename__ = 'sessions'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    last_activity = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('sessions', lazy=True, cascade='all, delete-orphan'))

class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    sender_role = db.Column(db.String(20), nullable=False)  # 'ADMIN' or 'USER'
    sender_username = db.Column(db.String(80), nullable=False)
    message_type = db.Column(db.String(20), nullable=False)  # 'text' or 'image'
    text_content = db.Column(db.Text, nullable=True)
    image_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'sender': self.sender_role,
            'username': self.sender_username,
            'type': self.message_type,
            'text': self.text_content if self.message_type == 'text' else None,
            'image_url': f'/api/image/{self.id}' if self.message_type == 'image' else None,
            'created_at': self.created_at.isoformat() + 'Z'
        }

class SystemState(db.Model):
    __tablename__ = 'system_state'

    id = db.Column(db.Integer, primary_key=True)
    user_visible_from = db.Column(db.DateTime, nullable=True)
