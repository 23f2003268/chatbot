import os
from dotenv import load_dotenv

# Load environment variables from .env if present
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod-12345')
    
    # Credentials from environment variables
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    USER_USERNAME = os.environ.get('USER_USERNAME', 'user')
    USER_PASSWORD = os.environ.get('USER_PASSWORD', 'user123')
    
    # Session inactivity timeout in seconds (Strict requirement: 15 seconds)
    SESSION_INACTIVITY_TIMEOUT = int(os.environ.get('SESSION_INACTIVITY_TIMEOUT', 15))
    
    # Database path inside instance directory
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(basedir, 'instance', 'chat.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload folder for private images (can be customized via env for cloud volumes like Render)
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(basedir, 'private_uploads', 'images'))
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB maximum upload size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

