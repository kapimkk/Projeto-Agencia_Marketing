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
from sqlalchemy import or_

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
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt', 'csv'}

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
# Define exatamente o que pode ser carregado. Bloqueia XSS.
csp = {
    'default-src': '\'self\'',
    'script-src': [
        '\'self\'',
        '\'unsafe-inline\'', # Necessário para scripts no HTML
        'https://cdn.jsdelivr.net',
        'https://cdnjs.cloudflare.com',
        'https://unpkg.com'
    ],
    'style-src': [
        '\'self\'',
        '\'unsafe-inline\'',
        'https://cdnjs.cloudflare.com',
        'https://fonts.googleapis.com'
    ],
    'font-src': [
        '\'self\'',
        'https://fonts.gstatic.com',
        'https://cdnjs.cloudflare.com'
    ],
    'img-src': [
        '\'self\'', 
        'data:', 
        'https://images.unsplash.com', 
        'https://api.qrserver.com',
        'https://cdn-icons-png.flaticon.com'
    ],
    'connect-src': ['\'self\'']
}

# force_https=False para funcionar no localhost. Mude para True em produção.
Talisman(app, content_security_policy=csp, force_https=False)

# --- 3. SEGURANÇA: HONEYPOTS (ARMADILHAS) ---
BANNED_IPS = set()

@app.before_request
def block_banned_ips():
    if request.remote_addr in BANNED_IPS:
        return jsonify({'error': 'Access Denied: Suspicious Activity Detected.'}), 403

@app.route('/wp-admin')
@app.route('/admin/login.php')
@app.route('/backup.sql')
@app.route('/.env')
def honeypot():
    ip = request.remote_addr
    print(f"🚨 HACKER DETECTADO: IP {ip} tentou acessar {request.path}")
    BANNED_IPS.add(ip) # Banimento em memória (reseta ao reiniciar servidor)
    return jsonify({'status': 'banned', 'reason': 'Honeypot triggered'}), 403

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.template_filter('format_currency')
def format_currency(value):
    try: return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return f"R$ {value}"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            print(f"✅ Email enviado para: {msg.recipients}")
        except Exception as e:
            print(f"❌ ERRO EMAIL: {str(e)}")

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# --- ROTAS PRINCIPAIS ---

@app.route('/')
def index():
    try:
        v = Visit(page='home'); db.session.add(v); db.session.commit()
    except: pass
    return render_template('index.html')

@app.route('/checkout/<plano>')
def checkout(plano):
    precos = {'Start': '1.500,00', 'Growth': '3.200,00', 'Scale': '7.000,00'}
    preco = precos.get(plano, 'Consultar')
    return render_template('checkout.html', plano=plano, preco=preco)

@app.route('/processar_pagamento', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def processar_pagamento():
    try:
        data = request.json
        novo_pedido = Order(plano=data.get('plano'), preco=data.get('preco'), status='Pendente')
        db.session.add(novo_pedido)
        db.session.commit()
        return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

@app.route('/avaliacoes')
def reviews():
    all_reviews = Review.query.order_by(Review.data.desc()).all()
    return render_template('reviews.html', reviews=all_reviews)

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
                    path = os.path.join(app.config['UPLOAD_FOLDER'], final_name)
                    file.save(path)
                    info_extra = " [Anexo]"; arquivo_anexo = final_name
                else:
                    return jsonify({'status': 'error', 'msg': 'Arquivo não permitido.'}), 400

        lead = Lead(nome=nome, email=email, telefone=telefone, projeto=f"{projeto}{info_extra}")
        db.session.add(lead)
        db.session.commit()
        
        whatsapp_link = f"https://wa.me/55{telefone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')}" if telefone else "#"
        msg = Message(f"🔥 Novo Lead: {nome}", sender=app.config['MAIL_USERNAME'], recipients=[app.config['MAIL_USERNAME']])
        msg.body = f"Nome: {nome}\nEmail: {email}\nTelefone: {telefone}"
        msg.html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;"><div style="max-width:600px;margin:0 auto;background:#fff;padding:40px;border-radius:8px;"> <h2 style="color:#000;">Novo Lead!</h2> <p><b>Nome:</b> {nome}</p> <p><b>Email:</b> {email}</p> <p><b>Tel:</b> {telefone}</p> <div style="background:#f9f9f9;padding:15px;border-left:4px solid #000;margin:20px 0;">{projeto}</div> <center><a href="mailto:{email}" style="background:#000;color:#fff;padding:10px 20px;text-decoration:none;border-radius:50px;">Responder</a> &nbsp; <a href="{whatsapp_link}" style="background:#25D366;color:#fff;padding:10px 20px;text-decoration:none;border-radius:50px;">WhatsApp</a></center></div></body></html>"""

        if arquivo_anexo:
            path = os.path.join(app.config['UPLOAD_FOLDER'], arquivo_anexo)
            if os.path.exists(path):
                with app.open_resource(path) as fp: msg.attach(arquivo_anexo, "application/octet-stream", fp.read())

        Thread(target=send_async_email, args=(app, msg)).start()
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Erro lead: {e}"); return jsonify({'status': 'error'}), 500

@app.route('/submit_review', methods=['POST'])
@csrf.exempt
def submit_review():
    try:
        data = request.json
        review = Review(
            nome=data.get('nome'), empresa=data.get('empresa'),
            email=data.get('email'), avaliacao=data.get('avaliacao'),
            estrelas=int(data.get('estrelas', 5))
        )
        db.session.add(review); db.session.commit()
        return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

@app.route('/init_session', methods=['POST'])
@csrf.exempt
def init_session():
    data = request.json
    new_session = ChatSession(
        session_uuid=uuid.uuid4().hex, category=data.get('category'),
        client_name=data.get('name'), client_phone=data.get('phone'), status='Aberto'
    )
    db.session.add(new_session); db.session.commit()
    db.session.add(ChatMessage(session_id=new_session.id, tipo='texto', conteudo=f"Olá {data.get('name')}, em que posso ajudar?", remetente='system'))
    db.session.commit()
    return jsonify({'status': 'success', 'session_id': new_session.session_uuid, 'ticket': f"#{new_session.id:04d}", 'category': data.get('category')})

@app.route('/my_tickets', methods=['POST'])
@csrf.exempt
def my_tickets():
    uuids = request.json.get('uuids', [])
    tickets = ChatSession.query.filter(ChatSession.session_uuid.in_(uuids)).order_by(ChatSession.created_at.desc()).all()
    result = [{'uuid':t.session_uuid, 'ticket':f"#{t.id:04d}", 'category':t.category, 'status':t.status, 'date':t.created_at.strftime('%d/%m')} for t in tickets]
    return jsonify(result)

@app.route('/send_chat', methods=['POST'])
@csrf.exempt
def send_chat():
    session_uuid = request.form.get('session_id')
    remetente = request.form.get('remetente')
    chat_session = ChatSession.query.filter_by(session_uuid=session_uuid).first()
    if not chat_session: return jsonify({'status': 'error'}), 404
    if chat_session.status == 'Encerrado' and remetente == 'user': return jsonify({'status': 'closed', 'msg': 'Encerrado.'})

    if 'message' in request.form:
        db.session.add(ChatMessage(session_id=chat_session.id, tipo='texto', conteudo=request.form['message'], remetente=remetente))
    if 'audio' in request.files:
        file = request.files['audio']; fname = f"audio_{uuid.uuid4().hex}.webm"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        db.session.add(ChatMessage(session_id=chat_session.id, tipo='audio', conteudo=fname, remetente=remetente))
    if 'arquivo' in request.files:
        file = request.files['arquivo']
        if file and allowed_file(file.filename):
            fname = secure_filename(file.filename); file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            db.session.add(ChatMessage(session_id=chat_session.id, tipo='arquivo', conteudo=fname, remetente=remetente))
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
        sess.status = 'Encerrado'
        db.session.add(ChatMessage(session_id=sess.id, tipo='texto', conteudo="Atendimento encerrado.", remetente='system'))
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 404

# --- 4. AUDITORIA: DELETE COM LOG ---
@app.route('/delete_ticket/<session_uuid>', methods=['DELETE'])
@csrf.exempt 
@login_required
def delete_ticket(session_uuid):
    try:
        sess = ChatSession.query.filter_by(session_uuid=session_uuid).first()
        if sess:
            # Registrar na Auditoria
            log = AuditLog(
                user_id=current_user.id, 
                action="DELETE_TICKET", 
                details=f"Ticket #{sess.id} ({sess.client_name}) deletado.",
                ip_address=request.remote_addr
            )
            db.session.add(log)
            
            ChatMessage.query.filter_by(session_id=sess.id).delete()
            db.session.delete(sess)
            db.session.commit()
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error'}), 404
    except: return jsonify({'status': 'error'}), 500

@app.route('/admin')
@login_required
def admin():
    search_query = request.args.get('q'); date_filter = request.args.get('date'); status_filter = request.args.get('status')
    start_date = None
    if date_filter == 'today': start_date = datetime.utcnow().replace(hour=0, minute=0, second=0)
    elif date_filter == 'week': start_date = datetime.utcnow() - timedelta(weeks=1)
    elif date_filter == 'month': start_date = datetime.utcnow() - timedelta(days=30)
    
    leads_q = Lead.query; orders_q = Order.query; reviews_q = Review.query; sessions_q = ChatSession.query
    if start_date: leads_q = leads_q.filter(Lead.data >= start_date); orders_q = orders_q.filter(Order.data >= start_date); sessions_q = sessions_q.filter(ChatSession.created_at >= start_date)
    if search_query:
        sq = f"%{search_query}%"
        leads_q = leads_q.filter(or_(Lead.nome.like(sq), Lead.email.like(sq)))
        sessions_q = sessions_q.filter(or_(ChatSession.client_name.like(sq), ChatSession.id.like(sq)))
    if status_filter and status_filter != 'todos': sessions_q = sessions_q.filter(ChatSession.status == status_filter)

    leads = leads_q.order_by(Lead.data.desc()).all()
    orders = orders_q.order_by(Order.data.desc()).all()
    reviews = reviews_q.order_by(Review.data.desc()).all()
    sessions = sessions_q.order_by(ChatSession.created_at.desc()).all()
    try: total_visits = Visit.query.count()
    except: total_visits = 0

    active_uuid = request.args.get('session_id'); chat_history, active_ticket, active_ticket_status = [], "", ""
    if active_uuid:
        sess = ChatSession.query.filter_by(session_uuid=active_uuid).first()
        if sess:
            chat_history = ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all()
            active_ticket = f"#{sess.id:04d} - {sess.client_name}"; active_ticket_status = sess.status
    for s in sessions: s.full_title = f"#{s.id:04d} - {s.client_name or 'Visitante'}"; s.uuid = s.session_uuid
    
    leads_chart = {'labels': ['Seg', 'Ter'], 'values': [0,0]}; sales_chart = {'labels': ['Start', 'Growth'], 'values': [0, 0]} 
    return render_template('admin.html', leads=leads, orders=orders, reviews=reviews, sessions=sessions,
                           total_visits=total_visits, active_session=active_uuid, chat_history=chat_history, 
                           active_ticket=active_ticket, active_ticket_status=active_ticket_status,
                           leads_chart=json.dumps(leads_chart), sales_chart=json.dumps(sales_chart))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    form = LoginForm()
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user)
            return redirect(url_for('admin'))
        flash('Login inválido')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            u = User(username='admin'); u.password_hash = generate_password_hash('admin123')
            db.session.add(u); db.session.commit()
    app.run(debug=True, port=5000)