from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import uuid
import json

db = SQLAlchemy()

# Tabela de Usuários (Clientes e Admins)
class User(db.Model, UserMixin): 
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(100))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='client') # 'client' ou 'admin'
    
    # Relacionamentos
    plan_info = db.relationship('ClientPlan', backref='user', uselist=False, cascade="all, delete-orphan")
    stats = db.relationship('ClientStat', backref='user', cascade="all, delete-orphan")

# Tabela dos Planos Públicos (Home Page)
class PublicPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    price = db.Column(db.String(20))
    benefits = db.Column(db.Text) # Lista JSON
    is_highlighted = db.Column(db.Boolean, default=False) # Se é o destaque (Growth)
    order_index = db.Column(db.Integer, default=0) # Ordem de exibição

# Tabela de Planos dos Clientes (Área Logada)
class ClientPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    plan_name = db.Column(db.String(50))
    benefits = db.Column(db.Text)

# Estatísticas do Gráfico do Cliente
class ClientStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    label = db.Column(db.String(50))
    value = db.Column(db.Float)
    type = db.Column(db.String(20))

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
    metodo = db.Column(db.String(20))
    data = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    empresa = db.Column(db.String(100))
    email = db.Column(db.String(100))
    avaliacao = db.Column(db.Text)
    estrelas = db.Column(db.Integer)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    visivel = db.Column(db.Boolean, default=True)

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_uuid = db.Column(db.String(50), unique=True)
    category = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Aberto')
    client_name = db.Column(db.String(100))
    client_phone = db.Column(db.String(30))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'))
    tipo = db.Column(db.String(20))
    conteudo = db.Column(db.Text)
    remetente = db.Column(db.String(20))
    data = db.Column(db.DateTime, default=datetime.utcnow)

# --- NOVAS TABELAS PARA O CMS ---
class PortfolioItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    description = db.Column(db.String(200))
    image_url = db.Column(db.String(300))
    
class SiteConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True)
    value = db.Column(db.Text)
