"""
Importa alunos app da planilha de anamnese:
- Alunos existentes: atualiza tipo_aluno para 'turma', email e telefone
- Novos alunos: cria com tipo_aluno='turma', email e telefone
"""
import csv
from datetime import date
from app import app, db, Aluno


def importar():
    with app.app_context():
        with open('alunos_app_anamnese.csv', encoding='utf-8') as f:
            reader = list(csv.DictReader(f))

        atualizados = 0
        criados = 0
        erros = []

        for row in reader:
            try:
                nome = row['Nome'].strip()
                tel = row['Telefone'].strip() or None
                email = row['Email'].strip() or None

                aluno = Aluno.query.filter(Aluno.nome.ilike(nome)).first()
                if not aluno:
                    partes = nome.split()
                    if len(partes) >= 2:
                        aluno = Aluno.query.filter(
                            Aluno.nome.ilike('%' + partes[0] + '%'),
                            Aluno.nome.ilike('%' + partes[-1] + '%')
                        ).first()

                if aluno:
                    aluno.tipo_aluno = 'turma'
                    if email and not aluno.email:
                        aluno.email = email
                    if tel and not aluno.telefone:
                        aluno.telefone = tel
                    atualizados += 1
                else:
                    aluno = Aluno(
                        nome=nome,
                        email=email,
                        telefone=tel,
                        tipo_aluno='turma',
                        status='ativo',
                        data_matricula=date.today()
                    )
                    db.session.add(aluno)
                    db.session.flush()
                    criados += 1
                    print(f'  Criado: {nome}')

            except Exception as e:
                erros.append(f'{nome}: {e}')
                db.session.rollback()

        db.session.commit()
        print(f'\nAtualizados: {atualizados}')
        print(f'Criados: {criados}')
        print(f'Erros: {len(erros)}')
        for e in erros:
            print(f'  - {e}')


if __name__ == '__main__':
    print('Importando alunos app...')
    importar()
    print('Concluido!')
