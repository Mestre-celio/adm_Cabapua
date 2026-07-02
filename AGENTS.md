# CTM Cabapuã — Contexto do Projeto

## Stack
Flask + SQLAlchemy + PostgreSQL (Render) + Jinja2 templates. Sem frontend framework.

## Deploy
`https://adm-cabapua.onrender.com` — Render via GitHub (`main` branch).
Deploy hook: `https://api.render.com/deploy/srv-d922t24vikkc73er506g?key=E5I4F4cmKm4`

## Credenciais
- Admin: `admin` / `admin123`
- Professor: `professor` / `prof123`

## Estrutura
- `app.py` (~1000 linhas) — app Flask, models, rotas, blueprints
- `routes/` — whatsapp, pagamentos, importacao (upload Excel)
- `templates/` — Jinja2 (sem base.html, cada template é completo)
- `importar_alunos_surveyheart.py` — script local de importação
- `requirements.txt` — pandas, openpyxl, etc.
- `runtime.txt` — `python-3.11.9`
- `.gitignore` — inclui `adm_Cabapua/`

## Models
- **Usuario**: username, password_hash, nome, nivel (admin/professor/recepcao), email, google_id, primeiro_acesso
- **Aluno**: nome, email, telefone, data_nascimento, tipo_aluno, modalidade (legado), graduacao, plano, status, endereco, responsavel, dados_saude (condicoes, alergias, medicamentos), altura, peso, genero, + atividades (N:N via `aluno_atividades`)
- **Atividade**: nome, descricao, valor_base, ativa
- **CheckIn**: aluno_id, data_checkin, origem
- **Pagamento**: aluno_id, valor, data_pagamento, tipo_plano, status

## Recém implementado (commit 95e46d9)
1. Modelo `Atividade` + tabela associativa `aluno_atividades`
2. Aluno pode ter múltiplas atividades (N:N)
3. Cálculo automático: 1ª atividade (maior valor) cheia, demais 50% desconto
4. CRUD de atividades: `/atividades`, `/atividade/nova`, `/atividade/<id>/editar`, `/atividade/<id>/excluir`
5. Dashboard financeiro: `/dashboard/financeiro` (admin only) — projeções 1/3/6 meses
6. Form de aluno com checkboxes de atividades (substituiu modalidade única)
7. Rota de teste: `/test-save` (requer login)
8. Google Sheets removido (blueprint, rotas, templates)
9. Rotas `/aluno/novo` e `/aluno/<id>/editar` com `try/except`, `or None`, `remove()` em vez de `clear()`
10. Seed script: `seed_atividades.py` — 9 atividades a R$ 120 (Capoeira, Jiu-Jitsu, Muay Thai, Hapkido, Kickboxing, Ninjutsu, Kenjutsu, Boxe, Grab Punch)
11. Tipos de aluno: `turma` (mensal por atividade), `particular` (R$ 70/h), `wellhub`/`totalpass`/`gurupass` (app)
12. `calcular_mensalidade()` condicional por `tipo_aluno`

## Problemas conhecidos
- `adm_Cabapua/` é um sub-repositório git incluído acidentalmente; `git rm --cached -f` + `.gitignore` já configurado
- Pandas/openpyxl sem versão fixa no requirements (para compatibilidade com Python 3.14 no Render)
- Lazy import `import pandas as pd` dentro da função em `routes/importacao.py`

## Próximos passos possíveis
- Terminar implementação de altura/peso no form
- Melhorar dashboard do professor
- Adicionar relatórios financeiros em PDF
