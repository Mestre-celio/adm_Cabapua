"""
Script para importar dados da planilha de anamnese para o sistema
Lê o arquivo Excel e atualiza os alunos existentes com:
- Email (se vazio)
- Telefone (se vazio)
- Responsavel (se vazio)
- Vinculo de atividade com base na modalidade escolhida
"""
import pandas as pd
from app import app, db, Aluno, Atividade


def importar_dados_anamnese(arquivo_excel):
    with app.app_context():
        print(" Lendo planilha Excel...")
        df = pd.read_excel(arquivo_excel)
        print(f"Planilha carregada: {len(df)} registros encontrados")

        colunas = {
            'nome':         '1. Nome completo',
            'data_nascimento': '2. Data de nascimento',
            'telefone':     '6. N\u00famero de celular ( whatsapp ) ',
            'email':        '7. Endere\u00e7o de e-mail ',
            'responsavel':  '9. Nome do respons\u00e1vel, Em caso de menor idade.',
            'modalidade':   '10. Qual a atividade escolhida? ',
        }

        alunos_atualizados = 0
        alunos_nao_encontrados = 0
        atividades_vinculadas = 0
        erros = []

        for idx, row in df.iterrows():
            try:
                nome = str(row.get(colunas['nome'], '')).strip()
                telefone = str(row.get(colunas['telefone'], '')).strip()
                email = str(row.get(colunas['email'], '')).strip()
                responsavel = str(row.get(colunas['responsavel'], '')).strip()
                modalidade = str(row.get(colunas['modalidade'], '')).strip()

                if not nome or nome.lower() == 'nan':
                    continue

                # Limpar "No answer" / vazios
                if telefone.lower() in ('no answer', 'nan', ''):
                    telefone = None
                if email.lower() in ('no answer', 'nan', ''):
                    email = None
                if responsavel.lower() in ('no answer', 'nan', ''):
                    responsavel = None
                if modalidade.lower() in ('no answer', 'nan', ''):
                    modalidade = None

                # Buscar aluno
                aluno = Aluno.query.filter(Aluno.nome.ilike(f'%{nome}%')).first()
                if not aluno:
                    partes = nome.split()
                    if len(partes) >= 2:
                        aluno = Aluno.query.filter(
                            Aluno.nome.ilike(f'%{partes[0]}%'),
                            Aluno.nome.ilike(f'%{partes[-1]}%')
                        ).first()

                if not aluno:
                    alunos_nao_encontrados += 1
                    print(f"  Aluno nao encontrado: {nome}")
                    continue

                atualizado = False

                if telefone and not aluno.telefone:
                    aluno.telefone = telefone
                    atualizado = True
                    print(f"  Telefone: {nome} -> {telefone}")

                if email and not aluno.email:
                    aluno.email = email
                    atualizado = True
                    print(f"  Email: {nome} -> {email}")

                if responsavel and not aluno.responsavel:
                    aluno.responsavel = responsavel
                    atualizado = True
                    print(f"  Responsavel: {nome} -> {responsavel}")

                if modalidade:
                    modalidade_clean = modalidade.strip()
                    atividade = Atividade.query.filter(
                        Atividade.nome.ilike(modalidade_clean),
                        Atividade.tipo == 'turma'
                    ).first()
                    if not atividade:
                        atividade = Atividade.query.filter(
                            Atividade.nome.ilike(f'%{modalidade_clean}%'),
                            Atividade.tipo == 'turma'
                        ).first()
                    if atividade and atividade not in aluno.atividades.all():
                        aluno.atividades.append(atividade)
                        atividades_vinculadas += 1
                        atualizado = True
                        print(f"  Atividade: {nome} -> {atividade.nome}")

                if atualizado:
                    alunos_atualizados += 1

            except Exception as e:
                erros.append(f"Linha {idx+2}: {e}")
                print(f"  Erro linha {idx+2}: {e}")

        db.session.commit()

        print(f"\n{'='*50}")
        print(f"RESUMO DA IMPORTACAO")
        print(f"{'='*50}")
        print(f"Alunos atualizados: {alunos_atualizados}")
        print(f"Atividades vinculadas: {atividades_vinculadas}")
        print(f"Alunos nao encontrados: {alunos_nao_encontrados}")
        print(f"Erros: {len(erros)}")
        if erros:
            for e in erros:
                print(f"  - {e}")


if __name__ == '__main__':
    arquivo = 'Anamnese e contrato aluno mensalista e app (3).xlsx'
    print("Iniciando importacao de dados da anamnese...")
    importar_dados_anamnese(arquivo)
    print("Importacao concluida!")
