import os
import uuid
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, func
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

from config import Config
from models import db, User, Lead, Order, Review, ChatSession, ChatMessage, Visit, AuditLog, ClientPlan, ClientStat
from forms import LoginForm

app = Flask(__name__)
app.config.from_object(Config)

# Configurações
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx'}
if not os.path.exists(app.config['UPLOAD_FOLDER']): os.makedirs(app.config['UPLOAD_FOLDER'])

db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'client_login'

limiter = Limiter(get_remote_address, app=app, default_limits=["2000 per day", "500 per hour"], storage_uri="memory://")
csp = { 'default-src': '\'self\'', 'script-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com', 'https://unpkg.com'], 'style-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdnjs.cloudflare.com', 'https://fonts.googleapis.com'], 'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'], 'img-src': ['\'self\'', 'data:', 'https://images.unsplash.com', 'https://api.qrserver.com'], 'connect-src': ['\'self\''] }
Talisman(app, content_security_policy=csp, force_https=False)

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

# Decorator de Segurança Melhorado (Evita erro 403, redireciona)
def admin_required(f):
    def wrap(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('admin_login'))
        if current_user.role != 'admin':
            flash('Acesso negado. Área exclusiva para administradores.')
            return redirect(url_for('client_login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# --- LOGIN ---
@app.route('/cliente/login', methods=['GET', 'POST'])
def client_login():
    if current_user.is_authenticated:
        if current_user.role == 'client': return redirect(url_for('client_dashboard'))
        logout_user()
    form = LoginForm()
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form.get('username')).first()
        if u and check_password_hash(u.password_hash, request.form.get('password')):
            if u.role == 'client': login_user(u); return redirect(url_for('client_dashboard'))
            else: flash('Use o login de Admin.')
        else: flash('Dados incorretos.')
    return render_template('login.html', form=form, login_type="Cliente")

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        if current_user.role == 'admin': return redirect(url_for('admin'))
        logout_user()
    form = LoginForm()
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form.get('username')).first()
        if u and check_password_hash(u.password_hash, request.form.get('password')):
            if u.role == 'admin': login_user(u); return redirect(url_for('admin'))
            else: flash('Acesso negado.')
        else: flash('Dados incorretos.')
    return render_template('login.html', form=form, login_type="Admin")

@app.route('/logout')
@login_required
def logout():
    r = current_user.role; logout_user()
    return redirect(url_for('admin_login')) if r == 'admin' else redirect(url_for('client_login'))

# --- ROTAS GERAIS ---
@app.route('/')
def index():
    try: db.session.add(Visit(page='home')); db.session.commit()
    except: pass
    return render_template('index.html')

@app.route('/avaliacoes')
def reviews():
    return render_template('reviews.html', reviews=Review.query.filter_by(visivel=True).order_by(Review.data.desc()).all())

@app.route('/checkout/<plano>')
def checkout(plano):
    precos = {'Start': '1.500,00', 'Growth': '3.200,00', 'Scale': '7.000,00'}
    return render_template('checkout.html', plano=plano, preco=precos.get(plano, 'Consultar'))

# --- AÇÕES ---
@app.route('/processar_pagamento', methods=['POST'])
@csrf.exempt
def processar_pagamento():
    try: db.session.add(Order(plano=request.json.get('plano'), preco=request.json.get('preco'))); db.session.commit(); return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

@app.route('/submit_lead', methods=['POST'])
@csrf.exempt
def submit_lead():
    try:
        db.session.add(Lead(nome=request.form.get('nome'), email=request.form.get('email'), telefone=request.form.get('telefone'), projeto=request.form.get('projeto')))
        db.session.commit()
        return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

@app.route('/submit_review', methods=['POST'])
@csrf.exempt
def submit_review():
    try:
        d = request.json
        db.session.add(Review(nome=d.get('nome'), empresa=d.get('empresa'), email=d.get('email'), avaliacao=d.get('avaliacao'), estrelas=int(d.get('estrelas',5)), visivel=True))
        db.session.commit()
        return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

# --- DASHBOARD CLIENTE ---
@app.route('/cliente')
@login_required
def client_dashboard():
    if current_user.role != 'client': return redirect(url_for('admin_login'))
    
    plan = ClientPlan.query.filter_by(user_id=current_user.id).first()
    stats = ClientStat.query.filter_by(user_id=current_user.id).all()
    
    chart_data = {'labels': [], 'values': []}
    for s in stats: chart_data['labels'].append(s.label); chart_data['values'].append(s.value)
    
    benefits = json.loads(plan.benefits) if plan and plan.benefits else []
    
    chat_session = ChatSession.query.filter_by(user_id=current_user.id, status='Aberto').first()
    messages = []
    if chat_session:
        messages = ChatMessage.query.filter_by(session_id=chat_session.id).order_by(ChatMessage.data).all()

    return render_template('client_dashboard.html', 
                           user=current_user, plan=plan, benefits=benefits, 
                           chart_data=json.dumps(chart_data),
                           chat_session=chat_session, messages=messages)

@app.route('/client/send_message', methods=['POST'])
@login_required
def client_send_message():
    if current_user.role != 'client': return jsonify({'error': 'Unauthorized'}), 403
    msg = request.form.get('message')
    
    sess = ChatSession.query.filter_by(user_id=current_user.id, status='Aberto').first()
    if not sess:
        # Cria sessão vinculada ao usuário
        sess = ChatSession(session_uuid=uuid.uuid4().hex, user_id=current_user.id, client_name=current_user.name, category='Cliente Dashboard', status='Aberto')
        db.session.add(sess); db.session.commit()
        db.session.add(ChatMessage(session_id=sess.id, tipo='texto', remetente='system', conteudo='Olá! Em que posso ajudar?'))
        
    db.session.add(ChatMessage(session_id=sess.id, tipo='texto', remetente='user', conteudo=msg))
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/client/get_chat', methods=['GET'])
@login_required
def client_get_chat():
    sess = ChatSession.query.filter_by(user_id=current_user.id, status='Aberto').first()
    if not sess: return jsonify({'messages': []})
    msgs = ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all()
    return jsonify({'messages': [{'remetente': m.remetente, 'conteudo': m.conteudo, 'tipo': m.tipo} for m in msgs]})

# --- ADMIN TOTAL ---
@app.route('/admin')
@login_required
@admin_required
def admin():
    tab = request.args.get('tab', 'dashboard')
    
    # Dados Reais Leads
    last_7_days = datetime.now() - timedelta(days=7)
    leads_data = db.session.query(func.date(Lead.data), func.count(Lead.id)).filter(Lead.data >= last_7_days).group_by(func.date(Lead.data)).all()
    chart_map = {(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d'): 0 for i in range(6, -1, -1)}
    for date_obj, count in leads_data: chart_map[str(date_obj)] = count
    leads_chart = {'labels': [datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m') for d in chart_map.keys()], 'values': list(chart_map.values())}

    # Dados Gerais
    total_visits = Visit.query.count()
    total_leads = Lead.query.count()
    total_sales = Order.query.count()
    leads = Lead.query.order_by(Lead.data.desc()).all()
    reviews = Review.query.order_by(Review.data.desc()).all()
    orders = Order.query.order_by(Order.data.desc()).all()
    
    # GESTÃO DE CLIENTES
    clients = User.query.filter_by(role='client').all()
    
    # SEPARAÇÃO DE CHATS (Site vs Clientes Logados)
    public_chats = ChatSession.query.filter(ChatSession.user_id == None).order_by(ChatSession.created_at.desc()).all()
    client_chats = ChatSession.query.filter(ChatSession.user_id != None).order_by(ChatSession.created_at.desc()).all()
    
    # Chat Admin Ativo
    active_uuid = request.args.get('session_id')
    chat_history, active_ticket = [], ""
    if active_uuid:
        sess = ChatSession.query.filter_by(session_uuid=active_uuid).first()
        if sess:
            chat_history = ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all()
            active_ticket = sess.client_name
    
    # Adicionar UUID auxiliar para o template
    for s in public_chats: s.uuid = s.session_uuid
    for s in client_chats: s.uuid = s.session_uuid

    return render_template('admin.html', 
                           leads=leads, reviews=reviews, clients=clients, orders=orders,
                           public_chats=public_chats, client_chats=client_chats,
                           total_visits=total_visits, total_leads=total_leads, total_sales=total_sales,
                           leads_chart=json.dumps(leads_chart),
                           active_tab=tab, active_session=active_uuid, chat_history=chat_history, active_ticket=active_ticket)

# --- ADMIN ACTIONS ---
@app.route('/admin/create_client', methods=['POST'])
@login_required
@admin_required
def create_client():
    u = request.form.get('username')
    if User.query.filter_by(username=u).first(): flash('Usuário já existe'); return redirect(url_for('admin', tab='clients'))
    new_user = User(username=u, password_hash=generate_password_hash(request.form.get('password')), name=request.form.get('name'), role='client')
    db.session.add(new_user); db.session.commit()
    # Padrões iniciais
    db.session.add(ClientPlan(user_id=new_user.id, plan_name=request.form.get('plan_name'), benefits=json.dumps(["Dashboard", "Suporte"])))
    db.session.add(ClientStat(user_id=new_user.id, label='Jan', value=0, type='growth'))
    db.session.commit(); return redirect(url_for('admin', tab='clients'))

@app.route('/admin/update_client_stats/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def update_client_stats(user_id):
    # Atualiza Gráfico
    ClientStat.query.filter_by(user_id=user_id).delete()
    labels = request.form.getlist('labels[]'); values = request.form.getlist('values[]')
    for l, v in zip(labels, values):
        if l and v: db.session.add(ClientStat(user_id=user_id, label=l, value=float(v), type='growth'))
    
    # Atualiza Plano e Benefícios
    plan = ClientPlan.query.filter_by(user_id=user_id).first()
    if plan: 
        plan.plan_name = request.form.get('plan_name')
        plan.benefits = json.dumps([b.strip() for b in request.form.get('benefits').split(',')])
    
    db.session.commit()
    flash('Dados do cliente atualizados com sucesso.')
    return redirect(url_for('admin', tab='clients'))

@app.route('/admin/delete_client/<int:id>')
@login_required
@admin_required
def delete_client(id): User.query.filter_by(id=id).delete(); db.session.commit(); return redirect(url_for('admin', tab='clients'))

@app.route('/admin/toggle_review/<int:id>')
@login_required
@admin_required
def toggle_review(id):
    r = db.session.get(Review, id)
    if r: r.visivel = not r.visivel; db.session.commit()
    return redirect(url_for('admin', tab='reviews'))

@app.route('/admin/delete_review/<int:id>')
@login_required
@admin_required
def delete_review(id): Review.query.filter_by(id=id).delete(); db.session.commit(); return redirect(url_for('admin', tab='reviews'))

# --- CHAT WIDGET PÚBLICO (Suporte) ---
@app.route('/init_session', methods=['POST'])
@csrf.exempt
def init_session():
    d = request.json
    ns = ChatSession(session_uuid=uuid.uuid4().hex, category=d.get('category'), client_name=d.get('name'), client_phone=d.get('phone'), status='Aberto')
    db.session.add(ns); db.session.commit(); db.session.add(ChatMessage(session_id=ns.id, tipo='texto', conteudo=f"Olá {d.get('name')}.", remetente='system')); db.session.commit()
    return jsonify({'status': 'success', 'session_id': ns.session_uuid, 'ticket': f"#{ns.id:04d}", 'category': ns.category})

@app.route('/send_chat', methods=['POST'])
@csrf.exempt
def send_chat():
    suuid = request.form.get('session_id'); rem = request.form.get('remetente'); sess = ChatSession.query.filter_by(session_uuid=suuid).first()
    if not sess: return jsonify({'status': 'error'}), 404
    if 'message' in request.form: db.session.add(ChatMessage(session_id=sess.id, tipo='texto', conteudo=request.form['message'], remetente=rem))
    if 'audio' in request.files: f = request.files['audio']; n = f"audio_{uuid.uuid4().hex}.webm"; f.save(os.path.join(app.config['UPLOAD_FOLDER'], n)); db.session.add(ChatMessage(session_id=sess.id, tipo='audio', conteudo=n, remetente=rem))
    db.session.commit(); return jsonify({'status': 'success'})

@app.route('/get_messages/<session_uuid>') 
def get_messages(session_uuid):
    sess = ChatSession.query.filter_by(session_uuid=session_uuid).first()
    msgs = ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all() if sess else []
    return jsonify({'messages': [{'remetente': m.remetente, 'conteudo': m.conteudo, 'tipo': m.tipo} for m in msgs], 'status': sess.status if sess else 'Closed'})

@app.route('/close_ticket/<session_uuid>', methods=['POST'])
@csrf.exempt
@login_required
def close_ticket(session_uuid):
    sess = ChatSession.query.filter_by(session_uuid=session_uuid).first(); 
    if sess: sess.status = 'Encerrado'; db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/delete_ticket/<session_uuid>', methods=['DELETE'])
@csrf.exempt 
@login_required
def delete_ticket(session_uuid):
    sess = ChatSession.query.filter_by(session_uuid=session_uuid).first()
    if sess: ChatMessage.query.filter_by(session_id=sess.id).delete(); db.session.delete(sess); db.session.commit()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Admin padrão
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', name="Super Admin", role='admin', password_hash=generate_password_hash('admin123')))
            db.session.commit()
    app.run(debug=False, port=5000)