import os
import uuid
import json
import csv
import io
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from flask_mail import Mail, Message
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Imports locais
from models import db, User, Lead, Order, Review, ChatSession, ChatMessage
from forms import LoginForm

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SECRET_KEY'] = 'chave-ultra-secreta-agencia'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')

# Config Email (Mantenha seus dados)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'seu_email@gmail.com' 
app.config['MAIL_PASSWORD'] = 'sua_senha_app'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Inicializações
db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- MODELO EXTRA: VISITAS ---
class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page = db.Column(db.String(50))
    date = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.template_filter('format_currency')
def format_currency(value):
    try: return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return f"R$ {value}"

# --- ROTAS PÚBLICAS ---

@app.route('/')
def index():
    v = Visit(page='home')
    db.session.add(v)
    db.session.commit()
    return render_template('index.html')

@app.route('/avaliacoes')
def reviews():
    all_reviews = Review.query.order_by(Review.data.desc()).all()
    return render_template('reviews.html', reviews=all_reviews)

@app.route('/submit_lead', methods=['POST'])
@csrf.exempt
def submit_lead():
    try:
        nome = request.form.get('nome')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        projeto = request.form.get('projeto')
        
        info_extra = ""
        if 'arquivo' in request.files:
            file = request.files['arquivo']
            if file and file.filename != '':
                safe_name = secure_filename(file.filename)
                final_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], final_name))
                info_extra = f" [Anexo: {final_name}]"

        lead = Lead(nome=nome, email=email, telefone=telefone, projeto=f"{projeto}{info_extra}")
        db.session.add(lead)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error'}), 500

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
        db.session.add(review)
        db.session.commit()
        return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'}), 500

# --- CHAT API ---

@app.route('/init_session', methods=['POST'])
@csrf.exempt
def init_session():
    # Pega a categoria enviada pelo botão (Ex: Financeiro)
    data = request.json
    categoria = data.get('category', 'Geral') if data else 'Geral'
    
    # Obs: Se você deletou o DB, o modelo ChatSession será recriado com a coluna category.
    # Se não deletou, vai dar erro. DELETE O ARQUIVO database.db.
    new_session = ChatSession(session_uuid=uuid.uuid4().hex, category=categoria)
    
    db.session.add(new_session)
    db.session.commit()
    
    return jsonify({
        'status': 'success', 
        'session_id': new_session.session_uuid, 
        'ticket': f"#{new_session.id:04d}",
        'category': categoria
    })

@app.route('/send_chat', methods=['POST'])
@csrf.exempt
def send_chat():
    session_uuid = request.form.get('session_id')
    remetente = request.form.get('remetente')
    chat_session = ChatSession.query.filter_by(session_uuid=session_uuid).first()
    
    if not chat_session: return jsonify({'status': 'error'}), 404

    if 'message' in request.form:
        db.session.add(ChatMessage(session_id=chat_session.id, tipo='texto', conteudo=request.form['message'], remetente=remetente))
    
    if 'audio' in request.files:
        file = request.files['audio']
        fname = f"audio_{uuid.uuid4().hex}.webm"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        db.session.add(ChatMessage(session_id=chat_session.id, tipo='audio', conteudo=fname, remetente=remetente))

    if 'arquivo' in request.files:
        file = request.files['arquivo']
        fname = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        db.session.add(ChatMessage(session_id=chat_session.id, tipo='arquivo', conteudo=fname, remetente=remetente))

    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/get_messages/<session_uuid>') 
def get_messages(session_uuid):
    sess = ChatSession.query.filter_by(session_uuid=session_uuid).first()
    if not sess: return jsonify([])
    
    msgs = ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all()
    output = []
    for m in msgs:
        output.append({
            'remetente': m.remetente,
            'tipo': m.tipo,
            'conteudo': m.conteudo
        })
    return jsonify(output)

@app.route('/delete_ticket/<session_uuid>', methods=['DELETE'])
@csrf.exempt # Importante para o fetch funcionar fácil
@login_required
def delete_ticket(session_uuid):
    try:
        sess = ChatSession.query.filter_by(session_uuid=session_uuid).first()
        if sess:
            ChatMessage.query.filter_by(session_id=sess.id).delete()
            db.session.delete(sess)
            db.session.commit()
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'msg': 'Não encontrado'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

# --- ADMIN DASHBOARD ---

@app.route('/admin')
@login_required
def admin():
    search_query = request.args.get('q')
    date_filter = request.args.get('date')
    
    start_date = None
    if date_filter == 'today': start_date = datetime.utcnow() - timedelta(days=1)
    elif date_filter == 'week': start_date = datetime.utcnow() - timedelta(weeks=1)
    elif date_filter == 'month': start_date = datetime.utcnow() - timedelta(days=30)
    
    leads_q = Lead.query
    orders_q = Order.query
    reviews_q = Review.query

    if search_query:
        leads_q = leads_q.filter(Lead.nome.contains(search_query) | Lead.email.contains(search_query))
    
    if start_date:
        leads_q = leads_q.filter(Lead.data >= start_date)
        orders_q = orders_q.filter(Order.data >= start_date)

    leads = leads_q.order_by(Lead.data.desc()).all()
    orders = orders_q.order_by(Order.data.desc()).all()
    reviews = reviews_q.order_by(Review.data.desc()).all()
    sessions = ChatSession.query.order_by(ChatSession.created_at.desc()).all()
    total_visits = Visit.query.count()

    active_uuid = request.args.get('session_id')
    chat_history = []
    active_ticket = ""
    if active_uuid:
        sess = ChatSession.query.filter_by(session_uuid=active_uuid).first()
        if sess:
            chat_history = ChatMessage.query.filter_by(session_id=sess.id).order_by(ChatMessage.data).all()
            # Mostra TICKET + CATEGORIA no Admin
            cat = getattr(sess, 'category', 'Geral') # getattr para segurança
            active_ticket = f"#{sess.id:04d} - {cat}"
    
    for s in sessions: 
        cat = getattr(s, 'category', 'Geral')
        s.ticket = f"#{s.id:04d}"
        s.full_title = f"#{s.id:04d} - {cat}" # Usaremos isso no HTML
        s.uuid = s.session_uuid

    # Gráficos Mock (para evitar erro se vazio)
    leads_chart = {'labels': ['Seg', 'Ter', 'Qua'], 'values': [0,0,0]}
    sales_chart = {'labels': ['Silver', 'Gold'], 'values': [0,0]}

    if len(leads) > 0:
        chart_dates = {}
        for i in range(6, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime('%d/%m')
            chart_dates[d] = 0
        for l in leads:
            d_str = l.data.strftime('%d/%m')
            if d_str in chart_dates: chart_dates[d_str] += 1
        leads_chart = {'labels': list(chart_dates.keys()), 'values': list(chart_dates.values())}

    return render_template('admin.html', 
                           leads=leads, orders=orders, reviews=reviews, sessions=sessions,
                           total_visits=total_visits,
                           active_session=active_uuid, chat_history=chat_history, active_ticket=active_ticket,
                           leads_chart=json.dumps(leads_chart), sales_chart=json.dumps(sales_chart))

@app.route('/admin/export/<data_type>')
@login_required
def export_data(data_type):
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    filename = "export.csv"
    if data_type == 'leads':
        cw.writerow(['Nome', 'Email', 'Telefone', 'Projeto'])
        for i in Lead.query.all(): cw.writerow([i.nome, i.email, i.telefone, i.projeto])
        filename = "leads.csv"
    output = make_response('\ufeff' + si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-type"] = "text/csv; charset=utf-8-sig"
    return output

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            return redirect(url_for('admin'))
        flash('Erro Login')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        # ATUALIZA O MODELO CHAT SESSION COM CATEGORIA
        # Se não deletar o DB, isso pode dar erro. DELETE O DB.
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            u = User(username='admin')
            u.password_hash = generate_password_hash('admin123')
            db.session.add(u); db.session.commit()
    app.run(debug=True, port=5000)