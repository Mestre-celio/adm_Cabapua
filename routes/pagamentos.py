"""Blueprint de Pagamentos - CTM Cabapua"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from datetime import datetime, date
from app import db, Aluno, Pagamento

pagamentos_bp = Blueprint('pagamentos', __name__, url_prefix='/pagamentos')

try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    from datetime import timedelta as relativedelta
    class relativedelta:
        def __init__(self, months=0):
            self.months = months

def calcular_vencimento(data_pagamento, tipo_plano):
    if tipo_plano == 'mensal':
        return data_pagamento + relativedelta(months=1)
    elif tipo_plano == 'trimestral':
        return data_pagamento + relativedelta(months=3)
    elif tipo_plano == 'semestral':
        return data_pagamento + relativedelta(months=6)
    return data_pagamento + relativedelta(months=1)

def gerar_referencia(data_pagamento, tipo_plano):
    if tipo_plano == 'mensal':
        return data_pagamento.strftime('%m/%Y')
    elif tipo_plano == 'trimestral':
        fim = data_pagamento + relativedelta(months=2)
        return f"{data_pagamento.strftime('%m/%Y')} a {fim.strftime('%m/%Y')}"
    elif tipo_plano == 'semestral':
        fim = data_pagamento + relativedelta(months=5)
        return f"{data_pagamento.strftime('%m/%Y')} a {fim.strftime('%m/%Y')}"
    return data_pagamento.strftime('%m/%Y')

@pagamentos_bp.route('/')
@login_required
def lista_pagamentos():
    status_filtro = request.args.get('status', 'todos')
    mes = request.args.get('mes', '')
    query = Pagamento.query
    if status_filtro != 'todos':
        query = query.filter_by(status=status_filtro)
    if mes:
        query = query.filter(db.extract('month', Pagamento.data_pagamento) == int(mes))
    pagamentos = query.order_by(Pagamento.data_pagamento.desc()).all()
    
    hoje = date.today()
    total_mes = db.session.query(db.func.sum(Pagamento.valor))\
        .filter(db.extract('month', Pagamento.data_pagamento) == hoje.month,
                db.extract('year', Pagamento.data_pagamento) == hoje.year,
                Pagamento.status == 'pago').scalar() or 0
    total_ano = db.session.query(db.func.sum(Pagamento.valor))\
        .filter(db.extract('year', Pagamento.data_pagamento) == hoje.year,
                Pagamento.status == 'pago').scalar() or 0
    
    return render_template('pagamentos_lista.html', pagamentos=pagamentos,
                         total_mes=total_mes, total_ano=total_ano,
                         status=status_filtro, mes=mes)

@pagamentos_bp.route('/novo', methods=['GET', 'POST'])
@login_required
def novo_pagamento():
    if request.method == 'POST':
        aluno_id = int(request.form['aluno_id'])
        valor = float(request.form['valor'])
        tipo_plano = request.form['tipo_plano']
        forma_pagamento = request.form['forma_pagamento']
        data_pgto = datetime.strptime(request.form['data_pagamento'], '%Y-%m-%d').date()
        observacoes = request.form.get('observacoes', '')
        data_venc = calcular_vencimento(data_pgto, tipo_plano)
        referencia = gerar_referencia(data_pgto, tipo_plano)
        
        pagamento = Pagamento(
            aluno_id=aluno_id, valor=valor, data_pagamento=data_pgto,
            data_vencimento=data_venc, tipo_plano=tipo_plano,
            forma_pagamento=forma_pagamento, status='pago',
            observacoes=observacoes, referencia=referencia
        )
        db.session.add(pagamento)
        
        aluno = Aluno.query.get(aluno_id)
        aluno.vencimento = data_venc
        aluno.status = 'ativo'
        db.session.commit()
        
        flash(f'Pagamento de R$ {valor:.2f} registrado!', 'success')
        return redirect(url_for('pagamentos.lista_pagamentos'))
    
    alunos = Aluno.query.filter_by(status='ativo').order_by(Aluno.nome).all()
    return render_template('pagamento_form.html', alunos=alunos, pagamento=None, today=date.today())

@pagamentos_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar_pagamento(id):
    pagamento = Pagamento.query.get_or_404(id)
    if request.method == 'POST':
        pagamento.valor = float(request.form['valor'])
        pagamento.tipo_plano = request.form['tipo_plano']
        pagamento.forma_pagamento = request.form['forma_pagamento']
        pagamento.data_pagamento = datetime.strptime(request.form['data_pagamento'], '%Y-%m-%d').date()
        pagamento.status = request.form['status']
        pagamento.observacoes = request.form.get('observacoes', '')
        pagamento.data_vencimento = calcular_vencimento(pagamento.data_pagamento, pagamento.tipo_plano)
        
        aluno = Aluno.query.get(pagamento.aluno_id)
        aluno.vencimento = pagamento.data_vencimento
        db.session.commit()
        flash('Pagamento atualizado!', 'success')
        return redirect(url_for('pagamentos.lista_pagamentos'))
    
    alunos = Aluno.query.filter_by(status='ativo').order_by(Aluno.nome).all()
    return render_template('pagamento_form.html', alunos=alunos, pagamento=pagamento, today=date.today())

@pagamentos_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_pagamento(id):
    pagamento = Pagamento.query.get_or_404(id)
    db.session.delete(pagamento)
    db.session.commit()
    flash('Pagamento excluído!', 'success')
    return redirect(url_for('pagamentos.lista_pagamentos'))

@pagamentos_bp.route('/aluno/<int:aluno_id>')
@login_required
def historico_aluno(aluno_id):
    aluno = Aluno.query.get_or_404(aluno_id)
    pagamentos = Pagamento.query.filter_by(aluno_id=aluno_id)\
        .order_by(Pagamento.data_pagamento.desc()).all()
    total_pago = sum(p.valor for p in pagamentos if p.status == 'pago')
    return render_template('historico_pagamentos.html', aluno=aluno,
                         pagamentos=pagamentos, total_pago=total_pago)

@pagamentos_bp.route('/relatorio')
@login_required
def relatorio_financeiro():
    hoje = date.today()
    planos_stats = db.session.query(
        Pagamento.tipo_plano, db.func.count(Pagamento.id), db.func.sum(Pagamento.valor)
    ).filter(Pagamento.status == 'pago').group_by(Pagamento.tipo_plano).all()
    
    formas_stats = db.session.query(
        Pagamento.forma_pagamento, db.func.count(Pagamento.id), db.func.sum(Pagamento.valor)
    ).filter(Pagamento.status == 'pago').group_by(Pagamento.forma_pagamento).all()
    
    meses_stats = []
    for i in range(11, -1, -1):
        mes_data = date(hoje.year, hoje.month, 1) - relativedelta(months=i)
        total = db.session.query(db.func.sum(Pagamento.valor))\
            .filter(db.extract('month', Pagamento.data_pagamento) == mes_data.month,
                    db.extract('year', Pagamento.data_pagamento) == mes_data.year,
                    Pagamento.status == 'pago').scalar() or 0
        meses_stats.append({'mes': mes_data.strftime('%m/%Y'), 'total': total})
    
    return render_template('relatorio_financeiro.html',
                         planos_stats=planos_stats, formas_stats=formas_stats,
                         meses_stats=meses_stats)
