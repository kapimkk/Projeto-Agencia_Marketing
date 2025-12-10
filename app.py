import os
import uuid
import json
import csv
import io
from threading import Thread
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from flask_mail import Mail, Message
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, func # <--- IMPORTANTE: func adicionado para performance

# Bibliotecas de Segurança
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

# Seus Arquivos Locais
from config import Config
from models import db, User, Lead, Order, Review, ChatSession, ChatMessage, Visit, AuditLog
from forms import LoginForm, LeadForm, ReviewForm

app = Flask(__name__)
app.config.from_object(Config)

# --- CONFIGURAÇÕES DE SEGURANÇA DE ARQUIVOS ---
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt', 'csv', 'xlsx'}

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# --- INICIALIZAÇÃO ---
db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- 1. SEGURANÇA: ANTI-DDOS E RATE LIMITING ---
limiter = Limiter(get_remote_address, app=app, default_limits=["2000 per day", "500 per hour"], storage_uri="memory://")

# --- 2. SEGURANÇA: CONTENT SECURITY POLICY (CSP) ---
csp = {
    'default-src': '\'self\'',
    'script-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com', 'https://unpkg.com'],
    'style-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdnjs.cloudflare.com', 'https://fonts.googleapis.com'],
    'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
    'img-src': ['\'self\'', 'data:', 'https://images.unsplash.com', 'https://api.qrserver.com', 'https://cdn-icons-png.flaticon.com'],
    'connect-src': ['\'self\'']
}
Talisman(app, content_security_policy=csp, force_https=False)

# --- 3. SEGURANÇA: HONEYPOTS ---
BANNED_IPS = set()
@app.before_request
def block_banned_ips():
    if request.remote_addr in BANNED_IPS: return jsonify({'error': 'Access Denied.'}), 403

@app.route('/wp-admin')
@app.route('/admin/login.php')
def honeypot():
    BANNED_IPS.add(request.remote_addr)
    return jsonify({'status': 'banned'}), 403

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

@app.template_filter('format_currency')
def format_currency(value):
    try: return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return f"R$ {value}"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def send_async_email(app, msg):
    with app.app_context():
        try: mail.send(msg)
        except Exception as e: print(f"Erro Email: {e}")

@app.errorhandler(404)
def page_not_found(e): return render_template('404.html'), 404

# --- ROTAS PRINCIPAIS ---
@app.route('/')
def index():
    try: v = Visit(page='home'); db.session.add(v); db.session.commit()
    except: pass
    return render_template('index.html')

@app.route('/checkout/<plano>')
def checkout(plano):
    precos = {'Start': '1.500,00', 'Growth': '3.200,00', 'Scale': '7.000,00'}
    return render_template('checkout.html', plano=plano, preco=precos.get(plano, 'Consultar'))

@app.route('/processar_pagamento', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def processar_pagamento():
    try:
        data = request.json
        db.session.add(Order(plano=data.get('plano'), preco=data.get('preco'), status='Pendente'))
        db.session.commit()
        return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

@app.route('/avaliacoes')
def reviews():
    return render_template('reviews.html', reviews=Review.query.order_by(Review.data.desc()).all())

@app.route('/submit_lead', methods=['POST'])
@csrf.exempt
@limiter.limit("5 per minute")
def submit_lead():
    try:
        nome = request.form.get('nome'); email = request.form.get('email')
        telefone = request.form.get('telefone'); projeto = request.form.get('projeto')
        info_extra = ""; arquivo_anexo = None
        
        if 'arquivo' in request.files:
            file = request.files['arquivo']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    safe_name = secure_filename(file.filename)
                    final_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], final_name))
                    info_extra = " [Anexo]"; arquivo_anexo = final_name
                else: return jsonify({'status': 'error', 'msg': 'Arquivo inválido'}), 400

        db.session.add(Lead(nome=nome, email=email, telefone=telefone, projeto=f"{projeto}{info_extra}"))
        db.session.commit()
        
        msg = Message(f"Novo Lead: {nome}", sender=app.config['MAIL_USERNAME'], recipients=[app.config['MAIL_USERNAME']])
        msg.body = f"Nome: {nome}\nEmail: {email}\nTel: {telefone}\nProjeto: {projeto}"
        if arquivo_anexo:
            with app.open_resource(os.path.join(app.config['UPLOAD_FOLDER'], arquivo_anexo)) as fp:
                msg.attach(arquivo_anexo, "application/octet-stream", fp.read())
        
        Thread(target=send_async_email, args=(app, msg)).start()
        return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

@app.route('/submit_review', methods=['POST'])
@csrf.exempt
def submit_review():
    try:
        d = request.json
        db.session.add(Review(nome=d.get('nome'), empresa=d.get('empresa'), email=d.get('email'), avaliacao=d.get('avaliacao'), estrelas=int(d.get('estrelas',5))))
        db.session.commit()
        return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

# --- CHATBOT ---
@app.route('/init_session', methods=['POST'])
@csrf.exempt
def init_session():
    d = request.json
    ns = ChatSession(session_uuid=uuid.uuid4().hex, category=d.get('category'), client_name=d.get('name'), client_phone=d.get('phone'), status='Aberto')
    db.session.add(ns); db.session.commit()
    db.session.add(ChatMessage(session_id=ns.id, tipo='texto', conteudo=f"Olá {d.get('name')}, em que posso ajudar?", remetente='system'))
    db.session.commit()
    return jsonify({'status': 'success', 'session_id': ns.session_uuid, 'ticket': f"#{ns.id:04d}", 'category': ns.category})

@app.route('/my_tickets', methods=['POST'])
@csrf.exempt
def my_tickets():
    uuids = request.json.get('uuids', [])
    return jsonify([{'uuid':t.session_uuid, 'ticket':f"#{t.id:04d}", 'category':t.category, 'status':t.status, 'date':t.created_at.strftime('%d/%m')} for t in ChatSession.query.filter(ChatSession.session_uuid.in_(uuids)).order_by(ChatSession.created_at.desc()).all()])

@app.route('/send_chat', methods=['POST'])
@csrf.exempt
def send_chat():
    suuid = request.form.get('session_id'); rem = request.form.get('remetente')
    sess = ChatSession.query.filter_by(session_uuid=suuid).first()
    if not sess: return jsonify({'status': 'error'}), 404
    if sess.status == 'Encerrado' and rem == 'user': return jsonify({'status': 'closed', 'msg': 'Encerrado.'})

    if 'message' in request.form: db.session.add(ChatMessage(session_id=sess.id, tipo='texto', conteudo=request.form['message'], remetente=rem))
    if 'audio' in request.files:
        f = request.files['audio']; n = f"audio_{uuid.uuid4().hex}.webm"
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], n))
        db.session.add(ChatMessage(session_id=sess.id, tipo='audio', conteudo=n, remetente=rem))
    if 'arquivo' in request.files:
        f = request.files['arquivo']
        if allowed_file(f.filename):
            n = secure_filename(f.filename); f.save(os.path.join(app.config['UPLOAD_FOLDER'], n))
            db.session.add(ChatMessage(session_id=sess.id, tipo='arquivo', conteudo=n, remetente=rem))
    
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/get_messages/<session_uuid>') 
def get_messages(session_uuid):
    sess = ChatSession.query.filter_by(session_uuid=session_uuid).first()
    if not sess: return jsonify([])
    msgs = ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all()
    return jsonify({'messages': [{'remetente': m.remetente, 'tipo': m.tipo, 'conteudo': m.conteudo} for m in msgs], 'status': sess.status})

@app.route('/close_ticket/<session_uuid>', methods=['POST'])
@csrf.exempt
@login_required
def close_ticket(session_uuid):
    sess = ChatSession.query.filter_by(session_uuid=session_uuid).first()
    if sess:
        sess.status = 'Encerrado'; db.session.add(ChatMessage(session_id=sess.id, tipo='texto', conteudo="Atendimento encerrado.", remetente='system')); db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 404

@app.route('/delete_ticket/<session_uuid>', methods=['DELETE'])
@csrf.exempt 
@login_required
def delete_ticket(session_uuid):
    try:
        sess = ChatSession.query.filter_by(session_uuid=session_uuid).first()
        if sess:
            db.session.add(AuditLog(user_id=current_user.id, action="DELETE", details=f"Ticket #{sess.id}", ip_address=request.remote_addr))
            ChatMessage.query.filter_by(session_id=sess.id).delete(); db.session.delete(sess); db.session.commit()
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error'}), 404
    except: return jsonify({'status': 'error'}), 500

# --- ADMIN OTIMIZADO ---
@app.route('/admin')
@login_required
def admin():
    search = request.args.get('q'); date_filter = request.args.get('date'); status_filter = request.args.get('status')
    page = request.args.get('page', 1, type=int) # Paginação
    
    # Consultas Base
    leads_q = Lead.query.order_by(Lead.data.desc())
    orders_q = Order.query.order_by(Order.data.desc())
    sessions_q = ChatSession.query.order_by(ChatSession.created_at.desc())

    # Filtros
    if date_filter:
        limit = datetime.utcnow()
        if date_filter == 'today': limit = limit.replace(hour=0, minute=0, second=0)
        elif date_filter == 'week': limit -= timedelta(weeks=1)
        elif date_filter == 'month': limit -= timedelta(days=30)
        leads_q = leads_q.filter(Lead.data >= limit); orders_q = orders_q.filter(Order.data >= limit); sessions_q = sessions_q.filter(ChatSession.created_at >= limit)

    if search:
        s = f"%{search}%"
        leads_q = leads_q.filter(or_(Lead.nome.like(s), Lead.email.like(s)))
        sessions_q = sessions_q.filter(or_(ChatSession.client_name.like(s), ChatSession.id.like(s)))

    if status_filter and status_filter != 'todos':
        sessions_q = sessions_q.filter(ChatSession.status == status_filter)

    # --- PERFORMANCE: Paginação ---
    # Ao usar .paginate(), não carregamos a lista inteira na memória
    leads_paginated = leads_q.paginate(page=page, per_page=20, error_out=False)
    orders_paginated = orders_q.paginate(page=page, per_page=20, error_out=False)
    sessions_paginated = sessions_q.paginate(page=page, per_page=50, error_out=False)
    reviews = Review.query.order_by(Review.data.desc()).limit(10).all() # Limite fixo pra reviews

    # --- PERFORMANCE: Agregação de Dados para Gráficos ---
    # 1. Gráfico de Leads (Últimos 7 dias)
    seven_days = datetime.utcnow() - timedelta(days=6)
    daily_leads = db.session.query(func.date(Lead.data), func.count(Lead.id)).filter(Lead.data >= seven_days).group_by(func.date(Lead.data)).all()
    
    chart_dates = [(datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
    leads_map = {d: 0 for d in chart_dates}
    for d, c in daily_leads: 
        if d in leads_map: leads_map[d] = c
    
    leads_chart = {
        'labels': [datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m') for d in chart_dates],
        'values': list(leads_map.values())
    }

    # 2. Gráfico de Status (Pizza)
    status_counts = db.session.query(ChatSession.status, func.count(ChatSession.id)).group_by(ChatSession.status).all()
    status_map = {'Aberto': 0, 'Encerrado': 0}
    for s, c in status_counts: 
        if s in status_map: status_map[s] = c
    
    status_chart = {
        'labels': list(status_map.keys()),
        'values': list(status_map.values())
    }

    # Totais Rápidos
    total_visits = Visit.query.count()
    total_leads = Lead.query.count()
    total_sales = Order.query.count()

    # Chat Ativo
    active_uuid = request.args.get('session_id')
    chat_history, active_ticket, active_ticket_status = [], "", ""
    if active_uuid:
        sess = ChatSession.query.filter_by(session_uuid=active_uuid).first()
        if sess:
            chat_history = ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all()
            active_ticket = f"#{sess.id:04d} - {sess.client_name}"
            active_ticket_status = sess.status
    
    for s in sessions_paginated.items: 
        s.full_title = f"#{s.id:04d} - {s.client_name or 'Visitante'}"
        s.uuid = s.session_uuid

    return render_template('admin.html', 
                           leads=leads_paginated, orders=orders_paginated, reviews=reviews, sessions=sessions_paginated,
                           total_visits=total_visits, total_leads=total_leads, total_sales=total_sales,
                           active_session=active_uuid, chat_history=chat_history, 
                           active_ticket=active_ticket, active_ticket_status=active_ticket_status,
                           leads_chart=json.dumps(leads_chart), status_chart=json.dumps(status_chart))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    form = LoginForm()
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form.get('username')).first()
        if u and check_password_hash(u.password_hash, request.form.get('password')):
            login_user(u); return redirect(url_for('admin'))
        flash('Login inválido')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password_hash=generate_password_hash('admin123')))
            db.session.commit()
    app.run(debug=False, port=5000)