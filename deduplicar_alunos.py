"""
Script para remover alunos duplicados do banco de dados
Uso: python deduplicar_alunos.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app, db, Aluno
from sqlalchemy import func

def deduplicar():
    with app.app_context():
        duplicados = db.session.query(
            Aluno.nome, func.count(Aluno.id).label('count')
        ).group_by(Aluno.nome).having(func.count(Aluno.id) > 1).all()
        
        if not duplicados:
            print("Nenhum aluno duplicado encontrado!")
            return
        
        print(f"\nEncontrados {len(duplicados)} nome(s) duplicado(s):\n")
        total = 0
        
        for nome, count in duplicados:
            alunos = Aluno.query.filter_by(nome=nome).order_by(Aluno.id).all()
            manter = alunos[0]
            print(f"[{nome}] {count} registros -> mantendo ID {manter.id}")
            for aluno in alunos[1:]:
                db.session.delete(aluno)
                total += 1
        
        db.session.commit()
        print(f"\nRemovidos {total} registro(s) duplicado(s)!")

if __name__ == '__main__':
    deduplicar()
