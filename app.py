from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import sqlite3
import os
import pandas as pd
import json
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
from dotenv import load_dotenv

pasta_atual = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.join(pasta_atual, '.env')

if not os.path.exists(caminho_env):
    with open(caminho_env, 'w') as f:
        f.write(f"ENCRYPTION_KEY={Fernet.generate_key().decode()}\n")
        f.write(f"SECRET_KEY={os.urandom(24).hex()}\n")
        f.write(f"ADMIN_PASSWORD=admin\n")
        f.write(f"EMAIL_USER=\n")
        f.write(f"EMAIL_PASS=\n")

load_dotenv(caminho_env)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
cipher_suite = Fernet(os.getenv('ENCRYPTION_KEY'))

UPLOAD_FOLDER = os.path.join(pasta_atual, 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY, nome TEXT, email TEXT, telefone TEXT, projeto TEXT, data TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_messages (id INTEGER PRIMARY KEY, session_id TEXT, tipo TEXT, conteudo TEXT, remetente TEXT, data TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, plano TEXT, preco TEXT, metodo TEXT, parcelas TEXT, status TEXT, data TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY, nome TEXT, email TEXT, empresa TEXT, avaliacao TEXT, estrelas INTEGER, data TEXT)''')
    conn.commit()
    conn.close()

init_db()

def encrypt(data): return cipher_suite.encrypt(data.encode()).decode() if data else None
def decrypt(token): 
    try: return cipher_suite.decrypt(token.encode()).decode() if token else token
    except: return token

@app.route('/')
def index(): return render_template('index.html')

@app.route('/avaliacoes')
def reviews(): return render_template('reviews.html')

@app.route('/checkout/<plano>')
def checkout(plano):
    precos = {'Silver': 1500, 'Gold': 3200, 'Rubi': 7000}
    preco_num = precos.get(plano, 0)
    preco_fmt = f"{preco_num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return render_template('checkout.html', plano=plano, preco=preco_fmt)

@app.route('/submit_lead', methods=['POST'])
def submit_lead():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO leads (nome, email, telefone, projeto, data) VALUES (?, ?, ?, ?, ?)",
                 (encrypt(data['nome']), encrypt(data['email']), encrypt(data['telefone']), encrypt(data['projeto']), datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/submit_review', methods=['POST'])
def submit_review():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO reviews (nome, email, empresa, avaliacao, estrelas, data) VALUES (?, ?, ?, ?, ?, ?)",
                 (encrypt(data['nome']), encrypt(data['email']), encrypt(data['empresa']), encrypt(data['avaliacao']), data['estrelas'], datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/processar_pagamento', methods=['POST'])
def processar_pagamento():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO orders (plano, preco, metodo, parcelas, status, data) VALUES (?, ?, ?, ?, ?, ?)",
                 (data['plano'], data['preco'], data['metodo'], data.get('parcelas', '1x'), 'Pendente', datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/send_chat', methods=['POST'])
def send_chat():
    try:
        session_id = request.form.get('session_id')
        remetente = request.form.get('remetente', 'user') 
        tipo, conteudo = 'texto', ''

        if 'arquivo' in request.files:
            file = request.files['arquivo']
            if file.filename:
                filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                tipo, conteudo = 'arquivo', filename
        elif 'audio' in request.files:
            file = request.files['audio']
            filename = secure_filename(f"audio_{datetime.now().timestamp()}.webm")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            tipo, conteudo = 'audio', filename
        else:
            msg = request.form.get('message')
            if msg: 
                tipo, conteudo = 'texto', encrypt(msg)

        if conteudo:
            conn = get_db()
            conn.execute("INSERT INTO chat_messages (session_id, tipo, conteudo, remetente, data) VALUES (?, ?, ?, ?, ?, ?)",
                         (session_id, tipo, conteudo, remetente, datetime.now().strftime("%d/%m %H:%M")))
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'content': conteudo, 'type': tipo})
            
        return jsonify({'status': 'error', 'message': 'Vazio'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == os.getenv('ADMIN_PASSWORD'):
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        return render_template('login.html', error="Senha Incorreta")
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not session.get('admin_logged_in'): return redirect(url_for('login'))
    
    conn = get_db()
    c = conn.cursor()
    
    raw_leads = c.execute("SELECT * FROM leads").fetchall()
    raw_orders = c.execute("SELECT * FROM orders").fetchall()
    
    leads = []
    for l in raw_leads:
        leads.append({
            'id': l['id'],
            'nome': decrypt(l['nome']),
            'email': decrypt(l['email']),
            'telefone': decrypt(l['telefone']),
            'projeto': decrypt(l['projeto']),
            'data': l['data']
        })
    df_leads = pd.DataFrame(leads) if leads else pd.DataFrame(columns=['data'])
    
    leads_chart_data = {'labels': [], 'values': []}
    if not df_leads.empty:
        df_leads['data'] = pd.to_datetime(df_leads['data'], errors='coerce').dt.strftime('%Y-%m-%d')
        counts = df_leads['data'].value_counts().sort_index()
        leads_chart_data['labels'] = counts.index.tolist()
        leads_chart_data['values'] = counts.values.tolist()

    orders_data = [dict(row) for row in raw_orders]
    df_orders = pd.DataFrame(orders_data) if orders_data else pd.DataFrame(columns=['plano'])
    
    sales_chart_data = {'labels': [], 'values': []}
    if not df_orders.empty:
        counts = df_orders['plano'].value_counts()
        sales_chart_data['labels'] = counts.index.tolist()
        sales_chart_data['values'] = counts.values.tolist()

    sessions_query = "SELECT DISTINCT session_id FROM chat_messages ORDER BY id DESC"
    sessions = [r[0] for r in c.execute(sessions_query).fetchall()]
    
    active_session = request.args.get('session_id')
    if not active_session and sessions:
        active_session = sessions[0]
    
    chat_history = []
    if active_session:
        msgs = c.execute("SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id ASC", (active_session,)).fetchall()
        for m in msgs:
            content = decrypt(m['conteudo']) if m['tipo'] == 'texto' else m['conteudo']
            chat_history.append({'tipo': m['tipo'], 'conteudo': content, 'remetente': m['remetente'], 'data': m['data']})

    conn.close()

    return render_template('admin.html', 
                           leads=leads, 
                           orders=raw_orders, 
                           leads_chart=json.dumps(leads_chart_data),
                           sales_chart=json.dumps(sales_chart_data),
                           sessions=sessions, 
                           active_session=active_session, 
                           chat_history=chat_history)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)