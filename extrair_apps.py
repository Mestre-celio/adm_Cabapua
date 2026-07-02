"""
Extrai emails e celulares dos alunos que concordaram com os apps
da planilha de anamnese, sem modificar o banco de dados.
"""
import pandas as pd
import csv

arquivo = 'Anamnese e contrato aluno mensalista e app (3).xlsx'
df = pd.read_excel(arquivo)

col_nome  = '1. Nome completo'
col_tel   = '6. N\u00famero de celular ( whatsapp ) '
col_email = '7. Endere\u00e7o de e-mail '
col_app   = df.columns[19]

app_rows = df[df[col_app].astype(str).str.strip() == 'Eu concordo']
print(f'Total na planilha: {len(df)}')
print(f'\"Eu concordo\" (apps): {len(app_rows)}')
print()

dados = []
for _, row in app_rows.iterrows():
    nome  = str(row[col_nome]).strip()
    tel   = str(row[col_tel]).strip()
    email = str(row[col_email]).strip()
    if tel.lower() in ('no answer', 'nan'):   tel = ''
    if email.lower() in ('no answer', 'nan'): email = ''
    dados.append({'nome': nome, 'telefone': tel, 'email': email})

with open('alunos_app_anamnese.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['Nome', 'Telefone', 'Email'])
    for d in dados:
        w.writerow([d['nome'], d['telefone'], d['email']])

print(f'{len(dados)} registros exportados para alunos_app_anamnese.csv')
print()
print('--- AMOSTRA (10 primeiros) ---')
for d in dados[:10]:
    print('  {0:35s} | {1:15s} | {2}'.format(d['nome'], d['telefone'], d['email']))
