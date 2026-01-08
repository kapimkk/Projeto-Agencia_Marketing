import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    uri = os.getenv('DATABASE_URL', 'sqlite:///banco_final.db')
    
    if uri and uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_DATABASE_URI = uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False 

    # --- Segurança ---
    SECRET_KEY = os.getenv('SECRET_KEY', 'chave-dev-padrao')
    
    # Define cookies seguros apenas se estiver em produção (evita bugs locais)
    SESSION_COOKIE_SECURE = os.getenv('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax' 
    PERMANENT_SESSION_LIFETIME = 3600

    # --- Arquivos ---
    basedir = os.path.abspath(os.path.dirname(__file__)) 
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'csv', 'xlsx'}
    
    # --- Email ---
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 465  
    MAIL_USE_TLS = False 
    MAIL_USE_SSL = True  
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')