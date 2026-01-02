import os
import uuid
import json
import mercadopago
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort
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
from models import db, User, Lead, Order, Review, ChatSession, ChatMessage, Visit, ClientPlan, ClientStat, PublicPlan
from forms import LoginForm

app = Flask(__name__)
app.config.from_object(Config)

# --- CONFIGURAÇÃO PARA PRODUÇÃO (ProxyFix) ---
# Corrige IP e HTTPS quando rodando atrás de proxy (Nginx/Heroku/Render)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- CONFIGURAÇÕES DE SEGURANÇA E PLUGINS ---
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx'}
if not os.path.exists(app.config['UPLOAD_FOLDER']): os.makedirs(app.config['UPLOAD_FOLDER'])

# Inicializa SDK do Mercado Pago
try:
    sdk = mercadopago.SDK(app.config['MERCADO_PAGO_ACCESS_TOKEN'])
except:
    print("Aviso: Token do Mercado Pago não configurado ou inválido.")

db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)
csrf = CSRFProtect(app)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'client_login'
login_manager.login_message = "Por favor, faça login para acessar."
login_manager.login_message_category = "warning"

# Rate Limiter (Proteção contra Brute Force)
limiter = Limiter(get_remote_address, app=app, default_limits=["2000 per day", "500 per hour"], storage_uri="memory://")

# Talisman (Cabeçalhos de Segurança HTTP)
csp = {
    'default-src': '\'self\'',
    'script-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com', 'https://unpkg.com', 'https://www.mercadopago.com.br', 'https://http2.mlstatic.com'],
    'style-src': ['\'self\'', '\'unsafe-inline\'', 'https://cdnjs.cloudflare.com', 'https://fonts.googleapis.com'],
    'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
    'img-src': ['\'self\'', 'data:', 'https://images.unsplash.com', 'https://api.qrserver.com', 'https://http2.mlstatic.com'],
    'connect-src': ['\'self\'', 'https://api.mercadopago.com', 'https://events.mercadopago.com'],
    'frame-src': ['\'self\'', 'https://www.mercadopago.com.br']
}

# Força HTTPS apenas se estiver em produção
is_production = os.environ.get('FLASK_ENV') == 'production'
Talisman(app, content_security_policy=csp, force_https=is_production)

# --- ROTA TEMPORÁRIA PARA CRIAR ADMIN (APAGUE DEPOIS) ---
@app.route('/setup-admin-secreto')
def setup_admin():
    from werkzeug.security import generate_password_hash
    try:
        # Verifica se já existe
        if User.query.filter_by(username='admin').first():
            return "O usuário Admin já existe!", 200
        
        # Cria o Admin
        admin = User(
            username='admin', 
            name="Super Admin", 
            role='admin', 
            password_hash=generate_password_hash('sua_senha_forte_aqui') # <--- Troque a senha aqui se quiser
        )
        db.session.add(admin)
        db.session.commit()
        return "Sucesso! Usuário Admin criado. Agora apague esta rota do código.", 200
    except Exception as e:
        return f"Erro ao criar admin: {str(e)}", 500

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def admin_required(f):
    def wrap(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('admin_login'))
        
        if current_user.role != 'admin':
            logout_user()
            flash('Acesso restrito a administradores.', 'error')
            return redirect(url_for('admin_login'))
            
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- ROTAS DE PAGAMENTO ---

@app.route('/criar_pagamento', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def criar_pagamento():
    try:
        dados = request.json
        plano_nome = dados.get('plano')
        metodo = dados.get('metodo') # 'pix' ou 'card'
        
        db_plan = PublicPlan.query.filter_by(name=plano_nome).first()
        if not db_plan:
            return jsonify({'status': 'error', 'message': 'Plano inválido ou não encontrado.'}), 400
            
        try:
            preco_real = float(db_plan.price.replace('R$', '').replace('.', '').replace(',', '.').strip())
        except:
            return jsonify({'status': 'error', 'message': 'Erro na configuração de preço do plano.'}), 500

        order_id = str(uuid.uuid4())

        nova_order = Order(
            id=order_id,
            plano=plano_nome,
            preco=db_plan.price,
            status='Pendente',
            metodo=metodo
        )
        db.session.add(nova_order)
        db.session.commit()

        if metodo == 'pix':
            payment_data = {
                "transaction_amount": preco_real,
                "description": f"Plano {plano_nome} - Studio Indexa",
                "payment_method_id": "pix",
                "payer": {
                    "email": dados.get('email', 'cliente@email.com'),
                    "first_name": dados.get('nome', 'Cliente'),
                },
                "external_reference": order_id,
                "notification_url": url_for('webhook_mp', _external=True)
            }
            result = sdk.payment().create(payment_data)
            
            if result["status"] == 201:
                payment = result["response"]
                return jsonify({
                    'status': 'pix_created',
                    'qr_code': payment['point_of_interaction']['transaction_data']['qr_code'],
                    'qr_code_base64': payment['point_of_interaction']['transaction_data']['qr_code_base64'],
                    'order_id': order_id
                })
            else:
                return jsonify({'status': 'error', 'message': 'Erro ao gerar PIX no Mercado Pago'}), 500

        else:
            preference_data = {
                "items": [{
                    "title": f"Plano {plano_nome}",
                    "quantity": 1,
                    "unit_price": preco_real,
                    "currency_id": "BRL"
                }],
                "external_reference": order_id,
                "notification_url": url_for('webhook_mp', _external=True),
                "back_urls": {
                    "success": url_for('index', _external=True),
                    "failure": url_for('checkout', plano=plano_nome, _external=True),
                    "pending": url_for('checkout', plano=plano_nome, _external=True)
                },
                "auto_return": "approved"
            }
            result = sdk.preference().create(preference_data)
            return jsonify({
                'status': 'preference_created',
                'init_point': result['response']['init_point']
            })

    except Exception as e:
        print(f"Erro Crítico MP: {e}")
        return jsonify({'status': 'error', 'message': 'Erro interno ao processar pagamento.'}), 500

@app.route('/webhook/mercadopago', methods=['POST'])
@csrf.exempt
def webhook_mp():
    topic = request.args.get('topic') or request.args.get('type')
    p_id = request.args.get('id') or request.args.get('data.id')

    if (topic == 'payment' or request.json.get('type') == 'payment') and p_id:
        try:
            payment_info = sdk.payment().get(p_id)
            if payment_info["status"] == 200:
                resp = payment_info["response"]
                status = resp["status"]
                external_ref = resp["external_reference"]
                
                order = db.session.get(Order, external_ref)
                if order:
                    if status == 'approved':
                        order.status = 'Aprovado'
                    elif status in ['rejected', 'cancelled']:
                        order.status = 'Rejeitado'
                    
                    db.session.commit()
        except Exception as e:
            print(f"Erro Webhook: {e}")
                
    return jsonify({'status': 'ok'}), 200

@app.route('/check_status/<order_id>')
def check_status(order_id):
    order = db.session.get(Order, order_id)
    if order:
        return jsonify({'status': order.status})
    return jsonify({'status': 'not_found'}), 404

# --- LOGIN ---
@app.route('/cliente/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute") 
def client_login():
    if current_user.is_authenticated:
        if current_user.role == 'admin': return redirect(url_for('admin'))
        return redirect(url_for('client_dashboard'))
        
    form = LoginForm()
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form.get('username')).first()
        if u and check_password_hash(u.password_hash, request.form.get('password')):
            if u.role == 'client': 
                login_user(u)
                return redirect(url_for('client_dashboard'))
            else: 
                flash('Esta conta é de Administrador. Use o painel correto.')
                return redirect(url_for('admin_login'))
        else: 
            flash('Usuário ou senha incorretos.')
    return render_template('login.html', form=form, login_type="Cliente")

@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def admin_login():
    if current_user.is_authenticated:
        if current_user.role == 'admin': return redirect(url_for('admin'))
        logout_user() 
        
    form = LoginForm()
    if request.method == 'POST':
        u = User.query.filter_by(username=request.form.get('username')).first()
        if u and check_password_hash(u.password_hash, request.form.get('password')):
            if u.role == 'admin': 
                login_user(u)
                return redirect(url_for('admin'))
            else: 
                flash('Acesso negado. Você não é administrador.')
        else: 
            flash('Credenciais inválidas.')
    return render_template('login.html', form=form, login_type="Admin")

@app.route('/logout')
@login_required
def logout():
    role = current_user.role
    logout_user()
    flash('Você saiu do sistema.', 'info')
    if role == 'admin':
        return redirect(url_for('admin_login'))
    return redirect(url_for('client_login'))

# --- ROTAS GERAIS ---
@app.route('/')
def index():
    try: db.session.add(Visit(page='home')); db.session.commit()
    except: pass
    
    plans = PublicPlan.query.order_by(PublicPlan.order_index).all()
    # Carrega Portfólio e Sobre Nós
    portfolio = PortfolioItem.query.all()
    about_text = SiteConfig.query.filter_by(key='about_text').first()
    
    # Se não tiver texto no banco, usa um padrão
    about_content = about_text.value if about_text else "Texto padrão sobre a agência..."

    # Fallback para planos (seu código antigo)
    if not plans: plans = []
    else:
        for p in plans:
            if isinstance(p.benefits, str):
                try: p.benefits_list = json.loads(p.benefits)
                except: p.benefits_list = []
    
    return render_template('index.html', plans=plans, portfolio=portfolio, about_content=about_content)

@app.route('/termos-e-privacidade')
def termos(): return render_template('legal.html') 

@app.route('/avaliacoes')
def reviews(): return render_template('reviews.html', reviews=Review.query.filter_by(visivel=True).order_by(Review.data.desc()).all())

@app.route('/checkout/<plano>')
def checkout(plano):
    db_plan = PublicPlan.query.filter_by(name=plano).first()
    preco = db_plan.price if db_plan else '0,00'
    return render_template('checkout.html', plano=plano, preco=preco)

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Erro ao enviar email em background: {e}")

# ROTA DE LEADS ATUALIZADA (EMAIL E ARQUIVO)
@app.route('/submit_lead', methods=['POST'])
@csrf.exempt
def submit_lead():
    try:
        nome = request.form.get('nome')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        projeto = request.form.get('projeto')
        
        # 1. Validação e Upload de Arquivo
        arquivo_nome = None
        file = request.files.get('arquivo')
        
        if file and file.filename != '':
            if not allowed_file(file.filename):
                return jsonify({'status': 'error', 'message': 'Tipo de arquivo não permitido.'}), 400
            
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            arquivo_nome = unique_filename

        # 2. Salvar no Banco de Dados
        novo_lead = Lead(
            nome=nome, 
            email=email, 
            telefone=telefone, 
            projeto=projeto, 
            data=datetime.now()
        )
        db.session.add(novo_lead)
        db.session.commit()

        # 3. Preparar E-mail
        msg = Message(f"Novo Lead: {nome}",
                      sender=app.config.get('MAIL_USERNAME'),
                      recipients=[app.config.get('MAIL_USERNAME')])
        
        msg.html = render_template('email_lead.html', 
                                   nome=nome, 
                                   email=email, 
                                   telefone=telefone, 
                                   projeto=projeto,
                                   tem_arquivo=(arquivo_nome is not None))
        
        if arquivo_nome:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], arquivo_nome)
            with app.open_resource(file_path) as fp:
                msg.attach(arquivo_nome, "application/octet-stream", fp.read())

        Thread(target=send_async_email, args=(app._get_current_object(), msg)).start()

        return jsonify({'status': 'success'})

    except Exception as e:
        print(f"Erro ao processar lead: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/submit_review', methods=['POST'])
@csrf.exempt
def submit_review():
    try: d = request.json; db.session.add(Review(nome=d.get('nome'), empresa=d.get('empresa'), email=d.get('email'), avaliacao=d.get('avaliacao'), estrelas=int(d.get('estrelas',5)), visivel=True, data=datetime.now())); db.session.commit(); return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

# --- DASHBOARD CLIENTE ---
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

# --- ADMIN ---
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
    
    public_plans = PublicPlan.query.order_by(PublicPlan.order_index).all()
    
    chat_history = []
    active_ticket = ""
    if active_uuid:
        sess = ChatSession.query.filter_by(session_uuid=active_uuid).first()
        if sess: 
            chat_history = ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all()
            active_ticket = sess.client_name
            if sess.user_id:
                if tab != 'chat_client': tab = 'chat_client'
            else:
                if tab != 'chat_public': tab = 'chat_public'

    public_chats = ChatSession.query.filter(ChatSession.user_id == None).order_by(ChatSession.created_at.desc()).all()
    client_chats = ChatSession.query.filter(ChatSession.user_id != None).order_by(ChatSession.created_at.desc()).all()
    
    for s in public_chats: s.uuid = s.session_uuid
    for s in client_chats: s.uuid = s.session_uuid

    return render_template('admin.html', 
        leads=Lead.query.order_by(Lead.data.desc()).all(),
        reviews=Review.query.order_by(Review.data.desc()).all(),
        clients=User.query.filter_by(role='client').all(),
        orders=Order.query.order_by(Order.data.desc()).all(),
        public_plans=public_plans,
        total_visits=Visit.query.count(), total_leads=Lead.query.count(), total_sales=Order.query.count(),
        leads_chart=json.dumps({'labels': [datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m') for d in chart_map.keys()], 'values': list(chart_map.values())}),
        active_tab=tab, active_session=active_uuid, chat_history=chat_history, active_ticket=active_ticket,
        public_chats=public_chats, client_chats=client_chats
    )

@app.route('/admin/update_plan/<int:plan_id>', methods=['POST'])
@login_required
@admin_required
def update_plan(plan_id):
    p = db.session.get(PublicPlan, plan_id)
    if p:
        p.name = request.form.get('name')
        p.price = request.form.get('price')
        benefits_list = [b.strip() for b in request.form.get('benefits').split(',')]
        p.benefits = json.dumps(benefits_list)
        db.session.commit()
        flash('Plano atualizado!')
    return redirect(url_for('admin', tab='plans'))

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
    flash('Cliente criado com sucesso!', 'success')
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
    User.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect(url_for('admin', tab='clients'))

@app.route('/admin/toggle_review/<int:id>')
@login_required
@admin_required
def toggle_review(id): r=db.session.get(Review,id); r.visivel=not r.visivel; db.session.commit(); return redirect(url_for('admin', tab='reviews'))

@app.route('/admin/delete_review/<int:id>')
@login_required
@admin_required
def delete_review(id): Review.query.filter_by(id=id).delete(); db.session.commit(); return redirect(url_for('admin', tab='reviews'))

# Chat Publico Backend
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
        # Seed Admin
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', name="Super Admin", role='admin', password_hash=generate_password_hash('admin123')))
            db.session.commit()
        # Seed Planos
        if not PublicPlan.query.first():
            db.session.add(PublicPlan(name='Start', price='1.500', benefits=json.dumps(['Redes Sociais', 'Tráfego Básico', 'Relatório PDF']), is_highlighted=False, order_index=1))
            db.session.add(PublicPlan(name='Growth', price='3.200', benefits=json.dumps(['Tráfego Avançado', 'Landing Page', 'Dashboard 24h']), is_highlighted=True, order_index=2))
            db.session.add(PublicPlan(name='Scale', price='7.000', benefits=json.dumps(['Gestão 360º', 'Consultoria Semanal', 'Time Dedicado']), is_highlighted=False, order_index=3))
            db.session.commit()
    app.run(debug=True, port=5000)