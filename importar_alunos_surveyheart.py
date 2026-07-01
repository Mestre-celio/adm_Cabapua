"""
Script de Importação — SurveyHeart → Banco de Dados CTM Cabapuã
Lê o Excel exportado do SurveyHeart e cadastra os alunos no banco.

Uso:
    python importar_alunos_surveyheart.py
    python importar_alunos_surveyheart.py --dry-run    # só lista, não salva
"""

import sys
import os
import argparse
from datetime import datetime, date

# Garante que o diretório do projeto está no PATH antes de importar app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pandas as pd
except ImportError:
    print("[ERRO] pandas não instalado. Execute: pip install pandas openpyxl")
    sys.exit(1)

from app import app, db, Aluno

# ── Caminho da planilha ───────────────────────────────────────────────────────
EXCEL_PATH = os.path.join(
    os.path.expanduser('~'),
    'Downloads',
    'Anamnese e contrato aluno mensalista e app (2).xlsx'
)

# ── Mapeamento de colunas (ajuste conforme o cabeçalho real do Excel) ─────────
COLUNAS = {
    'nome':         '1. Nome completo',
    'nascimento':   '2. Data de nascimento',
    'cpf':          '3. CPF',
    'rg':           '4. RG',
    'endereco':     '5. Endereço completo',
    'telefone':     '6. Número de celular ( whatsapp )',
    'email':        '7. Endereço de e-mail',
    'resp_nome':    '8. Nome do responsável (para menores de 18 anos)',
    'resp_tel':     '9. Telefone do responsável',
    'modalidade':   '10. Qual a atividade escolhida?',
    'vicios':       '11. Possui vicio, dependencia ou uso constante?',
    'cirurgias':    '12. Ja passou por alguma cirurgia?',
    'problemas':    '13. Algum problema de saude congenito ou adquirido?',
    'emergencia':   '14. Em caso de emergencia',
    'obs_saude':    '15. Deseja deixar alguma observacao sobre sua saude',
    'pagamento':    '16. Melhor dia para pagamento:',
    'apps':         '18. Apps . Está cláusula é obrigatória...',
}

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
