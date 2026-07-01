"""
Rotas WhatsApp — CTM Cabapuã
Usa wa.me links para abrir o WhatsApp Web/App com mensagem pré-preenchida.
Não requer API paga — funciona com qualquer conta WhatsApp.
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
import urllib.parse
from datetime import date

from app import db, Aluno

whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/whatsapp')

# Número da academia (sem formatação, com DDI)
NUMERO_ACADEMIA = '5511965962262'


def formatar_telefone(telefone_raw: str) -> str:
    """
    Normaliza o telefone para o formato wa.me: 55 + DDD + número.
    Trata casos com/sem DDD, com/sem +55, com hífen, ponto ou espaço.
    """
    if not telefone_raw:
        return ''

    # Remove tudo que não é dígito
    digitos = ''.join(filter(str.isdigit, str(telefone_raw)))

    # Remove .0 de floats vindos do pandas (ex: "11987654321.0")
    if digitos.endswith('0') and len(digitos) > 11:
        digitos = digitos[:-2] if digitos[-2] == '.' else digitos

    # Adiciona DDI 55 se necessário
    if digitos.startswith('55') and len(digitos) >= 12:
        return digitos          # já tem DDI
    if len(digitos) == 11:
        return '55' + digitos   # DDD + 9 dígitos
    if len(digitos) == 10:
        return '5511' + digitos  # sem DDD → assume SP (11)
    return '55' + digitos        # fallback


def gerar_mensagem(tipo: str, nome_aluno: str) -> str:
    """Retorna a mensagem pré-formatada conforme o tipo."""
    primeiro_nome = nome_aluno.split()[0] if nome_aluno else 'Aluno'

    templates = {
        'boas_vindas': (
            f"Olá {primeiro_nome}! 🥋\n\n"
            "Seja bem-vindo(a) ao *Centro de Treinamento Marcial Cabapuã Brasil*!\n\n"
            "Estamos muito felizes em ter você conosco. Qualquer dúvida sobre horários, "
            "modalidades ou pagamentos, estamos à disposição!\n\n"
            "OSS! 🙏"
        ),
        'aniversario': (
            f"Olá {primeiro_nome}! 🎂🎉\n\n"
            "Toda a equipe do *CTM Cabapuã* deseja um feliz aniversário!\n\n"
            "Que este novo ciclo seja repleto de conquistas dentro e fora do tatame. "
            "Muitos treinos pela frente!\n\n"
            "OSS! 🙏"
        ),
        'cobranca': (
            f"Olá {primeiro_nome}! 💳\n\n"
            "Passando para lembrar que sua *mensalidade no CTM Cabapuã* está próxima do vencimento.\n\n"
            "Para mais informações sobre formas de pagamento, entre em contato conosco.\n\n"
            "OSS! 🙏"
        ),
        'vencido': (
            f"Olá {primeiro_nome}! ⚠️\n\n"
            "Notamos que sua *mensalidade no CTM Cabapuã* está em aberto.\n\n"
            "Por favor, entre em contato para regularizar sua situação e continuar treinando!\n\n"
            "OSS! 🙏"
        ),
        'falta': (
            f"Olá {primeiro_nome}! 😊\n\n"
            "Sentimos sua falta nos treinos! O *CTM Cabapuã* está esperando por você.\n\n"
            "Bora voltar para o tatame? 🥋\n\n"
            "OSS! 🙏"
        ),
        'checkin': (
            f"Olá {primeiro_nome}! ✅\n\n"
            "Parabéns pela dedicação! Seu check-in no *CTM Cabapuã* foi registrado hoje.\n\n"
            "Continue assim! Consistência é a chave do campeão. 💪\n\n"
            "OSS! 🙏"
        ),
    }
    return templates.get(tipo, f"Olá {primeiro_nome}!\n\nMensagem do CTM Cabapuã.\n\nOSS! 🙏")


def montar_url_whatsapp(telefone: str, mensagem: str) -> str:
    tel = formatar_telefone(telefone)
    msg = urllib.parse.quote(mensagem)
    return f"https://wa.me/{tel}?text={msg}" if tel else '#'


# ─── Rotas ────────────────────────────────────────────────────────────────────

@whatsapp_bp.route('/')
@login_required
def central():
    """Central WhatsApp — página principal."""
    total_ativos = Aluno.query.filter_by(status='ativo').count()
    mes_atual = date.today().month
    aniversariantes = Aluno.query.filter(
        db.extract('month', Aluno.data_nascimento) == mes_atual,
        Aluno.status == 'ativo'
    ).count()

    return render_template('whatsapp/central.html',
                           numero_academia=NUMERO_ACADEMIA,
                           total_ativos=total_ativos,
                           aniversariantes=aniversariantes)


@whatsapp_bp.route('/enviar/<int:aluno_id>', methods=['GET', 'POST'])
@login_required
def enviar_individual(aluno_id):
    """Envia mensagem para um aluno específico."""
    aluno = Aluno.query.get_or_404(aluno_id)

    if request.method == 'POST':
        mensagem = request.form.get('mensagem', '').strip()
        if not mensagem:
            flash('Digite uma mensagem antes de enviar.', 'warning')
            return redirect(request.url)

        url = montar_url_whatsapp(aluno.telefone, mensagem)
        if url == '#':
            flash(f'Telefone inválido para {aluno.nome}.', 'danger')
            return redirect(request.url)

        return redirect(url)

    # Templates pré-prontos
    templates = {k: gerar_mensagem(k, aluno.nome)
                 for k in ['boas_vindas', 'aniversario', 'cobranca', 'vencido', 'falta', 'checkin']}

    return render_template('whatsapp/enviar.html',
                           aluno=aluno,
                           templates=templates,
                           numero_academia=NUMERO_ACADEMIA)


@whatsapp_bp.route('/massa', methods=['GET', 'POST'])
@login_required
def em_massa():
    """Prepara mensagens em lote para envio."""
    modalidades = db.session.query(Aluno.modalidade).distinct().filter(
        Aluno.modalidade.isnot(None)
    ).order_by(Aluno.modalidade).all()
    modalidades = [m[0] for m in modalidades if m[0]]

    resultados = []

    if request.method == 'POST':
        tipo_msg   = request.form.get('tipo_mensagem', 'boas_vindas')
        modalidade = request.form.get('modalidade', 'todos')
        status_filtro = request.form.get('status_filtro', 'ativo')
        mensagem_custom = request.form.get('mensagem_custom', '').strip()

        query = Aluno.query
        if status_filtro != 'todos':
            query = query.filter_by(status=status_filtro)
        if modalidade != 'todos':
            query = query.filter_by(modalidade=modalidade)

        alunos = query.order_by(Aluno.nome).all()

        for aluno in alunos:
            if not aluno.telefone:
                continue
            msg = mensagem_custom if mensagem_custom else gerar_mensagem(tipo_msg, aluno.nome)
            url = montar_url_whatsapp(aluno.telefone, msg)
            resultados.append({
                'aluno': aluno,
                'url': url,
                'mensagem': msg,
                'telefone_fmt': formatar_telefone(aluno.telefone)
            })

        flash(f'{len(resultados)} link(s) WhatsApp gerado(s). Clique em cada botão para enviar.', 'success')

    return render_template('whatsapp/massa.html',
                           modalidades=modalidades,
                           resultados=resultados,
                           numero_academia=NUMERO_ACADEMIA)


@whatsapp_bp.route('/aniversariantes')
@login_required
def aniversariantes():
    """Lista aniversariantes do mês com links WhatsApp prontos."""
    mes = request.args.get('mes', date.today().month, type=int)
    alunos = Aluno.query.filter(
        db.extract('month', Aluno.data_nascimento) == mes,
        Aluno.status == 'ativo'
    ).order_by(
        db.extract('day', Aluno.data_nascimento)
    ).all()

    links = []
    for aluno in alunos:
        msg = gerar_mensagem('aniversario', aluno.nome)
        links.append({
            'aluno': aluno,
            'url': montar_url_whatsapp(aluno.telefone, msg),
            'dia': aluno.data_nascimento.day if aluno.data_nascimento else '?'
        })

    meses = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
             'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

    return render_template('whatsapp/aniversariantes.html',
                           links=links,
                           mes=mes,
                           mes_nome=meses[mes - 1],
                           meses=meses,
                           numero_academia=NUMERO_ACADEMIA)
