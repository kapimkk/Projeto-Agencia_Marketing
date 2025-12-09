from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import uuid

db = SQLAlchemy()

class User(db.Model, UserMixin): 
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page = db.Column(db.String(50))
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    projeto = db.Column(db.Text)
    data = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plano = db.Column(db.String(50))
    preco = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Pendente')
    data = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    empresa = db.Column(db.String(100))
    email = db.Column(db.String(100))
    avaliacao = db.Column(db.Text)
    estrelas = db.Column(db.Integer)
    data = db.Column(db.DateTime, default=datetime.utcnow)

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_uuid = db.Column(db.String(50), unique=True)
    category = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Aberto')
    client_name = db.Column(db.String(100))
    client_phone = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'))
    tipo = db.Column(db.String(20))
    conteudo = db.Column(db.Text)
    remetente = db.Column(db.String(20))
    data = db.Column(db.DateTime, default=datetime.utcnow)

# --- NOVO: TABELA DE AUDITORIA DE SEGURANÇA ---
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer) # ID do Admin que fez a ação
    action = db.Column(db.String(50)) # O que fez (EX: DELETE_TICKET)
    details = db.Column(db.Text) # Detalhes
    ip_address = db.Column(db.String(50)) # IP de quem fez
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)