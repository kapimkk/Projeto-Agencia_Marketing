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
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='client') # 'client' ou 'admin'
    
    # Relacionamentos com outras tabelas
    plan_info = db.relationship('ClientPlan', backref='user', uselist=False, cascade="all, delete-orphan")
    stats = db.relationship('ClientStat', backref='user', cascade="all, delete-orphan")

# Tabela de Planos dos Clientes
class ClientPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    plan_name = db.Column(db.String(50))
    benefits = db.Column(db.Text) # JSON com lista de benefícios

# Tabela para Estatísticas do Gráfico do Cliente
class ClientStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    label = db.Column(db.String(50)) # Mês/Data
    value = db.Column(db.Float) # Valor do gráfico
    type = db.Column(db.String(20))

# Tabela de Visitas do Site
class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page = db.Column(db.String(50))
    date = db.Column(db.DateTime, default=datetime.utcnow)

# Tabela de Leads (Formulário de Contato)
class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    projeto = db.Column(db.Text)
    data = db.Column(db.DateTime, default=datetime.utcnow)

# Tabela de Pedidos/Checkout
class Order(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plano = db.Column(db.String(50))
    preco = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Pendente')
    data = db.Column(db.DateTime, default=datetime.utcnow)

# Tabela de Avaliações
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    empresa = db.Column(db.String(100))
    email = db.Column(db.String(100))
    avaliacao = db.Column(db.Text)
    estrelas = db.Column(db.Integer)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    visivel = db.Column(db.Boolean, default=True) # Controle se aparece ou não no site

# Tabela de Sessões de Chat (Tickets)
class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_uuid = db.Column(db.String(50), unique=True)
    category = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Aberto')
    client_name = db.Column(db.String(100))
    client_phone = db.Column(db.String(30))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Se for null, é visitante anônimo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Tabela de Mensagens do Chat
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'))
    tipo = db.Column(db.String(20)) # 'texto' ou 'audio'
    conteudo = db.Column(db.Text)
    remetente = db.Column(db.String(20))
    data = db.Column(db.DateTime, default=datetime.utcnow)
    
# Tabela de Logs de Auditoria
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    action = db.Column(db.String(50))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)