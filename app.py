import os
import uuid
import json
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask,current_app, render_template, request, jsonify, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from flask_mail import Mail, Message
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import or_, func
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

from config import Config
from models import db, User, Lead, Order, Review, ChatSession, ChatMessage, Visit, ClientPlan, ClientStat, PublicPlan, PortfolioItem, SiteConfig
from forms import LoginForm

app = Flask(__name__)
app.config.from_object(Config)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

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
login_manager.login_message = "Por favor, faça login para acessar."
login_manager.login_message_category = "warning"

limiter = Limiter(get_remote_address, app=app, default_limits=["2000 per day", "500 per hour"], storage_uri="memory://")

csp = {
    'default-src': '\'self\'',
    'script-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com', 'https://unpkg.com'],
    'style-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdnjs.cloudflare.com', 'https://fonts.googleapis.com'],
    'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
    'img-src': ['\'self\'', 'data:', 'https://images.unsplash.com', 'https://api.qrserver.com'],
    'connect-src': ['\'self\''],
}
is_production = os.environ.get('FLASK_ENV') == 'production'
Talisman(app, content_security_policy=csp, force_https=is_production)

@app.route('/configurar-site')
def configurar_site():
    try:
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', name="Super Admin", role='admin', password_hash=generate_password_hash('123456'))
            db.session.add(admin)
        else:
            admin.password_hash = generate_password_hash('123456')
        
        # Cria planos padrão se não existirem
        if not PublicPlan.query.first():
             db.session.add(PublicPlan(name='Starter', price='2.000', old_price='4.700', benefits=json.dumps(['Social Media Essencial', 'Gestão de Tráfego', 'Landing Page']), is_highlighted=False, order_index=1))
             db.session.add(PublicPlan(name='Growth', price='3.200', old_price='9.200', benefits=json.dumps(['Social Media Crescimento', 'Tráfego Pago', 'Identidade Visual simplificada']), is_highlighted=True, order_index=2))
             db.session.add(PublicPlan(name='Performance', price='4.500', old_price='16.500', benefits=json.dumps(['Estratégia completa', 'Foco total em vendas', 'Conversão acelerada']), is_highlighted=False, order_index=3))
        
        db.session.commit()
        return "Configuração concluída. Admin senha: 123456"
    except Exception as e:
        return f"Erro: {str(e)}"

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def admin_required(f):
    def wrap(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- LOGIN ---
@app.route('/cliente/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute") 
def client_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin') if current_user.role == 'admin' else url_for('client_dashboard'))
    form = LoginForm()
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form.get('username')).first()
        if u and check_password_hash(u.password_hash, request.form.get('password')):
            if u.role == 'client': login_user(u); return redirect(url_for('client_dashboard'))
            else: flash('Use o painel de admin.'); return redirect(url_for('admin_login'))
        else: flash('Credenciais inválidas.')
    return render_template('login.html', form=form, login_type="Cliente")

@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def admin_login():
    if current_user.is_authenticated and current_user.role == 'admin': return redirect(url_for('admin'))
    form = LoginForm()
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form.get('username')).first()
        if u and check_password_hash(u.password_hash, request.form.get('password')):
            if u.role == 'admin': login_user(u); return redirect(url_for('admin'))
            else: flash('Acesso negado.')
        else: flash('Credenciais inválidas.')
    return render_template('login.html', form=form, login_type="Admin")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('client_login'))

# --- SITE ---
@app.route('/')
def index():
    try: db.session.add(Visit(page='home')); db.session.commit()
    except: pass
    
    plans = PublicPlan.query.order_by(PublicPlan.order_index).all()
    if plans:
        for p in plans:
            try: p.benefits_list = json.loads(p.benefits)
            except: p.benefits_list = []
            
    portfolio = PortfolioItem.query.all()
    about_text = SiteConfig.query.filter_by(key='about_text').first()
    about_content = about_text.value if about_text else "Texto padrão..."
    
    return render_template('index.html', plans=plans, portfolio=portfolio, about_content=about_content)

@app.route('/termos-e-privacidade')
def termos(): return render_template('legal.html') 

@app.route('/avaliacoes')
def reviews(): return render_template('reviews.html', reviews=Review.query.filter_by(visivel=True).order_by(Review.data.desc()).all())

# --- ADMIN ROUTES ---
@app.route('/admin')
@login_required
@admin_required
def admin():
    tab = request.args.get('tab', 'dashboard')
    active_uuid = request.args.get('session_id')
    
    last_7 = datetime.now() - timedelta(days=7)
    leads_data = db.session.query(func.date(Lead.data), func.count(Lead.id)).filter(Lead.data >= last_7).group_by(func.date(Lead.data)).all()
    chart_map = {(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d'): 0 for i in range(6, -1, -1)}
    for d, c in leads_data: chart_map[str(d)] = c
    
    chat_history = []
    active_ticket = ""
    if active_uuid:
        sess = ChatSession.query.filter_by(session_uuid=active_uuid).first()
        if sess: 
            chat_history = ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all()
            active_ticket = sess.client_name

    public_chats = ChatSession.query.filter(ChatSession.user_id == None).order_by(ChatSession.created_at.desc()).all()
    client_chats = ChatSession.query.filter(ChatSession.user_id != None).order_by(ChatSession.created_at.desc()).all()
    
    for s in public_chats: s.uuid = s.session_uuid
    for s in client_chats: s.uuid = s.session_uuid

    return render_template('admin.html', 
        leads=Lead.query.order_by(Lead.data.desc()).all(),
        reviews=Review.query.order_by(Review.data.desc()).all(),
        clients=User.query.filter_by(role='client').all(),
        orders=Order.query.order_by(Order.data.desc()).all(),
        public_plans=PublicPlan.query.order_by(PublicPlan.order_index).all(),
        portfolio=PortfolioItem.query.all(),
        total_visits=Visit.query.count(), total_leads=Lead.query.count(), total_sales=Order.query.count(),
        leads_chart=json.dumps({'labels': [datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m') for d in chart_map.keys()], 'values': list(chart_map.values())}),
        active_tab=tab, active_session=active_uuid, chat_history=chat_history, active_ticket=active_ticket,
        public_chats=public_chats, client_chats=client_chats
    )

# --- PLANOS ---
@app.route('/admin/update_plan/<int:plan_id>', methods=['POST'])
@login_required
@admin_required
def update_plan(plan_id):
    p = db.session.get(PublicPlan, plan_id)
    if p:
        p.name = request.form.get('name')
        p.price = request.form.get('price')
        p.old_price = request.form.get('old_price')
        benefits_list = [b.strip() for b in request.form.get('benefits').split(',')]
        p.benefits = json.dumps(benefits_list)
        db.session.commit()
        flash('Plano atualizado com sucesso!')
    return redirect(url_for('admin', tab='plans'))

# --- CASES (PORTFÓLIO) ---
@app.route('/admin/create_case', methods=['POST'])
@login_required
@admin_required
def create_case():
    title = request.form.get('title')
    desc = request.form.get('description')
    image_url = request.form.get('image_url') # Pode ser URL externa ou upload
    
    # Se tiver upload de arquivo, prioriza
    file = request.files.get('image_file')
    if file and file.filename != '' and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"case_{uuid.uuid4().hex}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        image_url = url_for('static', filename=f'uploads/{unique_filename}')

    db.session.add(PortfolioItem(title=title, description=desc, image_url=image_url))
    db.session.commit()
    flash('Novo case adicionado!')
    return redirect(url_for('admin', tab='cases'))

@app.route('/admin/delete_case/<int:id>')
@login_required
@admin_required
def delete_case(id):
    PortfolioItem.query.filter_by(id=id).delete()
    db.session.commit()
    flash('Case removido.')
    return redirect(url_for('admin', tab='cases'))

# --- LEADS E CLIENTES ---
@app.route('/submit_lead', methods=['POST'])
@csrf.exempt
def submit_lead():
    try:
        nome = request.form.get('nome')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        projeto = request.form.get('projeto')
        
        arquivo_nome = None
        file = request.files.get('arquivo')
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            arquivo_nome = unique_filename

        db.session.add(Lead(nome=nome, email=email, telefone=telefone, projeto=projeto, data=datetime.now()))
        db.session.commit()
        
        # Envio de email (Thread)
        def send_mail_async(app, msg):
            with app.app_context(): mail.send(msg)
            
        msg = Message(f"Novo Lead: {nome}", sender=app.config.get('MAIL_USERNAME'), recipients=[app.config.get('MAIL_USERNAME')])
        msg.html = render_template('email_lead.html', nome=nome, email=email, telefone=telefone, projeto=projeto, tem_arquivo=(arquivo_nome is not None))
        if arquivo_nome:
            with app.open_resource(os.path.join(app.config['UPLOAD_FOLDER'], arquivo_nome)) as fp:
                msg.attach(arquivo_nome, "application/octet-stream", fp.read())
        
        Thread(target=send_mail_async, args=(app._get_current_object(), msg)).start()

        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/create_client', methods=['POST'])
@login_required
@admin_required
def create_client():
    if User.query.filter_by(username=request.form.get('username')).first(): 
        flash('Erro: Usuário já existe')
        return redirect(url_for('admin', tab='clients'))
    u = User(username=request.form.get('username'), password_hash=generate_password_hash(request.form.get('password')), name=request.form.get('name'), role='client')
    db.session.add(u); db.session.commit()
    db.session.add(ClientPlan(user_id=u.id, plan_name=request.form.get('plan_name'), benefits=json.dumps(["Suporte"])))
    db.session.add(ClientStat(user_id=u.id, label='Mês 1', value=0, type='growth'))
    db.session.commit()
    flash('Cliente criado!')
    return redirect(url_for('admin', tab='clients'))

@app.route('/admin/update_client_stats/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def update_client_stats(user_id):
    ClientStat.query.filter_by(user_id=user_id).delete()
    for l, v in zip(request.form.getlist('labels[]'), request.form.getlist('values[]')):
        if l and v: db.session.add(ClientStat(user_id=user_id, label=l, value=float(v), type='growth'))
    p = ClientPlan.query.filter_by(user_id=user_id).first()
    if p: p.plan_name = request.form.get('plan_name'); p.benefits = json.dumps([b.strip() for b in request.form.get('benefits').split(',')])
    db.session.commit(); flash('Cliente atualizado!'); return redirect(url_for('admin', tab='clients'))

@app.route('/admin/delete_client/<int:id>')
@login_required
@admin_required
def delete_client(id): 
    User.query.filter_by(id=id).delete(); db.session.commit(); return redirect(url_for('admin', tab='clients'))

# --- AVALIAÇÕES ---
@app.route('/submit_review', methods=['POST'])
@csrf.exempt
def submit_review():
    try: d = request.json; db.session.add(Review(nome=d.get('nome'), empresa=d.get('empresa'), email=d.get('email'), avaliacao=d.get('avaliacao'), estrelas=int(d.get('estrelas',5)), visivel=True, data=datetime.now())); db.session.commit(); return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

@app.route('/admin/toggle_review/<int:id>')
@login_required
@admin_required
def toggle_review(id): r=db.session.get(Review,id); r.visivel=not r.visivel; db.session.commit(); return redirect(url_for('admin', tab='reviews'))

@app.route('/admin/delete_review/<int:id>')
@login_required
@admin_required
def delete_review(id): Review.query.filter_by(id=id).delete(); db.session.commit(); return redirect(url_for('admin', tab='reviews'))

# --- CHAT ---
@app.route('/cliente')
@login_required
def client_dashboard():
    if current_user.role != 'client': return redirect(url_for('admin_login'))
    plan = ClientPlan.query.filter_by(user_id=current_user.id).first()
    stats = ClientStat.query.filter_by(user_id=current_user.id).all()
    chart_data = {'labels': [s.label for s in stats], 'values': [s.value for s in stats]}
    benefits = json.loads(plan.benefits) if plan and plan.benefits else []
    chat_session = ChatSession.query.filter_by(user_id=current_user.id, status='Aberto').first()
    messages = ChatMessage.query.filter_by(session_id=chat_session.id).order_by(ChatMessage.data).all() if chat_session else []
    return render_template('client_dashboard.html', user=current_user, plan=plan, benefits=benefits, chart_data=json.dumps(chart_data), chat_session=chat_session, messages=messages)

@app.route('/client/send_message', methods=['POST'])
@login_required
def client_send_message():
    sess = ChatSession.query.filter_by(user_id=current_user.id, status='Aberto').first()
    if not sess:
        sess = ChatSession(session_uuid=uuid.uuid4().hex, user_id=current_user.id, client_name=current_user.name, category='Cliente Dashboard', status='Aberto')
        db.session.add(sess); db.session.commit(); db.session.add(ChatMessage(session_id=sess.id, tipo='texto', remetente='system', conteudo='Olá! Em que posso ajudar?'))
    db.session.add(ChatMessage(session_id=sess.id, tipo='texto', remetente='user', conteudo=request.form.get('message'), data=datetime.now())); db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/client/get_chat', methods=['GET'])
@login_required
def client_get_chat():
    sess = ChatSession.query.filter_by(user_id=current_user.id, status='Aberto').first()
    msgs = ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all() if sess else []
    return jsonify({'messages': [{'remetente': m.remetente, 'conteudo': m.conteudo} for m in msgs]})

@app.route('/init_session', methods=['POST'])
@csrf.exempt
def init_session():
    d=request.json; ns=ChatSession(session_uuid=uuid.uuid4().hex, category=d.get('category'), client_name=d.get('name'), client_phone=d.get('phone'), status='Aberto')
    db.session.add(ns); db.session.commit(); db.session.add(ChatMessage(session_id=ns.id, tipo='texto', conteudo=f"Olá {d.get('name')}.", remetente='system', data=datetime.now())); db.session.commit()
    return jsonify({'status':'success', 'session_id':ns.session_uuid, 'ticket':f"#{ns.id:04d}"})

@app.route('/send_chat', methods=['POST'])
@csrf.exempt
def send_chat():
    sess=ChatSession.query.filter_by(session_uuid=request.form.get('session_id')).first()
    if sess:
        if 'message' in request.form: db.session.add(ChatMessage(session_id=sess.id, tipo='texto', conteudo=request.form['message'], remetente=request.form.get('remetente'), data=datetime.now()))
        if 'audio' in request.files: f=request.files['audio']; n=f"audio_{uuid.uuid4().hex}.webm"; f.save(os.path.join(app.config['UPLOAD_FOLDER'], n)); db.session.add(ChatMessage(session_id=sess.id, tipo='audio', conteudo=n, remetente=request.form.get('remetente'), data=datetime.now()))
        db.session.commit()
    return jsonify({'status':'success'})

@app.route('/get_messages/<session_uuid>') 
def get_messages(session_uuid):
    sess=ChatSession.query.filter_by(session_uuid=session_uuid).first()
    msgs=ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all() if sess else []
    return jsonify({'messages':[{'remetente':m.remetente,'conteudo':m.conteudo,'tipo':m.tipo} for m in msgs], 'status':sess.status if sess else 'Closed'})

@app.route('/close_ticket/<session_uuid>', methods=['POST'])
@csrf.exempt
@login_required
def close_ticket(session_uuid): sess=ChatSession.query.filter_by(session_uuid=session_uuid).first(); sess.status='Encerrado'; db.session.commit(); return jsonify({'status':'success'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)