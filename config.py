import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Configurações de Banco de Dados e Segurança
    SECRET_KEY = os.getenv('SECRET_KEY', 'chave-dev-padrao')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///banco_final.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Caminho absoluto
    basedir = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 465  
    MAIL_USE_TLS = False 
    MAIL_USE_SSL = True  
    
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Limite de 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'csv', 'xlsx'}

    SESSION_COOKIE_SECURE = False      # Só envia cookie via HTTPS (Ative apenas quando tiver SSL/Domínio)
    SESSION_COOKIE_HTTPONLY = True    # JavaScript não consegue ler o cookie
    SESSION_COOKIE_SAMESITE = 'Lax'   # Previne ataques CSRF de outros sites