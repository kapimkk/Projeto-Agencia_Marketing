from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import uuid

db = SQLAlchemy()

def generate_uuid():
    return uuid.uuid4().hex

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.String(200)) # Dica 2: Hash de senha

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(120))
    telefone = db.Column(db.String(20))
    projeto = db.Column(db.Text)
    data = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid) # Dica 10: UUID
    plano = db.Column(db.String(50))
    preco = db.Column(db.Float)
    metodo = db.Column(db.String(50))
    parcelas = db.Column(db.String(20))
    status = db.Column(db.String(50), default='Pendente')
    data = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    empresa = db.Column(db.String(100))
    avaliacao = db.Column(db.Text)
    estrelas = db.Column(db.Integer)
    data = db.Column(db.DateTime, default=datetime.utcnow)

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_uuid = db.Column(db.String(36), unique=True, default=generate_uuid)
    category = db.Column(db.String(50), default='Geral') # <--- ADICIONE ISTO
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('ChatMessage', backref='session', lazy=True)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'))
    tipo = db.Column(db.String(20)) # texto, arquivo, audio
    conteudo = db.Column(db.Text)
    remetente = db.Column(db.String(20))
    data = db.Column(db.DateTime, default=datetime.utcnow)