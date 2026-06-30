"""
=============================================================
  CTM CABAPUÃ BRASIL - SISTEMA WEB DE GESTÃO
  Versão 3.0 - COM CHECK-IN APPS + GOOGLE CALENDAR + SURVEYHEART
  Acessível via PC local e Internet
=============================================================
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests
import os
import pickle
import json
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'sua-chave-secreta-aqui')

# Render fornece DATABASE_URL com prefixo 'postgres://' (legado);
# SQLAlchemy 1.4+ exige 'postgresql://' — corrigimos aqui.
_db_url = os.getenv('DATABASE_URL', 'sqlite:///ctm_cabapua.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ============ MODELOS DO BANCO DE DADOS ============

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    nivel = db.Column(db.String(20), default='recepcao')
    email = db.Column(db.String(120))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Aluno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_externo = db.Column(db.String(50), unique=True)
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120))
    telefone = db.Column(db.String(20))
    data_nascimento = db.Column(db.Date)
    data_matricula = db.Column(db.Date, default=date.today)
    
    tipo_aluno = db.Column(db.String(30), default='particular')
    matricula_app = db.Column(db.String(50))
    validade_plano_app = db.Column(db.Date)
    ultimo_checkin = db.Column(db.DateTime)
    
    modalidade = db.Column(db.String(50))
    graduacao = db.Column(db.String(50))
    plano = db.Column(db.String(50))
    valor = db.Column(db.Float)
    vencimento = db.Column(db.Date)
    status = db.Column(db.String(20), default='ativo')
    
    calendar_event_id = db.Column(db.String(100))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Aluno {self.nome}>'

class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('aluno.id'), nullable=False)
    data_checkin = db.Column(db.DateTime, default=datetime.utcnow)
    origem = db.Column(db.String(30))
    codigo_verificacao = db.Column(db.String(50))
    
    aluno = db.relationship('Aluno', backref=db.backref('checkins', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# ============ INTEGRAÇÃO GOOGLE CALENDAR ============

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = None
    token_path = 'token.pickle'
    
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('calendar', 'v3', credentials=creds)

def criar_evento_aniversario(aluno):
    try:
        service = get_calendar_service()
        if not service:
            return False
        
        evento = {
            'summary': f'Aniversario - {aluno.nome}',
            'description': f'Aluno: {aluno.nome}\nModalidade: {aluno.modalidade}\nTelefone: {aluno.telefone}',
            'start': {
                'date': aluno.data_nascimento.strftime('%Y-%m-%d'),
            },
            'end': {
                'date': (aluno.data_nascimento + timedelta(days=1)).strftime('%Y-%m-%d'),
            },
            'recurrence': ['RRULE:FREQ=YEARLY'],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 60},
                ],
            },
        }
        
        evento_criado = service.events().insert(calendarId='primary', body=evento).execute()
        aluno.calendar_event_id = evento_criado['id']
        db.session.commit()
        return True
    except Exception as error:
        print(f'Erro ao criar evento: {error}')
        return False

def deletar_evento_aniversario(aluno):
    if not aluno.calendar_event_id:
        return
    try:
        service = get_calendar_service()
        if service:
            service.events().delete(
                calendarId='primary', 
                eventId=aluno.calendar_event_id
            ).execute()
    except:
        pass

# ============ INTEGRAÇÃO SURVEYHEART ============

class SurveyHeartAPI:
    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = 'https://api.surveyheart.com/v1'
    
    def get_form_responses(self, form_id, limit=100):
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
        params = {'limit': limit, 'orderBy': '-createdAt'}
        
        try:
            response = requests.get(
                f'{self.base_url}/forms/{form_id}/responses',
                headers=headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f'Erro ao buscar respostas: {e}')
            return None
    
    def importar_respostas_como_alunos(self, form_id, mapeamento_campos):
        respostas = self.get_form_responses(form_id)
        if not respostas or 'data' not in respostas:
            return 0
        
        alunos_importados = 0
        
        for resposta in respostas['data']:
            try:
                if Aluno.query.filter_by(id_externo=str(resposta['id'])).first():
                    continue
                
                dados_resposta = resposta.get('data', {})
                
                aluno = Aluno(
                    id_externo=str(resposta['id']),
                    nome=dados_resposta.get(mapeamento_campos['nome'], ''),
                    email=dados_resposta.get(mapeamento_campos.get('email'), ''),
                    telefone=dados_resposta.get(mapeamento_campos.get('telefone'), ''),
                    modalidade=dados_resposta.get(mapeamento_campos.get('modalidade'), 'Nao informada'),
                    tipo_aluno='particular',
                    status='ativo'
                )
                
                if 'data_nascimento' in mapeamento_campos:
                    try:
                        data_str = dados_resposta.get(mapeamento_campos['data_nascimento'])
                        if data_str:
                            aluno.data_nascimento = datetime.strptime(data_str, '%Y-%m-%d').date()
                    except:
                        pass
                
                db.session.add(aluno)
                db.session.flush()
                
                if aluno.data_nascimento:
                    criar_evento_aniversario(aluno)
                
                alunos_importados += 1
                
            except Exception as e:
                print(f'Erro ao importar resposta {resposta.get("id")}: {e}')
                continue
        
        db.session.commit()
        return alunos_importados

# ============ ROTAS DA APLICAÇÃO ============

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = Usuario.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Usuario ou senha incorretos', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    total_alunos = Aluno.query.count()
    alunos_ativos = Aluno.query.filter_by(status='ativo').count()
    checkins_hoje = CheckIn.query.filter(
        CheckIn.data_checkin >= date.today()
    ).count()
    
    alunos_por_tipo = db.session.query(
        Aluno.tipo_aluno, db.func.count(Aluno.id)
    ).group_by(Aluno.tipo_aluno).all()
    
    mes_atual = datetime.now().month
    aniversariantes = Aluno.query.filter(
        db.extract('month', Aluno.data_nascimento) == mes_atual
    ).all()
    
    return render_template('dashboard.html',
                          total_alunos=total_alunos,
                          alunos_ativos=alunos_ativos,
                          checkins_hoje=checkins_hoje,
                          alunos_por_tipo=dict(alunos_por_tipo),
                          aniversariantes=aniversariantes)

@app.route('/alunos')
@login_required
def alunos():
    tipo_filtro = request.args.get('tipo', 'todos')
    busca = request.args.get('busca', '')
    
    query = Aluno.query
    
    if tipo_filtro != 'todos':
        query = query.filter_by(tipo_aluno=tipo_filtro)
    
    if busca:
        query = query.filter(Aluno.nome.ilike(f'%{busca}%'))
    
    alunos = query.order_by(Aluno.nome).all()
    
    return render_template('alunos.html', alunos=alunos, tipo_filtro=tipo_filtro)

@app.route('/aluno/novo', methods=['GET', 'POST'])
@login_required
def novo_aluno():
    if request.method == 'POST':
        aluno = Aluno(
            nome=request.form['nome'],
            email=request.form.get('email'),
            telefone=request.form.get('telefone'),
            tipo_aluno=request.form['tipo_aluno'],
            matricula_app=request.form.get('matricula_app'),
            modalidade=request.form.get('modalidade'),
            graduacao=request.form.get('graduacao'),
            plano=request.form.get('plano'),
            valor=float(request.form.get('valor', 0)),
            status=request.form.get('status', 'ativo')
        )
        
        if request.form.get('data_nascimento'):
            aluno.data_nascimento = datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date()
        
        if request.form.get('validade_plano_app'):
            aluno.validade_plano_app = datetime.strptime(request.form['validade_plano_app'], '%Y-%m-%d').date()
        
        if request.form.get('vencimento'):
            aluno.vencimento = datetime.strptime(request.form['vencimento'], '%Y-%m-%d').date()
        
        db.session.add(aluno)
        db.session.commit()
        
        if aluno.data_nascimento:
            criar_evento_aniversario(aluno)
        
        flash('Aluno cadastrado com sucesso!', 'success')
        return redirect(url_for('alunos'))
    
    return render_template('aluno_form.html', aluno=None)

@app.route('/aluno/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_aluno(id):
    aluno = Aluno.query.get_or_404(id)
    
    if request.method == 'POST':
        aluno.nome = request.form['nome']
        aluno.email = request.form.get('email')
        aluno.telefone = request.form.get('telefone')
        aluno.tipo_aluno = request.form['tipo_aluno']
        aluno.matricula_app = request.form.get('matricula_app')
        aluno.modalidade = request.form.get('modalidade')
        aluno.graduacao = request.form.get('graduacao')
        aluno.plano = request.form.get('plano')
        aluno.valor = float(request.form.get('valor', 0))
        aluno.status = request.form.get('status', 'ativo')
        
        if request.form.get('data_nascimento'):
            aluno.data_nascimento = datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date()
        
        if request.form.get('validade_plano_app'):
            aluno.validade_plano_app = datetime.strptime(request.form['validade_plano_app'], '%Y-%m-%d').date()
        
        if request.form.get('vencimento'):
            aluno.vencimento = datetime.strptime(request.form['vencimento'], '%Y-%m-%d').date()
        
        db.session.commit()
        
        flash('Aluno atualizado com sucesso!', 'success')
        return redirect(url_for('alunos'))
    
    return render_template('aluno_form.html', aluno=aluno)

@app.route('/aluno/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_aluno(id):
    aluno = Aluno.query.get_or_404(id)
    deletar_evento_aniversario(aluno)
    db.session.delete(aluno)
    db.session.commit()
    flash('Aluno excluido com sucesso!', 'success')
    return redirect(url_for('alunos'))

@app.route('/checkin', methods=['GET', 'POST'])
@login_required
def registrar_checkin():
    if request.method == 'POST':
        matricula_app = request.form.get('matricula_app')
        origem = request.form.get('origem')
        
        aluno = Aluno.query.filter_by(matricula_app=matricula_app, tipo_aluno=origem).first()
        
        if not aluno:
            flash('Aluno nao encontrado!', 'error')
            return redirect(url_for('registrar_checkin'))
        
        if aluno.validade_plano_app and aluno.validade_plano_app < date.today():
            flash('Plano do aluno esta vencido!', 'warning')
        
        checkin = CheckIn(
            aluno_id=aluno.id,
            origem=origem,
            codigo_verificacao=request.form.get('codigo', '')
        )
        
        aluno.ultimo_checkin = datetime.utcnow()
        
        db.session.add(checkin)
        db.session.commit()
        
        flash(f'Check-in registrado: {aluno.nome}', 'success')
        return redirect(url_for('registrar_checkin'))
    
    return render_template('checkin.html')

@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    data = request.get_json()
    
    app_nome = data.get('app')
    matricula = data.get('matricula')
    codigo = data.get('codigo_verificacao', '')
    
    if not app_nome or not matricula:
        return jsonify({'error': 'Dados incompletos'}), 400
    
    aluno = Aluno.query.filter_by(matricula_app=matricula, tipo_aluno=app_nome).first()
    
    if not aluno:
        return jsonify({'error': 'Aluno nao encontrado'}), 404
    
    checkin = CheckIn(
        aluno_id=aluno.id,
        origem=app_nome,
        codigo_verificacao=codigo
    )
    
    aluno.ultimo_checkin = datetime.utcnow()
    
    db.session.add(checkin)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'aluno': aluno.nome,
        'data_checkin': checkin.data_checkin.isoformat()
    })

@app.route('/surveyheart/importar', methods=['GET', 'POST'])
@login_required
def importar_surveyheart():
    if request.method == 'POST':
        api_token = request.form.get('api_token')
        form_id = request.form.get('form_id')
        
        mapeamento = {
            'nome': request.form.get('field_nome'),
            'email': request.form.get('field_email'),
            'telefone': request.form.get('field_telefone'),
            'data_nascimento': request.form.get('field_nascimento'),
            'modalidade': request.form.get('field_modalidade')
        }
        
        api = SurveyHeartAPI(api_token)
        importados = api.importar_respostas_como_alunos(form_id, mapeamento)
        
        flash(f'{importados} aluno(s) importado(s) com sucesso!', 'success')
        return redirect(url_for('alunos'))
    
    return render_template('surveyheart_import.html')

@app.route('/relatorios')
@login_required
def relatorios():
    checkins_por_app = db.session.query(
        CheckIn.origem, db.func.count(CheckIn.id)
    ).group_by(CheckIn.origem).all()
    
    daqui_7_dias = date.today() + timedelta(days=7)
    planos_vencendo = Aluno.query.filter(
        Aluno.validade_plano_app <= daqui_7_dias,
        Aluno.validade_plano_app >= date.today(),
        Aluno.status == 'ativo'
    ).all()
    
    return render_template('relatorios.html',
                          checkins_por_app=dict(checkins_por_app),
                          planos_vencendo=planos_vencendo)

# ============ INICIALIZAÇÃO DO BANCO ============

def criar_usuario_admin():
    if not Usuario.query.filter_by(username='admin').first():
        admin = Usuario(
            username='admin',
            nome='Administrador',
            nivel='admin',
            email='admin@ctmcabapua.com.br'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Usuario admin criado: admin / admin123')

# Comando CLI: flask init-db
# Usado no Render como "Build Command" ou job único.
import click

@app.cli.command('init-db')
def init_db_command():
    """Cria tabelas e usuário admin padrão."""
    db.create_all()
    criar_usuario_admin()
    click.echo('Banco de dados inicializado!')

# ── Inicialização automática do banco ──────────────────────────
# Roda sempre que o módulo é importado (gunicorn, flask run, python app.py).
# O try/except evita crash se DATABASE_URL ainda não estiver disponível.
try:
    with app.app_context():
        db.create_all()
        criar_usuario_admin()
except Exception as _e:
    print(f'[AVISO] Não foi possível inicializar o banco agora: {_e}')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
