"""
Script de Importação — SurveyHeart → Banco de Dados CTM Cabapuã
Lê o Excel exportado do SurveyHeart e cadastra os alunos no banco.
Com mapeamento completo de saúde, responsáveis e modalidades.

Uso:
    python importar_alunos_surveyheart.py
    python importar_alunos_surveyheart.py --dry-run    # só lista, não salva
    python importar_alunos_surveyheart.py --arquivo CAMINHO
"""

import sys
import os
import re
import argparse
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pandas as pd
except ImportError:
    print("[ERRO] pandas não instalado. Execute: pip install pandas openpyxl")
    sys.exit(1)

from app import app, db, Aluno

# ── Mapeamento de colunas do SurveyHeart ──────────────────────────────────
COLUNAS = {
    'nome':          '1. Nome completo',
    'nascimento':    '2. Data de nascimento',
    'cpf':           '3. CPF',
    'rg':            '4. RG',
    'endereco':      '5. Endereço residencial:',
    'telefone':      '6. Número de celular ( whatsapp )',
    'email':         '7. Endereço de e-mail',
    'genero':        '8. Gênero',
    'resp_nome':     '9. Nome do responsável, Em caso de menor idade.',
    'modalidade':    '10. Qual a atividade escolhida?',
    'vicios':        '11. Possui vício, dependência ou uso constante?',
    'cirurgias':     '12. Já passou por alguma cirurgia? Se sim, qual ?',
    'problemas':     '13. Algum problema de saúde congênito ou adquirido? Se sim qual?',
    'emergencia':    '14. Em caso de emergência, um nome e número de contato:',
    'obs_saude':     '15. Deseja deixar alguma observação sobre sua saúde, ou comentario importante?',
    'pagamento':     '16. Melhor dia para pagamento:',
    'apps':          '18. Apps . Está cláusula é obrigatória e específica aos usuários destes.',
}

# ── Utilitários ──────────────────────────────────────────────────────────
def limpar_str(raw):
    if raw is None or str(raw).strip().lower() in ('', 'nan', 'no answer', 'none', 'nat'):
        return ''
    return str(raw).strip()

def formatar_telefone(raw):
    tel = limpar_str(raw)
    if not tel:
        return ''
    digitos = re.sub(r'\D', '', tel).split('.')[0]
    if len(digitos) == 9:
        digitos = '11' + digitos
    elif len(digitos) == 13 and digitos.startswith('55'):
        digitos = digitos[2:]
    return digitos

def converter_data(raw):
    s = limpar_str(raw)
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None

def calcular_idade(dt_nasc):
    if not dt_nasc:
        return None
    hoje = date.today()
    return hoje.year - dt_nasc.year - ((hoje.month, hoje.day) < (dt_nasc.month, dt_nasc.day))

# ── Análise de saúde ─────────────────────────────────────────────────────
def analisar_saude(row):
    condicoes, alergias, medicamentos = [], [], []

    # Campo 11 – Vícios
    vicios = limpar_str(row.get(COLUNAS['vicios'], ''))
    if vicios and vicios.lower() not in ('não possuo vícios', 'nao', 'não', 'n'):
        if any(w in vicios.lower() for w in ('cigarro', 'tabag')):
            condicoes.append('Tabagista')
        if any(w in vicios.lower() for w in ('álcool', 'alcool', 'etil')):
            condicoes.append('Etilista')
        if any(w in vicios.lower() for w in ('insulina', 'medicamento', 'humalog')):
            medicamentos.append(vicios)

    # Campo 12 – Cirurgias
    cirurgias = limpar_str(row.get(COLUNAS['cirurgias'], ''))
    if cirurgias and cirurgias.lower() not in ('não', 'nao', 'não.', 'nenhuma', 'n', 'nenhum'):
        condicoes.append(f'Cirurgia: {cirurgias}')

    # Campo 13 – Problemas de saúde
    problemas = limpar_str(row.get(COLUNAS['problemas'], ''))
    if problemas and problemas.lower() not in ('não', 'nao', 'não.', 'nenhum', 'n'):
        if 'alerg' in problemas.lower():
            alergias.append(problemas)
        elif any(w in problemas.lower() for w in ('insulina', 'humalog')):
            medicamentos.append(problemas)
        else:
            condicoes.append(problemas)

    # Campo 15 – Observações
    obs = limpar_str(row.get(COLUNAS['obs_saude'], ''))
    if obs and obs.lower() not in ('não', 'nao', 'não.', 'nenhum', 'n'):
        if 'alerg' in obs.lower():
            alergias.append(obs)
        else:
            condicoes.append(obs)

    return {
        'possui_condicao': len(condicoes) > 0,
        'condicoes':       ' | '.join(condicoes),
        'alergias':        ' | '.join(alergias),
        'medicamentos':    ' | '.join(medicamentos),
    }

# ── Detecção de tipo e vencimento ────────────────────────────────────────
def detectar_tipo_aluno(apps_str):
    s = limpar_str(apps_str).lower()
    if 'totalpass' in s:
        return 'totalpass'
    if 'wellhub' in s or 'gympass' in s:
        return 'wellhub'
    if 'gurupass' in s or 'guru' in s:
        return 'gurupass'
    return 'particular'

def detectar_vencimento(pagamento_str):
    s = limpar_str(pagamento_str)
    for dia in ['05', '15', '20', '30']:
        if dia in s:
            return int(dia)
    if '5' in s and ('útil' in s or 'util' in s):
        return 5
    return 5

# ── Importação principal ─────────────────────────────────────────────────
def importar(arquivo=None, dry_run=False):
    if not arquivo:
        # Busca automática na pasta Downloads
        downloads = os.path.expanduser('~/Downloads')
        candidatos = [f for f in os.listdir(downloads) if f.startswith('Anamnese') and f.endswith('.xlsx')]
        if candidatos:
            arquivo = os.path.join(downloads, sorted(candidatos)[-1])
        else:
            # Tenta na pasta local
            candidatos = [f for f in os.listdir('.') if f.startswith('Anamnese') and f.endswith('.xlsx')]
            if not candidatos:
                print("[ERRO] Nenhum arquivo 'Anamnese ... .xlsx' encontrado em ~/Downloads ou na pasta atual.")
                print("   Especifique com: --arquivo CAMINHO")
                sys.exit(1)
            arquivo = candidatos[0]

    if not os.path.exists(arquivo):
        print(f"[ERRO] Arquivo não encontrado: {arquivo}")
        sys.exit(1)

    print(f"[OK] Lendo: {arquivo}")
    df = pd.read_excel(arquivo)
    print(f"[INFO] {len(df)} registros | Colunas: {list(df.columns)[:5]}...\n")

    stats = {'importados': 0, 'atualizados': 0, 'existentes': 0, 'erros': 0, 'sem_nome': 0}
    menores = 0
    com_saude = 0

    with app.app_context():
        db.create_all()

        for idx, row in df.iterrows():
            try:
                nome = limpar_str(row.get(COLUNAS['nome'], ''))
                if not nome:
                    stats['sem_nome'] += 1
                    continue

                data_nasc = converter_data(row.get(COLUNAS['nascimento']))
                telefone  = formatar_telefone(row.get(COLUNAS['telefone']))
                email     = limpar_str(row.get(COLUNAS['email']))
                endereco  = limpar_str(row.get(COLUNAS['endereco']))
                responsavel = limpar_str(row.get(COLUNAS['resp_nome']))
                modalidade = limpar_str(row.get(COLUNAS['modalidade'])) or 'Não informada'
                apps_str   = limpar_str(row.get(COLUNAS['apps'], ''))

                tipo_aluno = detectar_tipo_aluno(apps_str)
                venc_dia   = detectar_vencimento(limpar_str(row.get(COLUNAS['pagamento'], '')))

                hoje = date.today()
                try:
                    vencimento = date(hoje.year, hoje.month, venc_dia)
                except ValueError:
                    vencimento = date(hoje.year, hoje.month, 5)

                matricula_app = f"APP_{idx+1:04d}" if tipo_aluno != 'particular' else None
                saude = analisar_saude(row)
                contato_emergencia = limpar_str(row.get(COLUNAS['emergencia'], ''))

                # Verifica duplicata
                aluno_existente = Aluno.query.filter(db.func.lower(Aluno.nome) == nome.lower()).first()

                if aluno_existente:
                    aluno_existente.email = email or aluno_existente.email
                    aluno_existente.telefone = telefone or aluno_existente.telefone
                    aluno_existente.data_nascimento = data_nasc or aluno_existente.data_nascimento
                    aluno_existente.modalidade = modalidade if modalidade != 'Não informada' else aluno_existente.modalidade
                    aluno_existente.tipo_aluno = tipo_aluno
                    aluno_existente.matricula_app = matricula_app
                    aluno_existente.endereco = endereco or aluno_existente.endereco
                    aluno_existente.responsavel = responsavel or aluno_existente.responsavel
                    if saude['possui_condicao']:
                        aluno_existente.possui_condicao_saude = True
                        aluno_existente.condicoes_saude = saude['condicoes'] or aluno_existente.condicoes_saude
                        aluno_existente.alergias = saude['alergias'] or aluno_existente.alergias
                        aluno_existente.medicamentos = saude['medicamentos'] or aluno_existente.medicamentos
                    aluno_existente.contato_emergencia = contato_emergencia or aluno_existente.contato_emergencia

                    stats['atualizados'] += 1
                    print(f"  [ATUALIZADO] {nome}")
                    continue

                if dry_run:
                    stats['importados'] += 1
                    flags = []
                    if saude['possui_condicao']:
                        flags.append('SAUDE')
                    if data_nasc and calcular_idade(data_nasc) and calcular_idade(data_nasc) < 18:
                        flags.append('MENOR')
                    tag = f" [{', '.join(flags)}]" if flags else ""
                    print(f"  [DRY-RUN] {nome} | {modalidade} | {tipo_aluno}{tag}")
                    continue

                aluno = Aluno(
                    id_externo           = f"SH_{idx+1:04d}",
                    nome                 = nome,
                    email                = email,
                    telefone             = telefone,
                    data_nascimento      = data_nasc,
                    tipo_aluno           = tipo_aluno,
                    matricula_app        = matricula_app,
                    modalidade           = modalidade,
                    plano                = 'Mensal',
                    valor                = 120.00 if tipo_aluno == 'particular' else 0.0,
                    vencimento           = vencimento,
                    status               = 'ativo',
                    data_matricula       = hoje,
                    endereco             = endereco,
                    responsavel          = responsavel,
                    possui_condicao_saude = saude['possui_condicao'],
                    condicoes_saude      = saude['condicoes'],
                    alergias             = saude['alergias'],
                    medicamentos         = saude['medicamentos'],
                    contato_emergencia   = contato_emergencia,
                )

                db.session.add(aluno)
                stats['importados'] += 1

                if data_nasc and calcular_idade(data_nasc) and calcular_idade(data_nasc) < 18:
                    menores += 1
                if saude['possui_condicao']:
                    com_saude += 1

                print(f"  [OK] {nome} | {modalidade} | {tipo_aluno}")

            except Exception as e:
                print(f"  [ERRO] Linha {idx+1}: {e}")
                stats['erros'] += 1
                continue

        if not dry_run and stats['importados'] > 0:
            db.session.commit()
            print(f"\n[SALVO] Dados gravados no banco.")

    # Resumo
    print("\n" + "=" * 50)
    print(f"Importados   : {stats['importados']}")
    print(f"Atualizados  : {stats['atualizados']}")
    print(f"Já existiam  : {stats['existentes']}")
    print(f"Sem nome     : {stats['sem_nome']}")
    print(f"Erros        : {stats['erros']}")
    print(f"Menores      : {menores}")
    print(f"Com condição : {com_saude}")
    print("=" * 50)
    if dry_run:
        print("[INFO] Modo DRY-RUN — nenhum dado foi salvo.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Importar alunos do SurveyHeart')
    parser.add_argument('--dry-run', action='store_true', help='Apenas lista sem salvar')
    parser.add_argument('--arquivo', help='Caminho do arquivo .xlsx')
    args = parser.parse_args()
    importar(arquivo=args.arquivo, dry_run=args.dry_run)

# ── Detecta tipo de aluno ─────────────────────────────────────────────────────
def detectar_tipo_aluno(apps_str: str) -> str:
    s = str(apps_str).lower()
    if 'totalpass' in s:
        return 'totalpass'
    if 'wellhub' in s or 'gympass' in s:
        return 'wellhub'
    if 'gurupass' in s or 'guru' in s:
        return 'gurupass'
    return 'particular'

# ── Extrai dia de vencimento ──────────────────────────────────────────────────
def detectar_vencimento(pagamento_str: str) -> int:
    s = str(pagamento_str)
    for dia in ['05', '15', '20', '30']:
        if dia in s:
            return int(dia)
    if '5' in s and ('útil' in s or 'util' in s):
        return 5   # 5° dia útil → assume dia 5
    return 5       # padrão

# ── Limpa string de telefone ──────────────────────────────────────────────────
def limpar_telefone(raw) -> str:
    if raw is None or str(raw).strip() in ('', 'nan', 'No answer'):
        return ''
    digitos = ''.join(filter(str.isdigit, str(raw).split('.')[0]))
    return digitos if digitos else ''

# ── Converte data ─────────────────────────────────────────────────────────────
def converter_data(raw) -> date | None:
    if raw is None or str(raw).strip() in ('', 'nan', 'No answer', 'NaT'):
        return None
    s = str(raw).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None

# ── Importação principal ──────────────────────────────────────────────────────
def importar(dry_run=False):
    if not os.path.exists(EXCEL_PATH):
        print(f"[ERRO] Arquivo não encontrado: {EXCEL_PATH}")
        print("   Verifique o caminho e o nome do arquivo.")
        sys.exit(1)

    print(f"[OK] Lendo: {EXCEL_PATH}")
    df = pd.read_excel(EXCEL_PATH)

    print(f"[INFO] {len(df)} linhas encontradas na planilha")
    print(f"[INFO] Colunas: {list(df.columns)}\n")

    stats = {'importados': 0, 'existentes': 0, 'erros': 0, 'sem_nome': 0}

    with app.app_context():
        # Garante que o banco existe
        db.create_all()

        for idx, row in df.iterrows():
            try:
                # Nome é obrigatório
                nome = str(row.get(COLUNAS['nome'], '')).strip()
                if not nome or nome.lower() in ('no answer', 'nan', ''):
                    stats['sem_nome'] += 1
                    continue

                # Verifica duplicata por nome
                existe = Aluno.query.filter(
                    db.func.lower(Aluno.nome) == nome.lower()
                ).first()
                if existe:
                    print(f"  [EXISTE] {nome}")
                    stats['existentes'] += 1
                    continue

                # Extrai campos
                telefone   = limpar_telefone(row.get(COLUNAS['telefone']))
                email      = str(row.get(COLUNAS['email'], '')).strip()
                email      = email if email.lower() not in ('no answer', 'nan') else ''
                modalidade = str(row.get(COLUNAS['modalidade'], '')).strip()
                modalidade = modalidade if modalidade.lower() not in ('no answer', 'nan', '') else 'Não informada'
                pagamento  = str(row.get(COLUNAS['pagamento'], '')).strip()
                apps_str   = str(row.get(COLUNAS['apps'], '')).strip()

                tipo_aluno  = detectar_tipo_aluno(apps_str)
                venc_dia    = detectar_vencimento(pagamento)
                data_nasc   = converter_data(row.get(COLUNAS['nascimento']))

                # Define vencimento para este mês
                hoje = date.today()
                try:
                    vencimento = date(hoje.year, hoje.month, venc_dia)
                except ValueError:
                    vencimento = date(hoje.year, hoje.month, 5)

                # Matrícula para alunos de app
                matricula_app = f"APP_{idx+1:04d}" if tipo_aluno != 'particular' else None

                if dry_run:
                    print(f"  [DRY-RUN] {nome} | {modalidade} | {tipo_aluno} | tel:{telefone}")
                    stats['importados'] += 1
                    continue

                # Extrai dados de saude
                vicios_str      = str(row.get(COLUNAS.get('vicios', ''), '')).strip()
                cirurgias_str   = str(row.get(COLUNAS.get('cirurgias', ''), '')).strip()
                problemas_str   = str(row.get(COLUNAS.get('problemas', ''), '')).strip()
                emergencia_str  = str(row.get(COLUNAS.get('emergencia', ''), '')).strip()
                obs_saude_str   = str(row.get(COLUNAS.get('obs_saude', ''), '')).strip()

                condicoes = []
                if cirurgias_str.lower() not in ('no answer', 'nan', '', 'não', 'nao'):
                    condicoes.append(f"Cirurgias: {cirurgias_str}")
                if problemas_str.lower() not in ('no answer', 'nan', '', 'não', 'nao', 'nenhum'):
                    condicoes.append(f"Problemas: {problemas_str}")
                possui_condicao = len(condicoes) > 0

                alergias = obs_saude_str if 'alergia' in obs_saude_str.lower() or 'alergico' in obs_saude_str.lower() else ''
                medicamentos = vicios_str if vicios_str.lower() not in ('no answer', 'nan', '', 'não possuo vícios', 'nao') else ''

                aluno = Aluno(
                    id_externo    = f"SH_{idx+1:04d}",
                    nome          = nome,
                    email         = email,
                    telefone      = telefone,
                    data_nascimento = data_nasc,
                    tipo_aluno    = tipo_aluno,
                    matricula_app = matricula_app,
                    modalidade    = modalidade,
                    plano         = 'Mensal',
                    valor         = 120.00 if tipo_aluno == 'particular' else 0.0,
                    vencimento    = vencimento,
                    status        = 'ativo',
                    endereco      = str(row.get(COLUNAS.get('endereco', ''), '')).strip() if str(row.get(COLUNAS.get('endereco', ''), '')).strip().lower() not in ('no answer', 'nan', '') else '',
                    responsavel   = str(row.get(COLUNAS.get('resp_nome', ''), '')).strip() if str(row.get(COLUNAS.get('resp_nome', ''), '')).strip().lower() not in ('no answer', 'nan', '') else '',
                    possui_condicao_saude = possui_condicao,
                    condicoes_saude = ' | '.join(condicoes),
                    alergias      = alergias,
                    medicamentos  = medicamentos,
                    contato_emergencia = emergencia_str if emergencia_str.lower() not in ('no answer', 'nan', '') else '',
                )

                db.session.add(aluno)
                stats['importados'] += 1
                print(f"  [OK] {nome} | {modalidade} | {tipo_aluno}")

            except Exception as e:
                print(f"  [ERRO] Linha {idx}: {e}")
                stats['erros'] += 1
                continue

        if not dry_run:
            db.session.commit()
            print(f"[SALVO] Dados gravados no banco.")

    # Resumo
    print("\n" + "─" * 50)
    print(f"Importados  : {stats['importados']}")
    print(f"Ja existiam : {stats['existentes']}")
    print(f"Sem nome    : {stats['sem_nome']}")
    print(f"Erros       : {stats['erros']}")
    print("─" * 50)
    if dry_run:
        print("[INFO] Modo DRY-RUN — nenhum dado foi salvo.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Importar alunos do SurveyHeart Excel')
    parser.add_argument('--dry-run', action='store_true', help='Apenas lista sem salvar')
    args = parser.parse_args()
    importar(dry_run=args.dry_run)
