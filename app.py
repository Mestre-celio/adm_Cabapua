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
from functools import wraps
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

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.nivel != 'admin':
            flash('Acesso restrito a administradores!', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ============ MODELOS DO BANCO DE DADOS ============

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    nivel = db.Column(db.String(20), default='recepcao')
    email = db.Column(db.String(120))
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    primeiro_acesso = db.Column(db.Boolean, default=True)
    
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
    
    # Dados de saúde
    possui_condicao_saude = db.Column(db.Boolean, default=False)
    condicoes_saude = db.Column(db.Text)
    alergias = db.Column(db.Text)
    medicamentos = db.Column(db.Text)
    contato_emergencia = db.Column(db.String(200))
    endereco = db.Column(db.String(300))
    responsavel = db.Column(db.String(150))
    altura = db.Column(db.Float)
    peso = db.Column(db.Float)
    genero = db.Column(db.String(20))
    
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

class Pagamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey('aluno.id'), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_pagamento = db.Column(db.Date, nullable=False, default=date.today)
    data_vencimento = db.Column(db.Date, nullable=False)
    tipo_plano = db.Column(db.String(20), nullable=False)
    forma_pagamento = db.Column(db.String(30))
    status = db.Column(db.String(20), default='pago')
    observacoes = db.Column(db.Text)
    referencia = db.Column(db.String(50))
    
    aluno = db.relationship('Aluno', backref=db.backref('pagamentos', lazy=True))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Pagamento {self.aluno.nome} - {self.data_pagamento}>'

# ============ MODELO DE ATIVIDADES (MÚLTIPLAS POR ALUNO) ============

aluno_atividades = db.Table('aluno_atividades',
    db.Column('aluno_id', db.Integer, db.ForeignKey('aluno.id'), primary_key=True),
    db.Column('atividade_id', db.Integer, db.ForeignKey('atividade.id'), primary_key=True),
    db.Column('data_inicio', db.Date, default=date.today),
    db.Column('desconto_aplicado', db.Boolean, default=False)
)

class Atividade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    descricao = db.Column(db.Text)
    valor_base = db.Column(db.Float, nullable=False)
    ativa = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Atividade {self.nome}>'

# Adicionar relacionamento e métodos ao modelo Aluno (injetados após definição)
Aluno.atividades = db.relationship('Atividade', secondary=aluno_atividades,
    backref=db.backref('alunos_rel', lazy='dynamic'), lazy='dynamic')

def calcular_mensalidade(self):
    if self.tipo_aluno in ('wellhub', 'totalpass', 'gurupass'):
        return 0
    if self.tipo_aluno == 'particular':
        return self.valor or 0
    ats = self.atividades.filter_by(ativa=True).all()
    if not ats:
        return 0
    vals = sorted([a.valor_base for a in ats], reverse=True)
    return vals[0] + sum(v * 0.5 for v in vals[1:])

Aluno.calcular_mensalidade = calcular_mensalidade

def get_atividades_com_desconto(self):
    if self.tipo_aluno != 'turma':
        return []
    ats = self.atividades.filter_by(ativa=True).all()
    if not ats:
        return []
    ordenadas = sorted(ats, key=lambda a: a.valor_base, reverse=True)
    resultado = []
    for i, a in enumerate(ordenadas):
        if i == 0:
            resultado.append({'atividade': a, 'valor_original': a.valor_base, 'desconto': 0, 'valor_final': a.valor_base})
        else:
            resultado.append({'atividade': a, 'valor_original': a.valor_base, 'desconto': a.valor_base * 0.5, 'valor_final': a.valor_base * 0.5})
    return resultado

Aluno.get_atividades_com_desconto = get_atividades_com_desconto

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Blueprint WhatsApp (importado após modelos para evitar circularidade)
from routes.whatsapp import whatsapp_bp
app.register_blueprint(whatsapp_bp)

# Blueprint Pagamentos
from routes.pagamentos import pagamentos_bp
app.register_blueprint(pagamentos_bp)

from routes.importacao import importacao_bp
app.register_blueprint(importacao_bp)

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
        if current_user.nivel == 'professor':
            return redirect(url_for('professor_dashboard'))
        return redirect(url_for('dashboard'))
    return render_template('splash.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        nivel_solicitado = request.form.get('nivel', 'admin')
        user = Usuario.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if user.nivel != nivel_solicitado:
                flash(f'Usuário não possui permissão de acesso como {nivel_solicitado}!', 'error')
                return render_template('login.html', google_enabled=bool(os.getenv('GOOGLE_CLIENT_ID')))
            login_user(user)
            if user.primeiro_acesso:
                flash('Por segurança, altere sua senha agora!', 'warning')
                return redirect(url_for('trocar_senha'))
            return redirect(url_for('dashboard'))
        flash('Usuario ou senha incorretos', 'error')
    
    google_enabled = bool(os.getenv('GOOGLE_CLIENT_ID'))
    return render_template('login.html', google_enabled=google_enabled)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/login/google')
def login_google():
    google_id = os.getenv('GOOGLE_CLIENT_ID')
    if not google_id:
        flash('Login com Google não configurado!', 'error')
        return redirect(url_for('login'))
    
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth(app)
    oauth.register(
        name='google',
        client_id=google_id,
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )
    redirect_uri = url_for('auth_google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/auth/google/callback')
def auth_google_callback():
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth(app)
    oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )
    
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.parse_id_token(token)
    
    email = user_info.get('email')
    nome = user_info.get('name')
    google_id = user_info.get('sub')
    
    usuario = Usuario.query.filter_by(google_id=google_id).first()
    if not usuario:
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario:
            usuario.google_id = google_id
            db.session.commit()
        else:
            username = email.split('@')[0]
            usuario = Usuario(
                username=username,
                password_hash=generate_password_hash('google_' + google_id),
                nome=nome, email=email, google_id=google_id,
                nivel='admin', primeiro_acesso=True
            )
            db.session.add(usuario)
            db.session.commit()
    
    login_user(usuario)
    if usuario.primeiro_acesso:
        flash('Bem-vindo! Configure sua senha.', 'warning')
        return redirect(url_for('trocar_senha'))
    flash('Login com Google realizado!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/professor/dashboard')
@login_required
def professor_dashboard():
    total_alunos = Aluno.query.count()
    alunos_ativos = Aluno.query.filter_by(status='ativo').count()
    checkins_hoje = CheckIn.query.filter(
        CheckIn.data_checkin >= date.today()
    ).count()
    alunos_saude = Aluno.query.filter_by(possui_condicao_saude=True).count()
    return render_template('professor_dashboard.html',
                          total_alunos=total_alunos,
                          alunos_ativos=alunos_ativos,
                          checkins_hoje=checkins_hoje,
                          alunos_saude=alunos_saude)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.nivel == 'professor':
        return redirect(url_for('professor_dashboard'))
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
        db.extract('month', Aluno.data_nascimento) == mes_atual,
        Aluno.status == 'ativo'
    ).all()
    
    # Alunos com condicoes de saude
    alunos_saude = Aluno.query.filter_by(possui_condicao_saude=True).count()
    
    # Dados para grafico de modalidades
    modalidades = db.session.query(Aluno.modalidade, db.func.count(Aluno.id))\
        .filter_by(status='ativo')\
        .group_by(Aluno.modalidade).all()
    modalidades_labels = [m[0] or 'Nao informada' for m in modalidades]
    modalidades_data = [m[1] for m in modalidades]
    
    # Dados para grafico de tipos
    tipos = db.session.query(Aluno.tipo_aluno, db.func.count(Aluno.id))\
        .filter_by(status='ativo')\
        .group_by(Aluno.tipo_aluno).all()
    tipos_labels = [t[0].title() for t in tipos]
    tipos_data = [t[1] for t in tipos]
    
    return render_template('dashboard.html',
                          total_alunos=total_alunos,
                          alunos_ativos=alunos_ativos,
                          checkins_hoje=checkins_hoje,
                          alunos_por_tipo=dict(alunos_por_tipo),
                          aniversariantes=aniversariantes,
                          alunos_saude=alunos_saude,
                          modalidades_labels=modalidades_labels,
                          modalidades_data=modalidades_data,
                          tipos_labels=tipos_labels,
                          tipos_data=tipos_data)

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
        try:
            aluno = Aluno(
                nome=request.form['nome'],
                email=request.form.get('email') or None,
                telefone=request.form.get('telefone') or None,
                tipo_aluno=request.form.get('tipo_aluno', 'turma'),
                matricula_app=request.form.get('matricula_app') or None,
                graduacao=request.form.get('graduacao') or None,
                plano=request.form.get('plano') or None,
                valor=request.form.get('valor', type=float) or None,
                status=request.form.get('status', 'ativo'),
                endereco=request.form.get('endereco') or None,
                responsavel=request.form.get('responsavel') or None,
                possui_condicao_saude=request.form.get('possui_condicao') == 'sim',
                condicoes_saude=request.form.get('condicoes_saude') or None,
                alergias=request.form.get('alergias') or None,
                medicamentos=request.form.get('medicamentos') or None,
                contato_emergencia=request.form.get('contato_emergencia') or None
            )
            
            try:
                if request.form.get('data_nascimento'):
                    aluno.data_nascimento = datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date()
            except ValueError:
                flash('Data de nascimento inválida', 'warning')
            
            try:
                if request.form.get('validade_plano_app'):
                    aluno.validade_plano_app = datetime.strptime(request.form['validade_plano_app'], '%Y-%m-%d').date()
            except ValueError:
                flash('Data de validade do plano inválida', 'warning')
            
            try:
                if request.form.get('vencimento'):
                    aluno.vencimento = datetime.strptime(request.form['vencimento'], '%Y-%m-%d').date()
            except ValueError:
                flash('Data de vencimento inválida', 'warning')
            
            db.session.add(aluno)
            db.session.flush()
            
            for ativ_id in request.form.getlist('atividades'):
                try:
                    atividade = Atividade.query.get(int(ativ_id))
                    if atividade:
                        aluno.atividades.append(atividade)
                except (ValueError, TypeError):
                    continue
            
            db.session.commit()
            
            if aluno.data_nascimento:
                try:
                    criar_evento_aniversario(aluno)
                except Exception as e:
                    print(f'Erro evento aniversário: {e}')
            
            flash('Aluno cadastrado com sucesso!', 'success')
            return redirect(url_for('alunos'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar aluno: {str(e)}', 'error')
            todas_atividades = Atividade.query.filter_by(ativa=True).order_by(Atividade.nome).all()
            return render_template('aluno_form.html', aluno=None, atividades=todas_atividades)
    
    todas_atividades = Atividade.query.filter_by(ativa=True).order_by(Atividade.nome).all()
    return render_template('aluno_form.html', aluno=None, atividades=todas_atividades)

@app.route('/aluno/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_aluno(id):
    aluno = Aluno.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            aluno.nome = request.form['nome']
            aluno.email = request.form.get('email') or None
            aluno.telefone = request.form.get('telefone') or None
            aluno.tipo_aluno = request.form.get('tipo_aluno', 'turma')
            aluno.matricula_app = request.form.get('matricula_app') or None
            aluno.graduacao = request.form.get('graduacao') or None
            aluno.plano = request.form.get('plano') or None
            aluno.valor = request.form.get('valor', type=float) or None
            aluno.status = request.form.get('status', 'ativo')
            aluno.endereco = request.form.get('endereco') or None
            aluno.responsavel = request.form.get('responsavel') or None
            aluno.possui_condicao_saude = request.form.get('possui_condicao') == 'sim'
            aluno.condicoes_saude = request.form.get('condicoes_saude') or None
            aluno.alergias = request.form.get('alergias') or None
            aluno.medicamentos = request.form.get('medicamentos') or None
            aluno.contato_emergencia = request.form.get('contato_emergencia') or None
            
            try:
                if request.form.get('data_nascimento'):
                    aluno.data_nascimento = datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date()
            except ValueError:
                flash('Data de nascimento inválida', 'warning')
            
            try:
                if request.form.get('validade_plano_app'):
                    aluno.validade_plano_app = datetime.strptime(request.form['validade_plano_app'], '%Y-%m-%d').date()
            except ValueError:
                flash('Data de validade do plano inválida', 'warning')
            
            try:
                if request.form.get('vencimento'):
                    aluno.vencimento = datetime.strptime(request.form['vencimento'], '%Y-%m-%d').date()
            except ValueError:
                flash('Data de vencimento inválida', 'warning')
            
            for atividade in list(aluno.atividades.all()):
                aluno.atividades.remove(atividade)
            
            for ativ_id in request.form.getlist('atividades'):
                try:
                    atividade = Atividade.query.get(int(ativ_id))
                    if atividade:
                        aluno.atividades.append(atividade)
                except (ValueError, TypeError):
                    continue
            
            db.session.commit()
            
            flash('Aluno atualizado com sucesso!', 'success')
            return redirect(url_for('alunos'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao editar aluno: {str(e)}', 'error')
            todas_atividades = Atividade.query.filter_by(ativa=True).order_by(Atividade.nome).all()
            return render_template('aluno_form.html', aluno=aluno, atividades=todas_atividades)
    
    todas_atividades = Atividade.query.filter_by(ativa=True).order_by(Atividade.nome).all()
    return render_template('aluno_form.html', aluno=aluno, atividades=todas_atividades)

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

@app.route('/test-save')
@login_required
def test_save():
    try:
        atividade = Atividade.query.first()
        if not atividade:
            return 'ERRO: Nenhuma atividade cadastrada. Acesse /atividades primeiro.'
        aluno_teste = Aluno(nome='Aluno Teste', telefone='000000000', tipo_aluno='particular', status='ativo')
        db.session.add(aluno_teste)
        db.session.flush()
        aluno_teste.atividades.append(atividade)
        db.session.commit()
        db.session.delete(aluno_teste)
        db.session.commit()
        return 'OK: Sistema funcionando corretamente!'
    except Exception as e:
        db.session.rollback()
        return f'ERRO: {str(e)}'

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

@app.route('/trocar-senha', methods=['GET', 'POST'])
@login_required
def trocar_senha():
    if request.method == 'POST':
        senha_atual = request.form.get('senha_atual')
        nova_senha = request.form.get('nova_senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        if not current_user.check_password(senha_atual):
            flash('Senha atual incorreta!', 'error')
            return render_template('trocar_senha.html')
        
        if nova_senha != confirmar_senha:
            flash('As novas senhas não conferem!', 'error')
            return render_template('trocar_senha.html')
        
        if len(nova_senha) < 8:
            flash('A nova senha deve ter pelo menos 8 caracteres!', 'error')
            return render_template('trocar_senha.html')
        
        current_user.set_password(nova_senha)
        current_user.primeiro_acesso = False
        db.session.commit()
        flash('Senha alterada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('trocar_senha.html')

@app.route('/alunos/saude')
@login_required
def alunos_saude():
    alunos_lista = Aluno.query.filter_by(possui_condicao_saude=True).order_by(Aluno.nome).all()
    return render_template('alunos_saude.html', alunos=alunos_lista)

@app.route('/aluno/<int:aluno_id>/pagamentos')
@login_required
def pagamentos_aluno(aluno_id):
    return redirect(url_for('pagamentos.historico_aluno', aluno_id=aluno_id))

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

# ============ ROTAS DE ATIVIDADES ============

@app.route('/atividades')
@login_required
def listar_atividades():
    lista = Atividade.query.order_by(Atividade.nome).all()
    return render_template('atividades.html', atividades=lista)

@app.route('/atividade/nova', methods=['GET', 'POST'])
@login_required
@admin_required
def nova_atividade():
    if request.method == 'POST':
        a = Atividade(
            nome=request.form['nome'],
            descricao=request.form.get('descricao'),
            valor_base=float(request.form['valor_base']),
            ativa=request.form.get('ativa') == 'on'
        )
        db.session.add(a)
        db.session.commit()
        flash('Atividade criada!', 'success')
        return redirect(url_for('listar_atividades'))
    return render_template('atividade_form.html', atividade=None)

@app.route('/atividade/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_atividade(id):
    a = Atividade.query.get_or_404(id)
    if request.method == 'POST':
        a.nome = request.form['nome']
        a.descricao = request.form.get('descricao')
        a.valor_base = float(request.form['valor_base'])
        a.ativa = request.form.get('ativa') == 'on'
        db.session.commit()
        flash('Atividade atualizada!', 'success')
        return redirect(url_for('listar_atividades'))
    return render_template('atividade_form.html', atividade=a)

@app.route('/atividade/<int:id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_atividade(id):
    a = Atividade.query.get_or_404(id)
    if a.alunos_rel.count() > 0:
        flash(f'Atividade vinculada a {a.alunos_rel.count()} aluno(s)!', 'error')
        return redirect(url_for('listar_atividades'))
    db.session.delete(a)
    db.session.commit()
    flash('Atividade excluída!', 'success')
    return redirect(url_for('listar_atividades'))

# ============ DASHBOARD FINANCEIRO ============

@app.route('/dashboard/financeiro')
@login_required
@admin_required
def dashboard_financeiro():
    alunos = Aluno.query.filter_by(status='ativo').all()
    receita_total = sum(a.calcular_mensalidade() for a in alunos)
    total_descontos = sum(sum(i['desconto'] for i in a.get_atividades_com_desconto()) for a in alunos)
    alunos_com_desconto = sum(1 for a in alunos if a.atividades.count() > 1)

    dados_por_atividade = {}
    for a in alunos:
        for info in a.get_atividades_com_desconto():
            nome = info['atividade'].nome
            if nome not in dados_por_atividade:
                dados_por_atividade[nome] = {'quantidade': 0, 'receita': 0}
            dados_por_atividade[nome]['quantidade'] += 1
            dados_por_atividade[nome]['receita'] += info['valor_final']

    return render_template('dashboard_financeiro.html',
        receita_mensal=receita_total,
        total_descontos=total_descontos,
        alunos_com_desconto=alunos_com_desconto,
        projecao_1_mes=receita_total,
        projecao_3_meses=receita_total * 3,
        projecao_6_meses=receita_total * 6,
        dados_por_atividade=dados_por_atividade,
        total_alunos=len(alunos))

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
        admin.primeiro_acesso = True
        db.session.add(admin)
        db.session.commit()
        print('Usuario admin criado: admin / admin123')

    if not Usuario.query.filter_by(username='professor').first():
        professor = Usuario(
            username='professor',
            nome='Professor',
            nivel='professor',
            email='professor@ctmcabapua.com.br'
        )
        professor.set_password('prof123')
        professor.primeiro_acesso = True
        db.session.add(professor)
        db.session.commit()
        print('Usuario professor criado: professor / prof123')

# Comando CLI: flask init-db
# Usado no Render como "Build Command" ou job único.
import click

@app.cli.command('init-db')
def init_db_command():
    """Cria tabelas e usuário admin padrão."""
    db.create_all()
    criar_usuario_admin()
    click.echo('Banco de dados inicializado!')

# ── Migração automática do banco ───────────────────────────────
# Adiciona colunas novas em tabelas existentes (para SQLite).
def migrar_banco():
    """Adiciona colunas que podem não existir em bancos criados antes da versão atual."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    
    migracoes = [
        ('usuario', 'google_id', 'VARCHAR(100)'),
        ('usuario', 'primeiro_acesso', 'BOOLEAN'),
        ('aluno', 'possui_condicao_saude', 'BOOLEAN'),
        ('aluno', 'condicoes_saude', 'TEXT'),
        ('aluno', 'alergias', 'TEXT'),
        ('aluno', 'medicamentos', 'TEXT'),
        ('aluno', 'contato_emergencia', 'VARCHAR(200)'),
        ('aluno', 'endereco', 'VARCHAR(300)'),
        ('aluno', 'responsavel', 'VARCHAR(150)'),
        ('aluno', 'altura', 'FLOAT'),
        ('aluno', 'peso', 'FLOAT'),
        ('aluno', 'genero', 'VARCHAR(20)'),
        ('aluno_atividades', None, None),
        ('atividade', None, None),
    ]
    
    for tabela, coluna, tipo in migracoes:
        if tabela in inspector.get_table_names():
            if coluna is None:
                continue
            colunas_existentes = [c['name'] for c in inspector.get_columns(tabela)]
            if coluna not in colunas_existentes:
                try:
                    with db.engine.connect() as conn:
                        conn.execute(text(f'ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}'))
                        conn.commit()
                    print(f'[MIGRACAO] Coluna {tabela}.{coluna} adicionada.')
                except Exception as e:
                    print(f'[MIGRACAO] Erro ao adicionar {tabela}.{coluna}: {e}')

# ── Inicialização automática do banco ──────────────────────────
try:
    with app.app_context():
        db.create_all()
        migrar_banco()
        criar_usuario_admin()
except Exception as _e:
    print(f'[AVISO] Não foi possível inicializar o banco agora: {_e}')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
