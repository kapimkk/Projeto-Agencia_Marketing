import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Configurações de Banco de Dados e Segurança
    SECRET_KEY = os.getenv('SECRET_KEY', 'chave-dev-padrao') # Mude isso em produção!
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///banco_final.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False 
    
    # Credencial Mercado Pago (Obtenha em: https://www.mercadopago.com.br/developers/panel)
    MERCADO_PAGO_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN', 'TEST-00000000-0000-0000-0000-000000000000')

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

    SESSION_COOKIE_SECURE = False      # Ative apenas quando tiver SSL (HTTPS)
    SESSION_COOKIE_HTTPONLY = True   # Impede JS de ler cookies
    SESSION_COOKIE_SAMESITE = 'Lax' # Proteção CSRF
    # Segurança de Sessão
    PERMANENT_SESSION_LIFETIME = 3600 # Logout automático em 1 hora