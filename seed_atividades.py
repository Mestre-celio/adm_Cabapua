"""
Seed: popula atividades padrão (R$ 120/mês) + adiciona tipo 'turma'
Uso: python seed_atividades.py
"""
from app import app, db, Atividade

ATIVIDADES = [
    {'nome': 'Capoeira',     'valor_base': 120.0, 'descricao': 'Arte marcial brasileira'},
    {'nome': 'Jiu-Jitsu',    'valor_base': 120.0, 'descricao': 'Arte marcial japonesa'},
    {'nome': 'Muay Thai',    'valor_base': 120.0, 'descricao': 'Arte marcial tailandesa'},
    {'nome': 'Hapkido',      'valor_base': 120.0, 'descricao': 'Arte marcial coreana'},
    {'nome': 'Kickboxing',   'valor_base': 120.0, 'descricao': 'Luta em pé'},
    {'nome': 'Ninjutsu',     'valor_base': 120.0, 'descricao': 'Arte ninja'},
    {'nome': 'Kenjutsu',     'valor_base': 120.0, 'descricao': 'Esgrima japonesa'},
    {'nome': 'Boxe',         'valor_base': 120.0, 'descricao': 'Boxe'},
    {'nome': 'Grab Punch',   'valor_base': 120.0, 'descricao': 'Defesa pessoal'},
]

with app.app_context():
    db.create_all()
    criadas = 0
    for a in ATIVIDADES:
        if not Atividade.query.filter_by(nome=a['nome']).first():
            db.session.add(Atividade(**a))
            criadas += 1
    db.session.commit()
    total = Atividade.query.count()
    print(f'{criadas} atividades criadas. Total: {total}')
