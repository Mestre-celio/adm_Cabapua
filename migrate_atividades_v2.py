"""
Migração v2: adiciona tipo às atividades existentes + cria novas atividades com tipo.
Uso: python migrate_atividades_v2.py
"""
from app import app, db, Atividade
from sqlalchemy import inspect, text

# Atividades existentes (originalmente turma) + novas atividades com tipo
ATIVIDADES = [
    # Turma (mensal R$ 120)
    {'nome': 'Capoeira',     'valor_base': 120.0, 'tipo': 'turma', 'descricao': 'Arte marcial brasileira'},
    {'nome': 'Jiu-Jitsu',    'valor_base': 120.0, 'tipo': 'turma', 'descricao': 'Arte marcial japonesa'},
    {'nome': 'Muay Thai',    'valor_base': 120.0, 'tipo': 'turma', 'descricao': 'Arte marcial tailandesa'},
    {'nome': 'Hapkido',      'valor_base': 120.0, 'tipo': 'turma', 'descricao': 'Arte marcial coreana'},
    {'nome': 'Kickboxing',   'valor_base': 120.0, 'tipo': 'turma', 'descricao': 'Luta em pé'},
    {'nome': 'Ninjutsu',     'valor_base': 120.0, 'tipo': 'turma', 'descricao': 'Arte ninja'},
    {'nome': 'Kenjutsu',     'valor_base': 120.0, 'tipo': 'turma', 'descricao': 'Esgrima japonesa'},
    {'nome': 'Boxe',         'valor_base': 120.0, 'tipo': 'turma', 'descricao': 'Boxe'},
    {'nome': 'Grab Punch',   'valor_base': 120.0, 'tipo': 'turma', 'descricao': 'Defesa pessoal'},
    # Particular (R$ 70/h)
    {'nome': 'Kung Fu',      'valor_base': 70.0,  'tipo': 'particular', 'descricao': 'Arte marcial chinesa'},
    {'nome': 'Defesa Pessoal', 'valor_base': 70.0, 'tipo': 'particular', 'descricao': 'Técnicas de defesa pessoal'},
]

with app.app_context():
    # Migrar coluna tipo se não existir
    inspector = inspect(db.engine)
    if 'atividade' in inspector.get_table_names():
        colunas = [c['name'] for c in inspector.get_columns('atividade')]
        if 'tipo' not in colunas:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE atividade ADD COLUMN tipo VARCHAR(30) DEFAULT 'turma'"))
                conn.commit()
            print('[MIGRACAO] Coluna atividade.tipo adicionada.')

        # Migrar colunas do aluno
        colunas_aluno = [c['name'] for c in inspector.get_columns('aluno')]
        for col, tipo in [('modalidade_particular', 'VARCHAR(100)'), ('parentesco_familiar', 'VARCHAR(30)'), ('familiar_id', 'INTEGER')]:
            if col not in colunas_aluno:
                with db.engine.connect() as conn:
                    conn.execute(text(f'ALTER TABLE aluno ADD COLUMN {col} {tipo}'))
                    conn.commit()
                print(f'[MIGRACAO] Coluna aluno.{col} adicionada.')

        # Migrar coluna horas_aula em aluno_atividades
        if 'aluno_atividades' in inspector.get_table_names():
            colunas_assoc = [c['name'] for c in inspector.get_columns('aluno_atividades')]
            if 'horas_aula' not in colunas_assoc:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE aluno_atividades ADD COLUMN horas_aula FLOAT'))
                    conn.commit()
                print('[MIGRACAO] Coluna aluno_atividades.horas_aula adicionada.')

    # Atualizar tipo das atividades existentes que não têm tipo
    for a in Atividade.query.filter(Atividade.tipo.is_(None)).all():
        a.tipo = 'turma'
        print(f'[MIGRACAO] Atividade "{a.nome}" recebeu tipo=turma.')

    # Criar novas atividades
    db.session.commit()
    criadas = 0
    for dados in ATIVIDADES:
        if not Atividade.query.filter_by(nome=dados['nome']).first():
            db.session.add(Atividade(**dados))
            criadas += 1
    db.session.commit()
    total = Atividade.query.count()
    print(f'{criadas} novas atividades criadas. Total: {total}')
