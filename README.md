# 🥋 CTM Cabapuã — Sistema de Gestão

Sistema de gestão de academia de artes marciais. Desenvolvido com Python (Flask) e implantado no Netlify via Serverless Functions.

---

## ✅ Estrutura do Projeto

```
Planilha academia/
├── public/                      # Arquivos estáticos (publicados pelo Netlify)
│   ├── index.html               # Página inicial (landing page)
│   ├── styles.css               # CSS global com tema dark
│   ├── script.js                # JavaScript global com utilitários
│   └── robots.txt               # Configuração de crawlers
├── netlify/
│   └── functions/
│       └── api.js               # Função serverless principal (Node.js wrapper)
├── templates/                   # Templates HTML (Flask/Jinja2)
│   ├── login.html
│   ├── dashboard.html
│   ├── alunos.html
│   ├── aluno_form.html
│   ├── checkin.html
│   ├── relatorios.html
│   └── surveyheart_import.html
├── models/                      # Modelos de banco de dados
├── routes/                      # Rotas Flask
├── services/                    # Serviços (Google Calendar, SurveyHeart)
├── middleware/                  # Middlewares (autenticação)
├── app.py                       # Aplicação Flask principal
├── netlify.toml                 # Configuração do Netlify
├── requirements.txt             # Dependências Python
└── package.json                 # Dependências Node.js (para funções Netlify)
```

---

## 🚀 Deploy no Netlify

### Passo 1 — Commit das mudanças

```bash
git add public/
git add netlify.toml
git add README.md
git commit -m "fix: Add public directory for Netlify deployment"
git push
```

### Passo 2 — Verificar configurações no painel Netlify

1. Acesse o painel em [app.netlify.com](https://app.netlify.com)
2. Vá em **Site settings → Build & deploy**
3. Confirme:
   - **Publish directory**: `public`
   - **Functions directory**: `netlify/functions`
   - **Build command**: *(deixe vazio)*

### Passo 3 — Deploy automático

O Netlify detectará o push e fará o deploy automaticamente. ✅

---

## 🔧 Variáveis de Ambiente

Configure em **Site settings → Environment variables**:

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Chave secreta da sessão Flask |
| `DATABASE_URL` | URL do PostgreSQL (ex: `postgresql://user:pass@host:5432/db`) |
| `SURVEYHEART_API_TOKEN` | Token da API SurveyHeart |
| `GOOGLE_CLIENT_ID` | Client ID do Google OAuth2 |
| `GOOGLE_CLIENT_SECRET` | Client Secret do Google OAuth2 |
| `GOOGLE_REDIRECT_URI` | `https://seu-site.netlify.app/oauth2callback` |

---

## 🌐 URLs do Sistema

Após o deploy, acesse:

| Página | URL |
|---|---|
| Landing page | `https://seu-site.netlify.app/` |
| Login | `https://seu-site.netlify.app/.netlify/functions/api/login` |
| Dashboard | `https://seu-site.netlify.app/.netlify/functions/api/dashboard` |
| Alunos | `https://seu-site.netlify.app/.netlify/functions/api/alunos` |

---

## 🐛 Troubleshooting

### `Deploy directory 'public' does not exist`
✅ **Solução**: O diretório `public/` já foi criado com os arquivos necessários.

### `Functions not found`
✅ **Solução**: Verifique se `netlify.toml` está correto e o arquivo `netlify/functions/api.js` existe.

### `Database connection failed`
✅ **Solução**: Configure `DATABASE_URL` com um PostgreSQL externo (Neon, Supabase, Railway).

### Sessões perdidas entre requests
✅ **Solução**: Configure um session store externo (banco PostgreSQL ou Redis).

---

## 📞 Suporte

- Documentação Netlify: [docs.netlify.com](https://docs.netlify.com/)
- Documentação Flask: [flask.palletsprojects.com](https://flask.palletsprojects.com/)
