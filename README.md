# PMO App

Aplicação web em Flask para gestão de portfólio de projetos (PMO), com foco em:

- Cadastro e acompanhamento de projetos estratégicos.
- Dashboard executivo com indicadores de criticidade.
- Mapa de criticidade para priorização.
- Análise inteligente por IA com fallback local.

## Visão geral

O projeto foi construído para ser simples de operar e fácil de evoluir:

- Backend em `Flask` com rotas server-side.
- Banco PostgreSQL com criação/evolução automática de estrutura.
- Frontend via templates Jinja (`templates/`) + CSS global (`static/style.css`).
- Integração de IA desacoplada no serviço `services/ia_service.py`.
- Pipeline CI no GitHub Actions para validação automática.

## Stack técnica

- Python 3.12 (compatível com 3.10+ na prática)
- Flask
- psycopg2-binary (PostgreSQL)
- openai SDK (usado para OpenAI, OpenRouter, Gemini via base_url, e Ollama)
- python-dotenv
- unittest (testes nativos)

## Estrutura do projeto

```text
pmo_app/
├─ app.py                         # Entrypoint Flask e rotas
├─ config.py                      # Configuração central (.env)
├─ db.py                          # Conexão e estrutura do banco
├─ database.sql                   # Script de referência do schema
├─ services/
│  └─ ia_service.py               # Integração com IA + fallback local
├─ templates/                     # Telas Jinja
├─ static/
│  ├─ style.css                   # Estilo global
│  └─ logo-exercito.png
├─ tests/
│  └─ test_health.py              # Smoke tests
├─ .github/workflows/
│  └─ workflowprod.yaml           # CI de push/PR/manual
├─ requirements.txt
└─ .env.example
```

## Requisitos

- Python 3.10+ (recomendado 3.12)
- PostgreSQL ativo
- Git

## Configuração local (passo a passo)

1. Clonar o repositório.
2. Criar e ativar ambiente virtual.
3. Instalar dependências.
4. Criar `.env` baseado em `.env.example`.
5. Garantir que o PostgreSQL esteja disponível.
6. Subir aplicação.

### Comandos (Windows PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

A aplicação sobe em `http://127.0.0.1:5000` por padrão.

## Variáveis de ambiente

Exemplo base disponível em `.env.example`.

### App

- `APP_SECRET_KEY`: chave da sessão Flask.
- `FLASK_DEBUG`: `1` para debug local, `0` para produção.

### Banco de dados

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_SCHEMA`
- `DB_CONNECT_TIMEOUT`

### IA

- `AI_PROVIDER`: `openai`, `openrouter`, `gemini` ou `ollama`.
- OpenAI: `OPENAI_API_KEY`, `OPENAI_MODEL`
- OpenRouter: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`
- Gemini: `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `GEMINI_MODEL`
- Ollama: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`

## Como o banco é preparado

Ao iniciar a aplicação, `ensure_database_structure()` é executado em `app.py`.

Esse processo:

- Cria schema se não existir.
- Cria tabelas base (`usuarios`, `projetos`, `historico_projetos`).
- Aplica evolução de colunas com `ALTER TABLE ... IF NOT EXISTS`.
- Cria índices para consultas frequentes.
- Cria trigger de `updated_at` em `projetos`.

Você pode usar `database.sql` como referência ou bootstrap manual.

## Fluxo funcional principal

1. Login em `/` valida usuário no PostgreSQL.
2. Rotas protegidas por `login_required`.
3. Dashboard consolida métricas do portfólio.
4. Gestão de projetos permite criar, listar, filtrar, detalhar e excluir.
5. Mapa de criticidade classifica projetos por risco/prioridade.
6. Tela de análise chama IA e monta recomendações executivas.

## Integração com IA (arquitetura)

Arquivo chave: `services/ia_service.py`.

### Estratégia

- Seleciona provider por `AI_PROVIDER`.
- Instancia cliente `OpenAI(...)` com `base_url` conforme provider.
- Monta prompt estruturado para análise de projeto.
- Espera retorno em JSON.
- Normaliza saída para payload padrão de UI.

### Resiliência

Se houver erro de cota, autenticação, conexão, status ou parse inválido:

- O serviço aplica fallback local (`_analise_local_payload`).
- A interface continua funcional com análise heurística.

Esse desenho evita indisponibilidade da feature por falha externa.

## Endpoints principais

- `GET /health`: healthcheck e provider ativo.
- `GET|POST /`: login.
- `GET /logout`: encerra sessão.
- `GET /dashboard`: indicadores executivos.
- `GET /projetos`: lista e filtros.
- `GET|POST /projetos/novo`: cadastro.
- `GET /projetos/<id>`: detalhes.
- `POST /projetos/excluir/<id>`: exclusão.
- `GET /mapa-criticidade`: visão de criticidade.
- `GET /portfolio`: consolidado do portfólio.
- `GET /analisar/<id>`: análise inteligente do projeto.

## Testes

Atualmente há smoke tests em `tests/test_health.py`:

- Validação sintática de arquivos Python críticos.
- Verificação da existência da rota `/health`.
- Verificação de template essencial.

### Rodar localmente

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

## CI/CD (GitHub Actions)

Workflow: `.github/workflows/workflowprod.yaml`.

Dispara em:

- `push` (todas as branches)
- `pull_request` (todas as branches)
- `workflow_dispatch` (manual)

Pipeline:

1. Checkout
2. Setup Python 3.12
3. Instala dependências
4. Executa testes com `unittest`

## Segurança e boas práticas

- Sessão com `HTTPOnly` e `SameSite=Lax`.
- SQL com parâmetros (`%s`) para reduzir risco de SQL injection.
- Validações de dados de projeto no backend.

Ponto de atenção atual:

- A autenticação consulta usuário por email/senha em texto.  
  Recomendado evoluir para hash de senha (`bcrypt`/`argon2`) e política de rotação.

## Troubleshooting rápido

- Erro de conexão no banco:
  Verifique `DB_*` no `.env` e se o PostgreSQL está ativo.

- IA não responde:
  Verifique `AI_PROVIDER` e chave correspondente (`*_API_KEY`).

- Workflow não roda no GitHub:
  Confirme arquivo em `.github/workflows/` e se Actions está habilitado no repositório.

## Próximas evoluções recomendadas

1. Migrar autenticação para senha com hash e camada de autorização por perfil.
2. Adicionar testes de integração das rotas principais.
3. Introduzir migrations versionadas (ex.: Alembic).
4. Instrumentar logs estruturados e métricas de observabilidade.
5. Padronizar contrato de resposta da IA com validação schema-first.

---

Se você está entrando agora no projeto, comece por esta ordem:

1. `config.py`
2. `db.py`
3. `app.py`
4. `services/ia_service.py`
5. `templates/`
