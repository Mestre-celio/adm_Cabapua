"""
Blueprint para importação de alunos via upload de Excel (SurveyHeart)
"""
import os, re
from datetime import datetime, date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import pandas as pd

from app import db, Aluno

importacao_bp = Blueprint('importacao', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Mapeamento real do Excel exportado do SurveyHeart
C = {
    'nome':       '1. Nome completo',
    'nascimento': '2. Data de nascimento',
    'endereco':   '3. Endereço residencial: ',
    'telefone':   '4. Número de celular ( whatsapp ) ',
    'email':      '5. Endereço de e-mail ',
    'genero':     '6. Gênero',
    'resp_nome':  '7. Nome do responsável, Em caso de menor idade.',
    'modalidade': '8. Qual a atividade escolhida? ',
    'vicios':     '9. Possui vício, dependência ou uso constante?',
    'cirurgias':  '10. Já passou por alguma cirurgia? Se sim, qual ? ',
    'problemas':  '11. Algum problema de saúde congênito ou adquirido? Se sim qual? ',
    'obs_saude':  '12. Deseja deixar alguma observação sobre sua saúde, ou comentario importante? ',
    'pagamento':  '13. Melhor dia para pagamento: ',
    'apps':       '15. Apps . Está cláusula é obrigatória e específica aos usuários destes.',
}

def _limpar(raw):
    if raw is None or str(raw).strip().lower() in ('', 'nan', 'no answer', 'none', 'nat'):
        return ''
    return str(raw).strip()

def _tel(raw):
    t = _limpar(raw)
    if not t: return ''
    d = re.sub(r'\D', '', t).split('.')[0]
    if len(d) == 9: d = '11' + d
    elif len(d) == 13 and d.startswith('55'): d = d[2:]
    return d

def _data(raw):
    s = _limpar(raw)
    if not s: return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try: return datetime.strptime(s[:10], fmt).date()
        except ValueError: continue
    return None

def _saude(row):
    cond, aler, medi = [], [], []
    v = _limpar(row.get(C['vicios'], ''))
    if v and v.lower() not in ('não possuo vícios', 'nao', 'não', 'n'):
        if any(w in v.lower() for w in ('cigarro', 'tabag')): cond.append('Tabagista')
        if any(w in v.lower() for w in ('álcool', 'alcool')): cond.append('Etilista')
        if any(w in v.lower() for w in ('insulina', 'medicamento', 'humalog', 'bombinha')): medi.append(v)
    c = _limpar(row.get(C['cirurgias'], ''))
    if c and c.lower() not in ('não', 'nao', 'não.', 'nenhuma', 'n'): cond.append(f'Cirurgia: {c}')
    p = _limpar(row.get(C['problemas'], ''))
    if p and p.lower() not in ('não', 'nao', 'não.', 'nenhum', 'n'):
        (aler if 'alerg' in p.lower() else medi if any(w in p.lower() for w in ('insulina', 'humalog')) else cond).append(p)
    o = _limpar(row.get(C['obs_saude'], ''))
    if o and o.lower() not in ('não', 'nao', 'não.', 'nenhum', 'n'):
        (aler if 'alerg' in o.lower() else cond).append(o)
    return {'possui_condicao': len(cond) > 0, 'condicoes': ' | '.join(cond), 'alergias': ' | '.join(aler), 'medicamentos': ' | '.join(medi)}

def _tipo(apps_str):
    s = _limpar(apps_str).lower()
    if 'totalpass' in s: return 'totalpass'
    if 'wellhub' in s or 'gympass' in s: return 'wellhub'
    if 'gurupass' in s or 'guru' in s: return 'gurupass'
    return 'particular'

def _venc(pagamento_str):
    s = _limpar(pagamento_str)
    for d in ['05', '15', '20', '30']:
        if d in s: return int(d)
    return 5


@importacao_bp.route('/importar', methods=['GET', 'POST'])
@login_required
def importar_excel():
    if current_user.nivel != 'admin':
        flash('Apenas administradores podem importar dados!', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo enviado!', 'error')
            return redirect(request.url)

        arquivo = request.files['arquivo']
        if arquivo.filename == '':
            flash('Nenhum arquivo selecionado!', 'error')
            return redirect(request.url)

        ext = arquivo.filename.rsplit('.', 1)[1].lower() if '.' in arquivo.filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            flash('Formato não suportado. Use .xlsx ou .xls', 'error')
            return redirect(request.url)

        filepath = os.path.join(UPLOAD_FOLDER, 'upload_temp.xlsx')
        arquivo.save(filepath)

        try:
            df = pd.read_excel(filepath)
        except Exception as e:
            os.remove(filepath)
            flash(f'Erro ao ler o arquivo: {e}', 'error')
            return redirect(request.url)

        stats = {'importados': 0, 'atualizados': 0, 'erros': 0, 'menores': 0, 'com_saude': 0}
        hoje = date.today()

        for idx, row in df.iterrows():
            try:
                nome = _limpar(row.get(C['nome'], ''))
                if not nome: continue

                data_nasc = _data(row.get(C['nascimento']))
                idade = (hoje - data_nasc).days // 365 if data_nasc else None
                saude = _saude(row)
                tipo_aluno = _tipo(row.get(C['apps'], ''))
                venc_dia = _venc(row.get(C['pagamento'], ''))
                try: vencimento = date(hoje.year, hoje.month, venc_dia)
                except ValueError: vencimento = date(hoje.year, hoje.month, 5)

                aluno = Aluno.query.filter(db.func.lower(Aluno.nome) == nome.lower()).first()

                dados = {
                    'email': _limpar(row.get(C['email'])),
                    'telefone': _tel(row.get(C['telefone'])),
                    'data_nascimento': data_nasc,
                    'modalidade': _limpar(row.get(C['modalidade'])) or 'Não informada',
                    'tipo_aluno': tipo_aluno,
                    'matricula_app': f"APP_{idx+1:04d}" if tipo_aluno != 'particular' else None,
                    'vencimento': vencimento,
                    'endereco': _limpar(row.get(C['endereco'])),
                    'responsavel': _limpar(row.get(C['resp_nome'])),
                    'genero': _limpar(row.get(C['genero'])),
                    'possui_condicao_saude': saude['possui_condicao'],
                    'condicoes_saude': saude['condicoes'],
                    'alergias': saude['alergias'],
                    'medicamentos': saude['medicamentos'],
                }

                if aluno:
                    for k, v in dados.items():
                        if v: setattr(aluno, k, v)
                    stats['atualizados'] += 1
                else:
                    dados['nome'] = nome
                    dados['id_externo'] = f"SH_{idx+1:04d}"
                    dados['plano'] = 'Mensal'
                    dados['valor'] = 120.00 if tipo_aluno == 'particular' else 0.0
                    dados['status'] = 'ativo'
                    dados['data_matricula'] = hoje
                    db.session.add(Aluno(**dados))
                    stats['importados'] += 1

                if idade and idade < 18: stats['menores'] += 1
                if saude['possui_condicao']: stats['com_saude'] += 1

            except Exception as e:
                stats['erros'] += 1
                continue

        db.session.commit()
        os.remove(filepath)

        flash(
            f'Importação concluída! '
            f'{stats["importados"]} importados, '
            f'{stats["atualizados"]} atualizados, '
            f'{stats["menores"]} menores, '
            f'{stats["com_saude"]} com condições de saúde, '
            f'{stats["erros"]} erros.',
            'success'
        )
        return redirect(url_for('alunos'))

    return render_template('importar_excel.html')
