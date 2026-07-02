"""
Script para importar dados da planilha Excel para o sistema
Atualiza automaticamente: telefone, email, responsavel e atividade
"""

import pandas as pd
from app import app, db, Aluno, Atividade


def limpar_telefone(telefone):
    if not telefone or pd.isna(telefone) or str(telefone).lower() in ['no answer', 'nan', '']:
        return None
    tel = ''.join(filter(str.isdigit, str(telefone)))
    if len(tel) > 10 and tel.startswith('0'):
        tel = tel[1:]
    return tel if tel else None


def limpar_email(email):
    if not email or pd.isna(email) or str(email).lower() in ['no answer', 'nan', '']:
        return None
    email = str(email).strip().lower()
    return email if '@' in email and '.' in email else None


def normalizar_nome(nome):
    if not nome or pd.isna(nome):
        return None
    return str(nome).strip().title()


def buscar_aluno(nome):
    if not nome:
        return None
    aluno = Aluno.query.filter(Aluno.nome.ilike(f'%{nome}%')).first()
    if aluno:
        return aluno
    partes = nome.split()
    if len(partes) >= 2:
        aluno = Aluno.query.filter(
            Aluno.nome.ilike(f'%{partes[0]}%'),
            Aluno.nome.ilike(f'%{partes[-1]}%')
        ).first()
    return aluno


def buscar_atividade(modalidade):
    if not modalidade:
        return None
    mod = str(modalidade).strip().lower()
    mapeamento = {
        'muay thai': 'Muay Thai',
        'jiu-jitsu': 'Jiu-Jitsu',
        'jiu jitsu': 'Jiu-Jitsu',
        'capoeira': 'Capoeira',
        'hapkido': 'Hapkido',
        'kickboxing': 'Kickboxing',
        'ninjutsu': 'Ninjutsu',
        'kenjutsu': 'Kenjutsu',
        'boxe': 'Boxe',
        'grab punch': 'Grab Punch',
        'defesa pessoal': 'Grab Punch',
    }
    for chave, nome_atv in mapeamento.items():
        if chave in mod:
            atv = Atividade.query.filter(
                Atividade.nome.ilike(f'%{nome_atv}%'),
                Atividade.tipo == 'turma'
            ).first()
            if atv:
                return atv
    return Atividade.query.filter(
        Atividade.nome.ilike(f'%{mod}%'),
        Atividade.tipo == 'turma'
    ).first()


def importar_dados(arquivo_excel):
    with app.app_context():
        print("=" * 60)
        print("INICIANDO IMPORTACAO DE DADOS")
        print("=" * 60)

        try:
            df = pd.read_excel(arquivo_excel)
            print(f"Planilha carregada: {len(df)} registros")
        except Exception as e:
            print(f"Erro ao ler planilha: {e}")
            return

        atualizados = 0
        nao_encontrados = 0
        erros = 0

        for idx, row in df.iterrows():
            try:
                nome_completo = normalizar_nome(row.get('1. Nome completo'))
                telefone = limpar_telefone(row.get('6. N\u00famero de celular ( whatsapp ) '))
                email = limpar_email(row.get('7. Endere\u00e7o de e-mail '))
                responsavel = normalizar_nome(row.get('9. Nome do respons\u00e1vel, Em caso de menor idade.'))
                modalidade = row.get('10. Qual a atividade escolhida? ')

                if not nome_completo:
                    continue

                aluno = buscar_aluno(nome_completo)
                if not aluno:
                    print(f"  [{idx+1}] Aluno nao encontrado: {nome_completo}")
                    nao_encontrados += 1
                    continue

                atualizado = False

                if telefone and (not aluno.telefone or aluno.telefone != telefone):
                    print(f"  [{idx+1}] {nome_completo}: Telefone -> {telefone}")
                    aluno.telefone = telefone
                    atualizado = True

                if email and (not aluno.email or aluno.email != email):
                    print(f"  [{idx+1}] {nome_completo}: Email -> {email}")
                    aluno.email = email
                    atualizado = True

                if responsavel and str(responsavel).lower() not in ['no answer', 'nan', '']:
                    if not aluno.responsavel or str(aluno.responsavel).lower() in ['no answer', 'nan', '']:
                        print(f"  [{idx+1}] {nome_completo}: Responsavel -> {responsavel}")
                        aluno.responsavel = responsavel
                        atualizado = True

                if modalidade and str(modalidade).lower() not in ['no answer', 'nan', '']:
                    atividade = buscar_atividade(modalidade)
                    if atividade and atividade not in aluno.atividades.all():
                        aluno.atividades.append(atividade)
                        print(f"  [{idx+1}] {nome_completo}: Atividade -> {atividade.nome}")
                        atualizado = True
                    elif not atividade:
                        print(f"  [{idx+1}] {nome_completo}: Atividade nao encontrada: {modalidade}")

                if atualizado:
                    atualizados += 1

            except Exception as e:
                print(f"  [{idx+1}] Erro: {e}")
                erros += 1

        try:
            db.session.commit()
            print("\n" + "=" * 60)
            print("IMPORTACAO CONCLUIDA")
            print("=" * 60)
            print(f"Alunos atualizados: {atualizados}")
            print(f"Nao encontrados: {nao_encontrados}")
            print(f"Erros: {erros}")
            print("=" * 60)
        except Exception as e:
            db.session.rollback()
            print(f"\nErro ao salvar: {e}")


if __name__ == '__main__':
    arquivo = 'Anamnese e contrato aluno mensalista e app (3).xlsx'
    importar_dados(arquivo)
