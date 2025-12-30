import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # --- Configurações de Banco de Dados ---
    # Captura a URL do banco. Se não existir, usa SQLite local.
    uri = os.getenv('DATABASE_URL', 'sqlite:///banco_final.db')
    
    # CORREÇÃO CRÍTICA PARA RENDER/HEROKU:
    # O SQLAlchemy exige 'postgresql://', mas o Render entrega 'postgres://'
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

    # --- Mercado Pago ---
    MERCADO_PAGO_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN', 'TEST-00000000-0000-0000-0000-000000000000')

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