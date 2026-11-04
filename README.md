# Liga eFootball

*Projeto independente, sem fins lucrativos, criado para gerenciar uma liga de eFootball entre amigos.*

Sistema web de **liga personalizada de eFootball para um grupo de amigos**. O jogo só oferece
torneios mata-mata; este site faz o papel de campeonato de pontos corridos: sorteia os confrontos
em dois turnos, permite agendar datas, lançar placares manualmente, contestar resultados e mantém
a classificação sempre recalculada a partir das partidas encerradas.

Não existe integração com API do jogo: as partidas acontecem no eFootball e os resultados são
digitados no site.

---

## Sumário

- [Visão geral](#visão-geral)
- [Transparência e escopo](#transparência-e-escopo)
- [Stack](#stack)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Como rodar localmente](#como-rodar-localmente)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Contas e dados de demonstração](#contas-e-dados-de-demonstração)
- [Admin em produção](#admin-em-produção)
- [Segurança da sessão (cookies HttpOnly + CSRF)](#segurança-da-sessão-cookies-httponly--csrf)
- [Email e recuperação de senha](#email-e-recuperação-de-senha)
- [Serviço único e mesma origem](#serviço-único-e-mesma-origem)
- [Hardening de produção](#hardening-de-produção)
- [Nome personalizado da liga](#nome-personalizado-da-liga)
- [Geração de confrontos](#geração-de-confrontos)
- [Resultados, contestação e W.O.](#resultados-contestação-e-wo)
- [Trava sequencial de rodadas](#trava-sequencial-de-rodadas)
- [Classificação e desempate](#classificação-e-desempate)
- [Modelo de permissões](#modelo-de-permissões)
- [Padrão de mensagens](#padrão-de-mensagens)
- [API](#api)
- [Frontend](#frontend)
- [Testes](#testes)
- [Deploy](#deploy)
- [Decisões tomadas nesta alteração](#decisões-tomadas-nesta-alteração)
- [Limitações e próximos passos](#limitações-e-próximos-passos)
- [Aviso legal](#aviso-legal)

---

## Visão geral

1. **Cadastro e login** com email único, nome da pessoa, nome do time e senha forte. A sessão é
   mantida em **cookies HttpOnly**, com access curto, refresh rotativo e blacklist.
2. **Confirmação de identidade via `GET /api/auth/me/`**: o front não guarda token nenhum, ele
   pergunta ao servidor quem é o usuário logado.
3. **Geração de confrontos** por round-robin (método do círculo), com folga (`BYE`) para número
   ímpar, dois turnos com mando invertido e semente auditável.
4. **Trava sequencial de rodadas configurável**: por padrão só se lança resultado na rodada N
   quando a N-1 estiver encerrada; o admin pode alternar para **duas rodadas simultâneas**, em
   pares fixos (1 e 2, 3 e 4...). A verificação é sempre feita no backend, dentro da mesma
   transação da escrita.
5. **W.O. pelo admin** para não deixar a liga travada por um jogador ausente (3 a 0 para quem
   compareceu, com badge na interface e registro de auditoria).
6. **Contestação em 48h**, correção pelo admin e auditoria completa em `MatchResultLog`.
7. **Nome da liga personalizável** pelo admin, refletido no cabeçalho, no `document.title`, na
   página inicial e na classificação, com log de auditoria.
8. **Classificação derivada** de partidas `FINISHED`/`CONTESTED`, com desempate por pontos,
   vitórias, saldo de gols, gols pró e nome do time.
9. **Autorização real no backend** (permissões DRF + checagem repetida nos serviços) e front
   apenas como UX.
10. **Mensagens amigáveis** `{code, message}` em pt-BR, sempre exibidas em toast.
11. **Recuperação de senha por email** via API da Brevo (ou SMTP genérico), link de uso único,
    token de 1 hora e invalidação das sessões antigas.
12. **Remoção de jogador pelo admin**, mantendo a conta de login e preservando o histórico quando
    já existem resultados.

Requisitos não funcionais: configuração por variáveis de ambiente, um único serviço em produção,
PostgreSQL como banco suportado, mobile-first e nenhuma regra crítica no frontend.

---

## Transparência e escopo

- O repositório é público para quem quiser conhecer o código e as decisões técnicas.
- O projeto não possui nenhuma lógica financeira: sem pagamentos, cobranças, inscrição paga,
  premiação em dinheiro, anúncios ou doações.
- Os dados coletados são apenas os necessários para a liga — email, nome e nome do time, além da
  senha (armazenada somente como hash) e dos dados esportivos (confrontos, placares e auditoria).
  Eles não são vendidos nem compartilhados.
- Nomes de times são texto livre digitado pelos próprios jogadores. O projeto não usa logos,
  escudos ou imagens oficiais do eFootball/Konami nem de clubes reais.

---

## Stack

**Backend (`/backend`)**

- Python 3.12, Django 5.2, Django REST Framework 3.18
- PostgreSQL via `psycopg` + `dj-database-url` (SQLite só como fallback de desenvolvimento)
- `djangorestframework-simplejwt` (+ `token_blacklist`), `whitenoise`, `gunicorn`, `python-dotenv`
- pytest + pytest-django (dev)

**Frontend (`/frontend`)**

- React 18 + Vite 6, React Router 7, axios (`withCredentials`, CSRF e refresh single-flight)
- CSS próprio, mobile-first, tema escuro e claro — sem biblioteca de UI

---

## Estrutura do projeto

```
.
├── backend/
│   ├── config/               # settings, urls (API + SPA + /django-admin/), wsgi/asgi
│   ├── core/                 # mensagens, erros, CSRF, autenticação por cookie, headers,
│   │                         # permissões, idempotência, throttles, email, view do SPA
│   ├── accounts/             # User por email, cookies de sessão, login/refresh/logout/csrf/me,
│   │                         # recuperação de senha
│   ├── templates/            # emails transacionais (reset de senha)
│   ├── league/
│   │   ├── models.py         # League, Participant, Round, Match, MatchResultLog, LeagueChangeLog
│   │   ├── services/         # fixtures, results, rounds (trava), standings, league_name
│   │   ├── serializers.py / views.py / urls.py / admin.py
│   │   └── management/commands/seed_demo.py
│   ├── tests/                # suíte pytest-django
│   ├── requirements.txt / requirements-dev.txt
│   └── manage.py
├── frontend/
│   ├── src/api/              # cliente axios (cookies + CSRF + refresh) e endpoints
│   ├── src/context/          # Auth (descoberta de sessão) e Toasts
│   ├── src/lib/              # cookies, limpeza de tokens legados, formatação
│   ├── src/components/       # Layout, MatchCard, tabela, diálogos, rotas protegidas
│   └── src/pages/            # Classificação, Rodadas, Login, Cadastro, Perfil, Admin,
│                             # Esqueci a senha e Redefinir senha
├── build.sh                  # build único: deps + frontend + collectstatic + migrate
├── start.sh                  # sync_admins + gunicorn (Render/Railway/Docker)
├── Procfile
├── render.yaml               # um serviço web + PostgreSQL externo (Neon)
├── Dockerfile                # imagem de produção (Node build + Python runtime)
├── docker-entrypoint.sh      # migrate (Neon) + start.sh
├── docker-compose.yml        # app externo (Neon) + PostgreSQL local opcional
├── .dockerignore
├── .env.example
└── README.md
```

---

## Como rodar localmente

### 1. Pré-requisitos

Python **3.12**, Node.js **20+**, PostgreSQL **15+** (SQLite funciona só como conveniência).

### 2. Banco de dados

```bash
docker compose up -d db          # PostgreSQL na porta 5433 do host
```

A porta padrão do compose é **5433** porque 5432 costuma estar ocupada por um PostgreSQL local.
Alternativa com banco já instalado:

```bash
createdb liga_efootball
# DATABASE_URL=postgres://postgres:postgres@localhost:5432/liga_efootball
```

### 3. Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cd ..
cp .env.example .env             # ajuste DATABASE_URL, SECRET_KEY e DEBUG
cd backend
python manage.py migrate
python manage.py seed_demo       # opcional: liga demo com 8 jogadores
python manage.py runserver
```

API em `http://localhost:8000/api/`; health check em `http://localhost:8000/api/health/`.
O Django admin fica em **`/django-admin/`** (a rota `/admin` é o painel React).

### 4. Frontend (desenvolvimento)

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

O Vite faz **proxy de `/api`, `/django-admin` e `/static` para `http://localhost:8000`**, então o
navegador conversa com uma única origem e os cookies de sessão funcionam sem CORS.
Para apontar para outro backend: `VITE_PROXY_TARGET=http://localhost:8001 npm run dev`.

### 5. Build de produção local (opcional)

```bash
./build.sh                       # instala deps, builda o frontend, collectstatic e migrate
python backend/manage.py runserver
```

Com o build em `frontend/dist`, o Django serve a SPA e a API na mesma origem.

### 6. Testes

```bash
cd backend
source ../.venv/bin/activate
pytest
```

Os testes usam o `DATABASE_URL` configurado e criam um banco de teste temporário. Sem
`DATABASE_URL`, o fallback SQLite permite rodar a suíte, mas o teste de concorrência da trava de
rodadas é mais bem exercitado no PostgreSQL.

---

## Variáveis de ambiente

Arquivo único na raiz (`.env`), carregado pelo backend. O frontend não precisa de `.env` (usa
`/api` e o proxy do Vite).

| Variável | Obrigatória | Descrição |
| --- | --- | --- |
| `SECRET_KEY` | **sim em produção** | Chave do Django/JWT. Com `DEBUG=False` o app **falha ao subir** sem ela. |
| `DEBUG` | sim | `True` local, `False` em produção. |
| `DATABASE_URL` | recomendada | URL PostgreSQL. No Render/Neon use a string **pooled** (`-pooler`, `sslmode=require`). Vazia → SQLite local. |
| `DIRECT_DATABASE_URL` | não | Endpoint **direto** do Neon, usado apenas por `migrate` (recomendado pela Neon). Se vazio, a migração usa `DATABASE_URL`. |
| `DATABASE_CONN_MAX_AGE` | não | Segundos de reuso da conexão (padrão 300, abaixo do scale-to-zero de ~5 min do Neon). |
| `DATABASE_SSL_REQUIRE` | não | Padrão `True` para hosts remotos e `False` para localhost. Exige TLS no PostgreSQL. |
| `DATABASE_CONNECT_TIMEOUT` | não | Timeout de conexão em segundos (padrão 10). |
| `POSTGRES_PORT` | não | Porta do host usada pelo `docker compose` (padrão 5433). |
| `ALLOWED_HOSTS` | sim | Lista separada por vírgula. Ex.: `localhost,127.0.0.1,.onrender.com`. |
| `CSRF_TRUSTED_ORIGINS` | **sim em produção** | Origem pública HTTPS do serviço único. Ex.: `https://liga-amigos.onrender.com`. |
| `ADMIN_EMAILS` | não | Emails (separados por vírgula) que devem ser admin. O `start.sh` promove a cada boot; a conta precisa existir. |
| `NUM_PROXIES` | não | Nº de proxies reversos. `1` no Render/Railway para o throttle usar o IP real; `0` quando exposto direto. |
| `SECURE_SSL_REDIRECT` | não | Padrão `not DEBUG`. O `/api/health/` é sempre isento para não quebrar health checks. |
| `SECURE_HSTS_SECONDS` | não | Padrão `31536000` quando `DEBUG=False`. |
| `CONTEST_WINDOW_HOURS` | não | Janela de contestação (padrão 48). |
| `MAX_GOALS_PER_MATCH` | não | Limite de gols (padrão 30; as constraints do banco usam 30). |
| `WALKOVER_GOALS` | não | Gols do W.O. (padrão 3). |
| `FRONTEND_URL` | recomendada | Origem pública do SPA usada no link de reset. Em dev o padrão é `http://localhost:5173`. |
| `BREVO_API_KEY` | sim para envio real | Chave da API transacional da Brevo (`xkeysib-...`). |
| `DEFAULT_FROM_EMAIL` | sim para envio real | Remetente **verificado na Brevo**. Padrão: `Biblioteca <dev.cesar26@gmail.com>`. |
| `BREVO_API_URL` | não | URL da API da Brevo (padrão `https://api.brevo.com/v3/smtp/email`). |
| `EMAIL_HOST` | não | Alternativa SMTP, usada só quando `BREVO_API_KEY` está vazia. |
| `EMAIL_PORT` | não | Porta SMTP (padrão 587; 465 com `EMAIL_USE_SSL=True`). |
| `EMAIL_HOST_USER` | não | Usuário SMTP (alternativa à API da Brevo). |
| `EMAIL_HOST_PASSWORD` | não | Senha/API key SMTP (alternativa à API da Brevo). |
| `EMAIL_USE_TLS` | não | STARTTLS na porta 587 (padrão `True`). |
| `EMAIL_USE_SSL` | não | SSL direto na porta 465 (padrão `False`). |
| `EMAIL_TIMEOUT` | não | Timeout de envio em segundos (padrão 10). |
| `PASSWORD_RESET_TIMEOUT` | não | Validade do link em segundos (padrão 3600). |

Não existem valores inseguros de fallback: fora do desenvolvimento, `SECRET_KEY` é obrigatória.

---

## Contas e dados de demonstração

O seed cria a liga **“Liga dos Amigos”** (exemplo de nome personalizado), 8 jogadores, 14 rodadas,
56 partidas e alguns placares.

```bash
cd backend
python manage.py seed_demo                 # cria se não existir, sem duplicar
python manage.py seed_demo --reset         # apaga a liga/contas demo e recria
python manage.py seed_demo --players 10 --results 4
python manage.py seed_demo --no-fixtures   # só jogadores, para testar “Gerar confrontos”
```

| Perfil | Email | Senha |
| --- | --- | --- |
| Admin | `admin@demo.efootball` | `admin12345` |
| Jogadores | `jogador1@demo.efootball` … | `demo12345` |

> **Nunca rode `seed_demo` em produção.** Ele cria contas com senhas conhecidas e, por isso,
> recusa rodar com `DEBUG=False` (use `--force` apenas em ambiente descartável).
> Para o admin real, veja [Admin em produção](#admin-em-produção).

O seed respeita a trava de rodadas: ele preenche placares na ordem das rodadas e para ao encontrar
uma rodada bloqueada. Para um admin real: `python manage.py createsuperuser` (login por email) e
`/django-admin/`.

---

## Admin em produção

Não existe um cadastro separado de "admin": o papel é a flag **`is_staff`** do usuário. É ela que o
backend (`core/permissions.IsAdmin`) e a rota `/admin` do React verificam. A flag `is_superuser`
serve apenas para dar acesso total ao **`/django-admin/`** do Django.

> **Ordem importa:** o projeto não tem verificação de email. Crie/garanta a conta do admin antes de
> divulgar o cadastro. Depois que os confrontos são gerados, a inscrição pública fecha.

### Opção 1 — declarativa, via `ADMIN_EMAILS` (recomendada no Render)

1. A pessoa se cadastra normalmente no site (ou você cria a conta).
2. No Render, defina `ADMIN_EMAILS=dev.cesar26@gmail.com` (vários emails separados por vírgula).
3. Reinicie/redeploy o serviço. O `start.sh` roda `sync_admins` a cada boot e promove as contas
   existentes. Emails ainda não cadastrados geram **aviso no log**, sem criar conta.
4. Recarregue o site logado; o `/api/auth/me/` passa a devolver `is_staff: true` e `/admin` abre.

Para aplicar na hora, sem depender do próximo boot, use o Shell do Render:

```bash
python backend/manage.py sync_admins
```

`sync_admins` só promove; remover um email de `ADMIN_EMAILS` **não** rebaixa ninguém. Para revogar,
use `set_admin --revoke` (abaixo).

### Opção 2 — pontual, pelo Shell do Render (ou `docker compose exec app ...`)

```bash
# promove uma conta que já existe (admin da liga)
python backend/manage.py set_admin voce@exemplo.com

# promove + libera o Django admin (/django-admin/)
python backend/manage.py set_admin voce@exemplo.com --superuser

# revoga (is_staff e is_superuser)
python backend/manage.py set_admin voce@exemplo.com --revoke
```

### Opção 3 — criar um superusuário do zero

Útil para o primeiro acesso ao `/django-admin/`. O comando abaixo não é interativo e lê a senha de
uma variável de ambiente:

```bash
DJANGO_SUPERUSER_PASSWORD='uma-senha-forte' \
  python backend/manage.py createsuperuser --email voce@exemplo.com --noinput
```

Remova `DJANGO_SUPERUSER_PASSWORD` do ambiente depois de criar a conta. Para trocar a senha:
`python backend/manage.py changepassword voce@exemplo.com`.

O admin do Django fica em **`/django-admin/`** (a rota `/admin` é o painel React).

---

## Segurança da sessão (cookies HttpOnly + CSRF)

### Por que não localStorage

Antes o JWT ficava em `localStorage`. Qualquer XSS — uma dependência comprometida, um `innerHTML`
mal usado, um link com script — consegue ler `localStorage` e levar a sessão inteira para fora do
site, inclusive o refresh token de 7 dias. Não existe mitigação confiável do lado do cliente.

Com **cookies HttpOnly**, o JavaScript não consegue ler o token. Um XSS passa a precisar executar
ações *dentro* da sessão (e aí o CSRF não ajuda em nada), mas não consegue exportar credenciais
para outro dispositivo nem sobreviver ao fechamento da aba.

### Como funciona

| Cookie | Conteúdo | `Path` | `HttpOnly` | `SameSite` | `Secure` | Validade |
| --- | --- | --- | --- | --- | --- | --- |
| `access_token` | JWT de acesso | `/api/` | sim | `Lax` | fora do `DEBUG` | 15 min |
| `refresh_token` | JWT de refresh | `/api/auth/` | sim | `Lax` | fora do `DEBUG` | 7 dias |
| `csrftoken` | token CSRF (legível) | `/` | não | `Lax` | fora do `DEBUG` | sessão |

- **Login/cadastro** definem os dois cookies e **não devolvem tokens no corpo** — a resposta traz
  apenas `{user, code, message}`.
- **Access curto (15 min)**; o refresh vale 7 dias, **rotaciona a cada uso** e o anterior entra na
  blacklist (`ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION` + app `token_blacklist`).
- **Autenticação DRF** (`core.authentication.CookieJWTAuthentication`) lê o access apenas do
  cookie. Header `Authorization: Bearer` não é aceito (há teste para isso).
- **Logout** blacklista o refresh do cookie e apaga os dois cookies.
- **`GET /api/auth/me/`** é como o front descobre se existe sessão.
- **Refresh com single-flight** no axios: vários 401 simultâneos compartilham uma única chamada de
  refresh (o token é de uso único, então chamadas paralelas invalidariam umas às outras). Falha do
  refresh → toast `SESSION_EXPIRED` e redirecionamento para o login preservando `?next=`.
- **Limpeza de legado**: no boot, `frontend/src/lib/legacyTokenCleanup.js` apaga chaves antigas de
  token (`liga.access`, `liga.refresh`, `token`, `access_token`, …) de `localStorage` e
  `sessionStorage`. Nenhum outro arquivo do front toca storage com credenciais (teste automatizado
  varre `frontend/src` e falha se encontrar). `IndexedDB` não é usado em lugar nenhum.

### CSRF

- Toda requisição de escrita (`POST/PUT/PATCH/DELETE`) em `/api/` passa por
  `core.middleware.ApiCsrfMiddleware`, que força a validação do Django **inclusive em views DRF**
  (que são `csrf_exempt` por padrão) e **inclusive no login**. O
  `django.middleware.csrf.CsrfViewMiddleware` padrão continua na pilha logo depois, cobrindo o
  Django admin (`check --deploy` limpo).
- O cookie `csrftoken` é legível e o axios envia `X-CSRFToken`; o cookie é garantido por
  `GET /api/auth/csrf/` no carregamento do app.
- Sem token válido a resposta é **403 `CSRF_FAILED`** com a mensagem amigável
  “Não foi possível validar sua solicitação. Recarregue a página e tente de novo.” —
  em nenhum ponto o CSRF é desabilitado.

### Enumeração de usuário e força bruta

- Email inexistente e senha errada devolvem exatamente a mesma resposta
  (`401 INVALID_CREDENTIALS`, “Email ou senha incorretos.”).
- Throttling: login `10/min`, cadastro `30/h`, refresh `60/h` por IP; usuários `6000/h`.
- Pedido de reset de senha `5/h` e confirmação `20/h` por IP. Email existente e inexistente
  devolvem a mesma resposta (`200 PASSWORD_RESET_SENT`).

### Auditoria de XSS e SQL

- Nenhum `dangerouslySetInnerHTML` no frontend (verificado por teste) e todo texto de usuário é
  renderizado como texto puro pelo React.
- Nenhum SQL cru concatenado no backend: só ORM, com parâmetros.
- CSP restritiva (abaixo) sem `unsafe-inline` para scripts.

---

## Email e recuperação de senha

O único email transacional é o link de redefinição de senha. Não há verificação de email no
cadastro nem notificações automáticas de partidas.

### Como funciona

- `POST /api/auth/password-reset/` recebe o email e **sempre** devolve a mesma resposta
  (`PASSWORD_RESET_SENT`), exista ou não a conta. Se a conta estiver ativa e tiver senha utilizável,
  o Django gera um token de uso único e envia o link.
- `POST /api/auth/password-reset/confirm/` valida `uid` + `token`, troca a senha, blacklista todos
  os refresh tokens do usuário e limpa os cookies da resposta. A nova senha passa pelos mesmos
  validadores do cadastro.
- O link aponta para `FRONTEND_URL/redefinir-senha?uid=...&token=...`; o token expira em
  `PASSWORD_RESET_TIMEOUT` (padrão **1 hora**) e deixa de valer depois do primeiro uso.
- As páginas são `/esqueci-senha` e `/redefinir-senha`; o login tem o link “Esqueci minha senha”.
- Throttle: `5/h` para solicitar e `20/h` para confirmar, por IP.
- Falha de envio é registrada no log e a resposta continua genérica, para não revelar se o email
  existe.

### Brevo (recomendado)

Em desenvolvimento (`DEBUG=True`) o backend de console imprime o email no terminal e o link aponta
para `http://localhost:5173`. Em produção, o projeto usa a **API HTTP da Brevo** quando
`BREVO_API_KEY` está definida. Basta configurar no Render:

| Variável | Exemplo |
| --- | --- |
| `BREVO_API_KEY` | `xkeysib-...` |
| `DEFAULT_FROM_EMAIL` | `Biblioteca <dev.cesar26@gmail.com>` |
| `FRONTEND_URL` | `https://liga-amigos.onrender.com` |

A chave é criada em **Brevo → Transactional → Settings → API keys**. O email em
`DEFAULT_FROM_EMAIL` precisa estar **verificado na Brevo** (ou o domínio autenticado); sem isso a
API recusa o envio. A API da Brevo tem precedência sobre SMTP.

Neste projeto o remetente é **`Biblioteca <dev.cesar26@gmail.com>`**, já verificado na Brevo. O
mesmo email também é usado como conta admin via `ADMIN_EMAILS=dev.cesar26@gmail.com`.

### SMTP (alternativa)

Se preferir SMTP, deixe `BREVO_API_KEY` vazia e use `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
com `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` e `EMAIL_USE_TLS`. Nesse
caso, a senha é a **SMTP key** da Brevo (não a API key). Resend, Mailgun, Gmail e qualquer outro
provedor SMTP também funcionam sem SDK adicional.

---

## Serviço único e mesma origem

Produção roda **um único serviço**: o Django entrega a API em `/api/` e o build do React em todas
as outras rotas.

- `build.sh` instala dependências, builda o frontend (`frontend/dist`), roda `collectstatic` e
  `migrate`.
- `whitenoise` serve os assets (`WHITENOISE_ROOT = frontend/dist`) e `core.spa.spa_index` responde
  `index.html` (com `Cache-Control: no-store`) para tudo que **não** comece com `/api/`,
  `/django-admin/` ou `/static/`.
- **CORS foi removido** (inclusive `django-cors-headers` das dependências): não existe requisição
  cross-origin. Restaram apenas `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` explícitos via env.
- Em desenvolvimento o Vite faz proxy de `/api` para o Django, reproduzindo a mesma origem.

---

## Hardening de produção

Com `DEBUG=False` (e `SECURE_SSL_REDIRECT` pode ser forçado por env):

- `SECRET_KEY` obrigatória — sem ela o processo **não sobe** (`ImproperlyConfigured`). Placeholders
  conhecidos (`change-me-in-production`, etc.) e chaves com menos de 32 caracteres também são
  rejeitados quando `DEBUG=False`.
- `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`.
- `SECURE_HSTS_SECONDS=31536000` com `includeSubDomains` e `preload`.
- `SECURE_CONTENT_TYPE_NOSNIFF=True`, `X_FRAME_OPTIONS=DENY`, `Referrer-Policy: same-origin`,
  `Cross-Origin-Opener-Policy: same-origin`, `Permissions-Policy` restritiva.
- `SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https")` para o proxy do Render/Railway.
- `/api/health/` é isento do redirect HTTPS (`SECURE_REDIRECT_EXEMPT`) para que o health check
  interno da plataforma não receba um 301. É um endpoint público de liveness e não consulta o banco.
- **CSP**: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
  img-src 'self' data:; font-src 'self' data:; connect-src 'self'; object-src 'none';
  base-uri 'self'; form-action 'self'; frame-ancestors 'none'` (nenhum script inline).
- `CSRF_TRUSTED_ORIGINS` por env; Django admin em `/django-admin/`.
- Renderizadores DRF só JSON quando `DEBUG=False` (sem Browsable API em produção).
- `NUM_PROXIES=1` no Render/Railway para o throttle de login/cadastro usar o IP real do cliente
  (`X-Forwarded-For`) em vez do IP do proxy. Fora de um proxy confiável, mantenha `0`.
- No Neon, a conexão exige TLS (`sslmode=require`), usa `CONN_HEALTH_CHECKS`, `CONN_MAX_AGE=300`
  (abaixo do scale-to-zero de ~5 min) e desabilita server-side cursors (PgBouncer em modo
  transaction). Migrações podem usar o endpoint direto via `DIRECT_DATABASE_URL`.

### Riscos residuais (conhecidos)

- **Sem verificação de email e sem notificações automáticas.** A recuperação de senha agora é por
  email; o `seed_demo` com senha conhecida continua bloqueado com `DEBUG=False`.
- **Throttle em memória por processo.** O cache padrão do Django é `LocMemCache`: com 2 workers,
  os limites de login/cadastro valem por worker (e zeram ao reiniciar). Para um limite global,
  configure um cache compartilhado (Redis) — não é obrigatório para o tamanho desta liga.
- **Backups são responsabilidade do Neon.** Use branches/restauração point-in-time do Neon; o
  Render não hospeda mais o banco neste projeto.
- O refresh token de 7 dias continua válido se roubado por um XSS que execute na própria origem;
  a mitigação é a CSP estrita + rotação/blacklist do refresh.

---

## Nome personalizado da liga

- O nome vive em `League.name` (o campo já existia); a migration `0003` adiciona o default
  “Liga eFootball” e preenche nomes vazios, **sem tocar nos nomes já existentes**.
- **`PATCH /api/admin/league/`** (somente admin) valida **3 a 60 caracteres**, remove espaços
  extras (`"  Liga   Nova "` → `"Liga Nova"`) e **rejeita HTML** (`<`, `>`), devolvendo
  `400 INVALID_LEAGUE_NAME` — “O nome da liga deve ter entre 3 e 60 caracteres.”.
- Cada alteração grava `LeagueChangeLog` (usuário, valor anterior, novo valor, horário).
  Repetir o mesmo nome devolve `NOTHING_CHANGED` e não gera log.
- Pode ser alterado **a qualquer momento**, inclusive com a liga em andamento: partidas,
  rodadas e classificação não dependem do nome.
- Exibição: cabeçalho do site (que também define `document.title`), página inicial e tela de
  classificação; `GET /api/league/` é o endpoint público de leitura.
- O `seed_demo` usa “Liga dos Amigos” como exemplo.

---

## Remoção de jogador

- **`DELETE /api/admin/participants/<id>/`** (somente admin) remove o vínculo com a liga
  (`Participant`), mas **mantém a conta de login** (`User`).
- Antes de gerar confrontos, a remoção é direta.
- Depois de gerar confrontos e **sem nenhum resultado**, os confrontos são regerados sem o
  jogador para manter rodadas, folgas (`BYE`) e classificação consistentes.
- Com resultados já registrados, jogadores que têm partidas **não podem ser removidos**
  (`409 CANNOT_REMOVE_PARTICIPANT_WITH_RESULTS`), para não apagar histórico e alterar a
  classificação.
- Um jogador inscrito depois da geração e ainda sem partidas pode ser removido sem mexer nos
  confrontos existentes.
- Também é bloqueado (`409 CANNOT_REMOVE_LAST_PLAYERS`) quando a remoção deixaria menos de 2
  jogadores em uma liga que já tem confrontos.

---

## Geração de confrontos

- Método do círculo: com `N` jogadores são `N-1` rodadas por turno (N par) e `N` rodadas por turno
  quando N é ímpar, pois um jogador folga (`BYE`) por rodada e **nenhuma partida é criada** para a
  folga.
- 2º turno repete os pares com mando invertido, em rodadas numeradas na sequência — a numeração é
  **contínua entre os turnos**, o que é exatamente o que a trava de rodadas usa.
- Sorteio com semente (`League.fixture_seed`) para auditoria; geração idempotente (segunda chamada
  devolve o estado existente) e segura sob concorrência (lock da linha da liga + constraints).
- Após criar, o serviço revalida no banco: ninguém duas vezes na mesma rodada e total de partidas
  esperado; qualquer falha desfaz a transação.

---

## Resultados, contestação e W.O.

- Só o vencedor lança o resultado; empate pode ser lançado por qualquer um dos dois.
- Gols inteiros de 0 a 30 (`MAX_GOALS_PER_MATCH`).
- Resultado já lançado: repetir o mesmo placar pelo mesmo autor é no-op (`200 NOTHING_CHANGED`),
  qualquer outra tentativa é `409 RESULT_ALREADY_REGISTERED`.
- Contestação: o adversário de quem lançou, em até 48h; a partida vira `CONTESTED` e **continua
  valendo** na classificação. O admin confirma (`FINISHED`) ou corrige.
- Correções **não** reabrem nem bloqueiam rodadas posteriores: a classificação é sempre
  recalculada a partir das partidas.
- Toda alteração relevante grava `MatchResultLog` com valores anteriores/novos, autor e horário.

### W.O. pelo admin

Um jogador ausente não pode travar a liga, mas o admin também não pode pular a trava para lançar
um resultado normal.

- `POST /api/matches/<id>/walkover/` com `{"absent_side": "home" | "away"}` (somente admin).
- Grava **3 a 0** para quem compareceu (`WALKOVER_GOALS`), status `FINISHED` e `is_walkover=true`.
- A partida é encerrada como qualquer outra: a rodada fecha e a seguinte libera.
- Registra `RESULT_WALKOVER` no log de auditoria, com o nome de quem não compareceu.
- A interface mostra o badge **W.O.** no cartão da partida.
- O W.O. **respeita a trava**: só é possível em partida pendente de rodada aberta (a rodada atual
  é justamente a que precisa ser destravada).
- Uma correção posterior de placar limpa `is_walkover` (o resultado deixou de ser um W.O.).

---

## Trava sequencial de rodadas

O estado de cada rodada é **sempre calculado no backend** a partir das partidas e da configuração
atuais; nunca é armazenado. Trocar a configuração no meio da liga é seguro: o estado é recalculado
e nenhum resultado é apagado ou invalidado.

### Chave do admin: 1 ou 2 rodadas simultâneas

A liga tem a configuração **`League.single_round_mode`** (migration `0004`, default **`True`** para
preservar o comportamento que já estava em produção):

- **Ativada (`True`)**: apenas **1 rodada aberta por vez**. A rodada N só aceita resultado quando a
  N-1 estiver encerrada.
- **Desativada (`False`)**: até **2 rodadas abertas ao mesmo tempo**, em **pares fixos por
  número**: (1, 2), (3, 4), (5, 6)...

A regra é generalizada pelo conceito de **bloco**: `tamanho do bloco = 1` (chave ativada) ou `2`
(desativada), e `bloco(n) = ceil(n / tamanho)`. Uma rodada está **aberta** quando **todas as
rodadas de blocos anteriores** estão encerradas; as rodadas do mesmo bloco abrem juntas.

Exemplos com a chave desativada:

- As rodadas **1 e 2** abrem desde o início.
- As rodadas **3 e 4** só abrem quando **1 e 2** estiverem **ambas** encerradas. Encerrar só a 1
  **não** libera a 3.
- Num total ímpar de rodadas, a última fica sozinha no seu bloco.

A numeração é **contínua entre os turnos**, então um par pode atravessar a virada: com **11
jogadores** são **11 rodadas por turno (22 no total), 5 partidas por rodada e 1 folga por rodada**;
o par **(11, 12)** junta a última rodada do 1º turno com a primeira do 2º e funciona normalmente.
Com 10 jogadores, o par **(9, 10)** também atravessa o turno.

### Regras que não mudam

- **Rodada encerrada** = todas as suas partidas com resultado (`FINISHED` ou `CONTESTED`, incluindo
  W.O.). Como a folga não cria partida, uma liga ímpar encerra rodadas normalmente.
- **Verificação no backend**, dentro do mesmo `transaction.atomic` que grava o resultado, com lock
  da linha da liga (`select_for_update`) antes do lock da partida. A configuração é lida dentro da
  transação, então duas requisições simultâneas não furam a trava nem se a chave for trocada no
  meio (há testes com threads).
- **Estados calculados no backend** (`league/services/rounds.py`: `locked`, `open`, `closed`) e
  expostos em `/api/rounds/` (`state`, `state_label`) e em cada partida (`round_state`,
  `permissions.round_locked`, `permissions.can_report`). O front apenas exibe.
- **Trocar a chave nunca apaga resultados.** Se a rodada 2 já tiver placares e a chave for ativada
  com a 1 incompleta, os placares existentes continuam valendo; apenas **novos** lançamentos na
  rodada 2 ficam bloqueados até a 1 encerrar.
- **Alterar data continua permitido** em rodada bloqueada: a trava vale só para lançar resultado.
- **Corrigir/contestar resultado antigo** não reabre nem bloqueia rodadas e continua permitido em
  qualquer modo.
- O **W.O. do admin** mantém o comportamento: 3x0, encerra a partida e respeita a trava.
- Erro: **409 `ROUND_NOT_OPEN`** — “Você ainda não pode lançar este resultado: as rodadas
  anteriores precisam ser encerradas primeiro.”.
- A chave é alterada por **`PATCH /api/admin/league/`** (somente admin) com
  `{"single_round_mode": true|false}`; o mesmo valor é idempotente e cada mudança grava
  `LeagueChangeLog` com autor, valor anterior, novo valor e horário.

---

## Classificação e desempate

A ordem é **exatamente**:

1. **pontos**
2. **número de vitórias**
3. **saldo de gols**
4. gols pró
5. nome do time

Os critérios 4 e 5 existem apenas para tornar a ordem determinística (o último desempate técnico
usa o nome do jogador, se dois times tiverem o mesmo nome). **Não existe mais confronto direto** —
a função de mini-tabela foi removida junto com seus testes.

Pontuação 3/1/0 e estatísticas derivadas de partidas `FINISHED` **e** `CONTESTED`. A tabela é
sempre recalculada (`compute_standings`), nunca incrementada, então correções não acumulam pontos
indevidos.

---

## Modelo de permissões

Autenticação identifica o usuário **pelo cookie de sessão**, nunca pelo corpo da requisição.
Autorização é feita por permissões DRF + serviços, com checagem de objeto.

| Ação | Público | Jogador da partida | Terceiro logado | Admin |
| --- | --- | --- | --- | --- |
| Ver rodadas, partidas, tabela, jogadores, liga | ✅ | ✅ | ✅ | ✅ |
| Cadastrar (enquanto `REGISTRATION`) | ✅ | — | — | — |
| Editar o próprio perfil | — | ✅ | ✅ | ✅ |
| Gerar / resetar confrontos | — | — | — | ✅ |
| Inscrever jogador manualmente | — | — | — | ✅ |
| Alterar nome da liga | — | — | — | ✅ |
| Alterar data de partida agendada | — | ✅ | ❌ `NOT_MATCH_PARTICIPANT` | ✅ |
| Lançar resultado | — | ✅ (vencedor) | ❌ `NOT_MATCH_PARTICIPANT` | ✅ |
| Lançar W.O. | — | — | — | ✅ |
| Editar resultado | — | ❌ `ADMIN_ONLY` | ❌ `ADMIN_ONLY` | ✅ |
| Contestar (adversário de quem lançou) | — | ✅ | ❌ `NOT_MATCH_PARTICIPANT` | ✅ |
| Confirmar contestação / ver auditoria | — | — | — | ✅ |

A checagem de propriedade é repetida dentro da transação do serviço, comparando `request.user`
com `match.home.user_id`/`match.away.user_id`.

---

## Padrão de mensagens

Toda resposta de erro segue:

```json
{ "code": "ROUND_NOT_OPEN", "message": "Você ainda não pode lançar este resultado: as rodadas anteriores precisam ser encerradas primeiro." }
```

- Textos centralizados em **`backend/core/messages.py`**.
- `AppError` + `api_exception_handler` cobrem 400/401/403/404/405/409/429 e validações.
- `ApiErrorMiddleware` devolve `500 SERVER_ERROR` em JSON, com traceback apenas no log.
- O front sempre exibe a `message` em toast; nunca “Request failed with status code 403”.

Códigos adicionados nesta alteração: `ROUND_NOT_OPEN` (409), `CSRF_FAILED` (403),
`SESSION_EXPIRED` (401), `INVALID_LEAGUE_NAME` (400), `INVALID_ABSENT_SIDE` (400),
`WALKOVER_REGISTERED`, `LOGIN_OK`/`LOGGED_IN`, `LEAGUE_NAME_TAKEN`.

Mensagens existentes continuam iguais, por exemplo
`NOT_MATCH_PARTICIPANT`: “Você não pode alterar dados desse confronto, pois não está envolvido nele.”.

---

## API

Base: `/api/`. Leitura é pública; escrita exige sessão (cookies) **e** `X-CSRFToken`.

### Autenticação

| Método | Endpoint | Descrição |
| --- | --- | --- |
| GET | `/auth/csrf/` | Garante o cookie `csrftoken` e devolve o token |
| POST | `/auth/register/` | Cadastro + login automático (define cookies) |
| POST | `/auth/login/` | Login por email (define cookies; sem tokens no corpo) |
| POST | `/auth/password-reset/` | Solicita link de redefinição (resposta genérica) |
| POST | `/auth/password-reset/confirm/` | Redefine a senha com `uid` + `token` |
| POST | `/auth/refresh/` | Rotaciona o refresh do cookie e define novos cookies |
| POST | `/auth/logout/` | Blacklista o refresh e apaga os cookies |
| GET/PATCH | `/auth/me/` | Perfil do usuário logado |

### Leitura pública

| Método | Endpoint | Descrição |
| --- | --- | --- |
| GET | `/league/` | Liga ativa, nome personalizado, status, contagens, rodada atual |
| GET | `/participants/` | Jogadores inscritos |
| GET | `/standings/` | Classificação calculada |
| GET | `/rounds/?leg=1&mine=1` | Rodadas com `state` (`locked`/`open`/`closed`) |
| GET | `/matches/?mine=1&status=pending&round=3` | Lista plana de partidas |
| GET | `/matches/<id>/` | Detalhe da partida |
| GET | `/health/` | Health check |

### Escrita

| Método | Endpoint | Quem |
| --- | --- | --- |
| POST | `/matches/<id>/result/` | Participantes (vencedor) e admin — respeita a trava |
| PATCH | `/matches/<id>/result/` | Admin (correção) |
| POST | `/matches/<id>/walkover/` | Admin (W.O. 3x0) |
| PATCH | `/matches/<id>/kickoff/` | Participantes e admin (liberado em rodada bloqueada) |
| POST | `/matches/<id>/contest/` | Adversário de quem lançou e admin |
| POST | `/matches/<id>/confirm/` | Admin |
| GET | `/matches/<id>/logs/` | Admin |
| PATCH | `/admin/league/` | Admin (nome da liga e/ou `single_round_mode`) |
| POST | `/admin/generate-fixtures/` | Admin (idempotente) |
| POST | `/admin/reset-and-regenerate/` | Admin (bloqueado com resultados) |
| GET | `/admin/overview/` | Admin (inclui pendentes para W.O.) |
| POST | `/admin/participants/` | Admin (inscrever) |
| DELETE | `/admin/participants/<id>/` | Admin (remover da liga; mantém a conta) |

Headers opcionais nos endpoints críticos: `Idempotency-Key: <texto-único>`.
`Idempotency-Key` e o corpo do resultado são a base da idempotência; a classificação nunca é
incrementada.

---

## Frontend

### Rotas

| Rota | Acesso |
| --- | --- |
| `/` | público — classificação e resumo da liga |
| `/rodadas` | público — rodadas, cadeados e ações permitidas |
| `/login`, `/cadastro` | público |
| `/esqueci-senha`, `/redefinir-senha` | público — recuperação de senha |
| `/perfil` | privado (redireciona ao login e volta) |
| `/admin` | apenas admin (senão página amigável de acesso negado) |
| `/sem-acesso`, `*` | páginas amigáveis |

### Sessão no front

1. No boot, `purgeLegacyAuthStorage()` apaga tokens antigos do navegador.
2. `GET /api/auth/csrf/` garante o cookie de CSRF.
3. `GET /api/auth/me/` descobre a sessão (401 significa “visitante”, não erro).
4. Em qualquer 401 de rota autenticada: um único refresh (single-flight) e **uma** repetição da
   requisição; se falhar, toast `SESSION_EXPIRED` e redirecionamento para `/login?next=…`.
5. Nenhuma tela acessa `localStorage`/`sessionStorage`/`IndexedDB` para credenciais — só o tema
   (`liga.theme`) é persistido localmente.

### UX

- Mobile-first, navegação inferior no celular, tema escuro/claro.
- Cabeçalho e `document.title` mostram o **nome personalizado** da liga (atualizado na hora após o
  admin renomear).
- Banner discreto com o modo atual (“Modo atual: 1 rodada por vez” / “2 rodadas por vez”).
- Rodadas abertas (uma ou duas) destacadas; bloqueadas com cadeado e tooltip
  (“Esta rodada será liberada quando as rodadas anteriores forem encerradas.”); “Inserir
  resultado” só aparece em rodada aberta.
- Cartões de partida com placar, status, badge **W.O.**, autoria e aviso de contestação.
- Admin: switch “Modo 1 rodada por vez” com confirmação e toast, nome da liga, geração/reset de
  confrontos, W.O. por lado, contestações, inscrições e remoção de jogador (a conta de login é
  mantida).
- Toasts de sucesso/erro, loading, erro com retry e estados vazios.

---

## Testes

```bash
cd backend
source ../.venv/bin/activate
pytest
```

**Resultado final desta alteração: `144 passed`** (backend) + `npm run build` sem erros no frontend.

Cobertura relevante:

- **Segurança da sessão**: cookies `HttpOnly`/`SameSite=Lax`/`Secure` fora do `DEBUG`; login e
  cadastro sem tokens no corpo; requisição autenticada só com cookie (header `Bearer` recusado);
  POST sem CSRF → `403 CSRF_FAILED`; login com cookie + `X-CSRFToken`; refresh rotaciona e o token
  anterior é rejeitado; logout limpa os cookies e invalida a sessão; ausência de cookie de refresh →
  `SESSION_EXPIRED`; headers de segurança e HSTS; varredura de `frontend/src` contra
  `localStorage`/`sessionStorage`/`indexedDB` com credenciais; ausência de `dangerouslySetInnerHTML`.
- **Nome da liga**: admin altera (com espaços normalizados) e o endpoint público reflete; não-admin
  recebe `403 ADMIN_ONLY`; vazio/curto/longo/HTML → `400 INVALID_LEAGUE_NAME`; no-op sem log;
  renomear em liga em andamento não altera partidas nem classificação; log de auditoria gravado.
- **Trava de rodadas**: modo de 1 rodada (default) idêntico ao anterior; modo de 2 rodadas com
  pares fixos e blocos; encerrar só a primeira rodada do par não libera o próximo; encerrar as duas
  libera o par seguinte; cenários de 11 jogadores (22 rodadas, 5 partidas, 1 folga por rodada,
  par (11,12) na virada), 10 jogadores (par (9,10) na virada) e total ímpar (última sozinha);
  `CONTESTED` e W.O. contam como encerradas nos dois modos; troca da chave no meio da liga preserva
  resultados e recalcula estados; corrigir resultado antigo continua permitido; duas requisições
  simultâneas não furam a trava nem com a chave trocada; apenas admin altera a chave, PATCH repetido
  é idempotente e a auditoria registra valor anterior/novo.
- **Desempate**: pontos iguais decididos por vitórias; vitórias iguais por saldo; três times
  empatados; confronto direto **não** é usado; empate total decidido pelo nome do time.
- **W.O.**: só admin, 3x0 para quem compareceu, entra na classificação, `is_walkover`, log,
  fecha a rodada, exige partida pendente e respeita a trava.
- **Remoção de jogador**: só admin; remove o participante e mantém a conta; antes dos confrontos
  é direta; depois dos confrontos sem resultados regera a tabela; com resultados é bloqueada;
  jogador sem partidas pode ser removido; e a liga não fica com menos de 2 jogadores.
- **Recuperação de senha**: email enviado só para conta ativa, resposta genérica para email
  inexistente, token válido troca a senha, token inválido/expirado e reuso recebem
  `PASSWORD_RESET_INVALID`, senha fraca é rejeitada, refresh tokens antigos são blacklistados, os
  cookies são limpos e a API da Brevo é usada quando `BREVO_API_KEY` está configurada.
- **Regressão**: idempotência de geração e resultado (inclusive concorrência com threads),
  propriedade da partida (terceiro recebe `403 NOT_MATCH_PARTICIPANT`), formato `{code, message}` e
  permissões existentes.

**Testes atualizados por causa das novas regras** (documentado no resumo final): `test_auth.py`
(cookies em vez de tokens no corpo), `test_errors.py` (token expirado/inválido agora via cookie),
`test_standings.py` (removida a função de confronto direto), e `test_results.py`,
`test_permissions.py`, `test_walkover.py`, `test_idempotency.py`, que passaram a usar a partida da
rodada 1 (sempre aberta) em vez de qualquer partida do 1º turno — antes poderiam cair numa rodada
bloqueada.

---

## Deploy

### Banco no Neon

O banco **não** é criado pelo Render. Ele fica no **Neon**, então os dados sobrevivem a redeploys,
recriação do serviço e ao sleep do plano free.

1. Crie o projeto no Neon e copie a **connection string pooled** (o hostname tem `-pooler` e a URL
   termina em `?sslmode=require`). Guarde também a **direct** (sem `-pooler`), opcional.
2. Escolha a região do Neon mais próxima da região do Render (ex.: `us-east-2`/Ohio) para reduzir
   latência.
3. No Neon, o banco pode suspender após ~5 minutos sem uso. O app está configurado com
   `CONN_MAX_AGE=300` + `CONN_HEALTH_CHECKS=True` para não reutilizar conexões mortas.
4. Migrações usam `DIRECT_DATABASE_URL` quando definido; o resto do app usa `DATABASE_URL`
   (pooled). Isso segue a recomendação do Neon para schema changes fora do PgBouncer.

### Render (serviço único)

`render.yaml` descreve **um** serviço web, sem bloco `databases`. O PostgreSQL é externo (Neon).

1. Suba o repositório no GitHub.
2. Render → **New → Blueprint** → selecione o repositório.
3. Preencha as variáveis que estão com `sync: false`:
   - `DATABASE_URL`: string **pooled** do Neon;
   - `DIRECT_DATABASE_URL`: string **direta** do Neon (opcional, usada só no `migrate`);
   - `BREVO_API_KEY`: chave da API transacional da Brevo.
   `SECRET_KEY` é gerada pelo Blueprint. `DEFAULT_FROM_EMAIL`
   (`Biblioteca <dev.cesar26@gmail.com>`), `ADMIN_EMAILS` (`dev.cesar26@gmail.com`),
   `CSRF_TRUSTED_ORIGINS` e `FRONTEND_URL` já vêm definidos; ajuste se o nome do serviço for
   diferente ou se usar domínio próprio.
4. O build executa `./build.sh`:
   - `pip install -r backend/requirements.txt`;
   - `npm ci`/`npm install` + `npm run build` em `frontend` (gera `frontend/dist`);
   - `collectstatic` (WhiteNoise) e `migrate` (via `DIRECT_DATABASE_URL`, se definido).
5. O start executa `./start.sh`: `sync_admins` + `gunicorn` (2 workers), health check em
   `/api/health/`.
6. Se usar domínio próprio, acrescente-o em `ALLOWED_HOSTS` e em `CSRF_TRUSTED_ORIGINS`.
7. Para criar/promover o admin: cadastre a conta e use `ADMIN_EMAILS`, ou o Shell do Render com
   `python backend/manage.py set_admin email --superuser`; Django admin em `/django-admin/`.

> O plano free do Render dorme após inatividade; o primeiro acesso depois disso pode demorar
> (cold start do Render + retomada do compute do Neon). O banco continua no Neon.

### Docker (opcional)

O `Dockerfile` é multi-stage (Node 20 constrói o Vite; Python 3.12 roda o Django), cria usuário
não-root, roda `collectstatic` no build, `migrate` no start e **não** copia o `.env` para a imagem
(veja `.dockerignore`).

```bash
cp .env.example .env            # preencha SECRET_KEY e DATABASE_URL do Neon
docker compose up --build       # app em http://localhost:8000 (DEBUG=False)
```

Em produção atrás de HTTPS, mantenha `DEBUG=False`. Para testar localmente em HTTP, use
`DEBUG=True` (só então os cookies deixam de ser `Secure`).

Para o reset de senha no Docker, configure `FRONTEND_URL` e `BREVO_API_KEY` no `.env`; sem uma
chave válida, a falha de envio fica registrada no log e a resposta ao usuário continua genérica.
Se preferir SMTP, configure também `EMAIL_*` e deixe `BREVO_API_KEY` vazia.

PostgreSQL local opcional (sem Neon), com o profile `local-db`:

```bash
DATABASE_URL=postgres://postgres:postgres@db:5432/liga_efootball \
  docker compose --profile local-db up --build
```

### Migrando de dois serviços (API + site estático) para um

A versão anterior publicava a API e o frontend estático separadamente. Passos:

1. Remova o serviço estático do `render.yaml` (já removido neste repositório) e deixe apenas o
   serviço Python; o `build.sh` agora builda o frontend.
2. Remova `CORS_ALLOWED_ORIGINS`/`VITE_API_URL` do painel — não são mais usados (não há CORS nem
   build apontando para outra origem).
3. Defina `CSRF_TRUSTED_ORIGINS` com a URL do **serviço único**.
4. Depois do deploy, os usuários precisam entrar de novo: os tokens que estavam em `localStorage`
   são apagados no primeiro carregamento e passam a viver em cookies HttpOnly.

### Railway

- Crie o projeto e use o **Neon** como banco (ou o plugin PostgreSQL, que injeta `DATABASE_URL`).
- Build: `./build.sh`; Start: `./start.sh` (ou o `Procfile`).
- Defina `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` (URL do serviço),
  `NUM_PROXIES=1`, `FRONTEND_URL`, `BREVO_API_KEY` e `DEFAULT_FROM_EMAIL` para recuperação de senha.
  `ADMIN_EMAILS` é opcional.

### Dependências auditadas

- `pip-audit` (requirements e ambiente): **sem vulnerabilidades conhecidas** após atualizar
  Django REST Framework para 3.18.2 e pytest para 9.2.0.
- `npm audit`: **0 vulnerabilidades** após atualizar `react-router-dom` para 7.18.5.
- `pip-audit` é uma ferramenta de desenvolvimento; instale com `pip install pip-audit` para repetir.

---

## Decisões tomadas nesta alteração

1. **`Path` do refresh em `/api/auth/`** (e não apenas `/api/auth/refresh/`): o logout precisa ler o
   refresh para colocá-lo na blacklist. Continua sendo um caminho restrito aos endpoints de
   autenticação — o token nunca vai para `/api/matches/`, assets ou páginas.
2. **SPA servida por view própria (`core/spa.py`)** em vez de `TemplateView`: devolve uma página
   amigável quando `frontend/dist` não existe (dev sem build) e marca `index.html` como
   `no-store`.
3. **`django-cors-headers` removido**: com origem única não há CORS, e deixar a dependência
   permitiria configuração acidental de wildcard. `CSRF_TRUSTED_ORIGINS` continua explícito.
4. **CSRF por middleware** (`ApiCsrfMiddleware`, subclasse de `CsrfViewMiddleware`) e
   `CSRF_FAILURE_VIEW` apontando para JSON: reaproveita toda a validação do Django (token + origem)
   sem desabilitar nada e sem depender de `SessionAuthentication`.
5. **Descoberta de sessão silenciosa**: `GET /auth/me/` pode devolver 401 sem toast/redirect, para
   que visitantes em páginas públicas não vejam “sessão expirada”.
6. **Flags derivadas de `DEBUG` reaplicadas na suíte**: pytest-django força `DEBUG=False` depois do
   carregamento das settings; o `conftest.py` reaplica a postura de produção para os testes
   verificarem os headers e o `Secure` de verdade.
7. **`League.name` já existia**: a migration só adiciona o default e preenche nomes vazios. O
   `max_length` no banco continua 100; a regra 3–60 é validada na API para não arriscar dados.
8. **Nome único**: a constraint `unique_league_name` foi mantida; duplicar um nome devolve
   `400 INVALID_LEAGUE_NAME` em vez de 500.
9. **Tiebreak extra por nome do jogador** depois do nome do time: só para garantir ordem
   determinística quando dois times têm exatamente o mesmo nome.
10. **W.O. de 3 gols é configurável** (`WALKOVER_GOALS`), limitado por `MAX_GOALS_PER_MATCH`.
11. **W.O. respeita a trava** e só atua em partida pendente; `is_walkover` é limpo quando o admin
    corrige o placar (o resultado deixa de ser W.O.).
12. **Rodada fechada usa `FINISHED` + `CONTESTED`** com placar preenchido, então contestação e W.O.
    contam como encerramento — como pedido.
13. **Admin não pula a trava** para resultado comum (nem para W.O. em rodada bloqueada).
14. **`Idempotency-Key` preservado** nos endpoints críticos e a idempotência de domínio continua
    valendo mesmo sem o header.
15. **`single_round_mode` com default `True`**: a migration `0004` adiciona a coluna preenchida para
    todas as ligas existentes, sem apagar dados e sem mudar o comportamento atual.
16. **Blocos derivados, nunca armazenados**: `bloco(n) = ceil(n / 1|2)` e o estado de cada rodada
    são recalculados a partir das partidas e da chave vigente. Assim, ativar/desativar no meio da
    liga não exige migração de dados nem invalida resultados.
17. **A chave é lida dentro da transação de escrita**: o lock da linha da liga serializa lançamentos
    e alterações de configuração, fechando a condição de corrida inclusive quando a chave muda no
    meio de duas requisições.
18. **Mesmo `PATCH /admin/league/`**: o endpoint do nome foi ampliado para aceitar
    `single_round_mode` (nome e modo podem ir juntos), reaproveitando `IsAdmin`, `AppError`,
    `messages.py` e `LeagueChangeLog`.

---

## Limitações e próximos passos

- **Sem API do jogo**: resultados são manuais por definição do projeto.
- “Um jogador por rodada” é garantido por algoritmo + validação + testes, não por constraint SQL.
- Gols limitados a 30 também no banco; aumentar exige migração.
- Não há verificação de email nem notificações automáticas — a recuperação de senha é o único
  email transacional e o admin resolve o resto pela interface.
- Se o refresh token for roubado por um XSS que consiga executar na origem, ainda é possível agir
  na sessão (o CSRF não protege contra script na própria origem); a mitigação é a CSP estrita e a
  rotação/blacklist do refresh.
- Possíveis evoluções: múltiplas temporadas na UI, histórico de confrontos, exportação da tabela,
  painel de auditoria no frontend e notificações por email/WhatsApp.

---

## Aviso legal

Este é um projeto independente, sem fins lucrativos, criado para uso entre amigos. Não possui
qualquer vínculo, afiliação ou endosso da Konami Digital Entertainment. “eFootball” é marca
registrada de seus respectivos proprietários e é citada apenas para identificar o jogo ao qual a
liga se refere.
