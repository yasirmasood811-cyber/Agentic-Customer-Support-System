# ShopEase: Agentic AI Customer Support System

An AI support assistant that does more than chat. It understands a customer's message, finds answers in a company knowledge base (RAG), and performs real actions: it checks orders, issues refunds (Stripe test mode), updates records and sends emails. Routine cases are handled without a human. Complex or sensitive cases are escalated to a human agent as a ticket with full context.

> Author: `<your name>`  |  Course: `<course name>`  |  Final project

## 1. The problem

Support teams spend most of their time on routine questions (order status, refunds, policies). Customers want instant answers at any hour. A normal chatbot only talks; it cannot check an order or issue a refund. Human agents then repeat the same work.

This project builds an agent that **acts**: it looks up real data, performs allowed actions with safety limits, and hands over to a human when it should.

## 2. What it can do

| Capability | How |
|---|---|
| Answer policy / FAQ questions | RAG over the company documents (ChromaDB + local embeddings) |
| Verify the customer (email code) | Before any order action the customer types a 6-digit code that is emailed to the address on the order. Order tools then work only for that customer's own orders |
| Check order status | `get_order_status` reads PostgreSQL |
| Refund an order | `process_refund` refunds the order's Stripe test payment (orders added from the Admin page keep their own payment), with limits enforced in code |
| Update address / phone | `update_record`, only while the order is still processing |
| Send confirmation emails | Email Agent sends via Gmail SMTP after a successful refund or update |
| Escalate to a human | Escalation Agent creates a ticket with a full summary and emails the support team |
| Check a ticket's status | `check_ticket_status` needs the ticket number and the matching email |
| Remember the conversation | LangGraph checkpointer keeps history per `thread_id` |
| Admin page | Login, ticket list, reply to the customer by email, orders list, add orders and customers |
| Understands English, Urdu and Roman Urdu | Agents reply in the customer's style |

## 3. Architecture

![Architecture](docs/architecture.png)

```mermaid
flowchart TD
  U[Customer chat - React] -->|POST /api/chat SSE| API[FastAPI]
  A[Admin page - React] -->|token| API
  API --> G[LangGraph]
  G --> R{Router}
  R -->|policy or FAQ| K[Knowledge Agent]
  R -->|order, refund, ticket status| AC[Action Agent]
  R -->|angry, human, legal| E[Escalation Agent]
  AC -->|refund or update done| EM[Email Agent]
  AC -->|refund above 200 USD| E
  K --> KB[(ChromaDB)]
  AC --> DB[(PostgreSQL)]
  AC --> ST[Stripe test mode]
  EM --> SMTP[Gmail SMTP]
  E --> DB
  E --> SMTP
```

### The agents

| Agent | Job | Tools |
|---|---|---|
| **Router** (LangGraph node, structured output) | Decides which agent handles the message | none |
| **Knowledge Agent** | Answers only from the knowledge base | `search_knowledge_base` |
| **Action Agent** | Identity check, order status, refunds, record updates, ticket status | `request_verification`, `confirm_verification`, `get_order_status`, `process_refund`, `update_record`, `check_ticket_status` |
| **Email Agent** | Confirmation email after a successful action | `send_email` |
| **Escalation Agent** | Creates a ticket for a human | `escalate_to_human` |

### Decisions made by code, not by the LLM

LLMs can make mistakes, so the important rules are enforced in code:

- After the Action Agent, **code** checks the tool results: a successful refund or update goes to the Email Agent; a refund above the limit goes to the Escalation Agent.
- `process_refund` refuses: amounts above **200 USD** (needs a human), orders that are not *delivered* or *cancelled*, orders already refunded, and amounts above the order total. A full refund sets the order status to *refunded*.
- `update_record` only changes `shipping_address` (while the order is *processing*) or `phone`. Email changes are refused.
- `escalate_to_human` creates no ticket unless there is an order on record or a valid email, so a human can always reach the customer.
- `check_ticket_status` reveals nothing unless the ticket number and email both match.
- **Identity check (email code):** `get_order_status`, `process_refund` and `update_record` refuse to run unless this conversation is verified, and they only accept orders that belong to the verified customer. Someone else's order looks exactly like an order that does not exist. Who is verified is kept on the server per conversation id (`thread_id`); the LLM cannot claim it.
- `send_email` only sends to the verified customer's own address, and `escalate_to_human` links a ticket to an order only for a verified owner.

### Data flow of one chat message

1. React sends the message and a `thread_id` to `POST /api/chat`.
2. FastAPI runs the LangGraph and streams events (Server-Sent Events): `start`, `route`, `agent`, `tool`, `escalation`, `status`, `message`, `error`, `done`.
3. React shows a live indicator ("Checking your order...") from the `route` event, turns `tool` results into cards, shows an escalation banner with the ticket number, then types out the final reply.
4. If the AI service answers 503 or 429, the backend retries up to 3 times and resumes from the last checkpoint.

## 4. Tech stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini through `langchain-google-genai` (free API key) |
| Agent framework | LangChain (tools, retriever) + LangGraph (routing, state, memory) |
| RAG | ChromaDB, `sentence-transformers/all-MiniLM-L6-v2` (local, no key), `RecursiveCharacterTextSplitter` (500 characters, 80 overlap), top 3 chunks |
| Database | PostgreSQL via SQLAlchemy (tables: `customers`, `orders`, `tickets`) |
| Backend | FastAPI, Pydantic, Uvicorn |
| Frontend | React 18 + Vite (plain CSS, light and dark mode) |
| Email | Gmail SMTP with an App Password |
| Payments | Stripe, **test mode only** |
| Tracing (optional) | LangSmith, enabled with the `LANGSMITH_*` values in `.env` |

## 5. Project structure

```
support-agent/
├── README.md
├── docs/
│   ├── architecture.svg / architecture.png
│   ├── DEMO_SCRIPT.md            demo scenarios + viva questions
│   └── PGADMIN_GUIDE.md          using pgAdmin with this project
├── backend/
│   ├── requirements.txt
│   ├── .env.example              copy to .env and fill in
│   ├── try_api.py                quick API test from the terminal
│   └── app/
│       ├── main.py               FastAPI app and endpoints
│       ├── streaming.py          graph -> Server-Sent Events, retries
│       ├── graph.py              LangGraph: router, edges, memory
│       ├── auth.py               admin login (token, rate limit)
│       ├── notifications.py      emails about tickets and verification codes
│       ├── verification.py       email-code (OTP) identity check
│       ├── payments.py           Stripe test-mode helpers (create payment, refund)
│       ├── config.py, schemas.py, chat_cli.py
│       ├── agents/               knowledge, action, email_agent, escalation, llm
│       ├── tools/                kb_tools, order_tools, email_tools, ticket_tools, verify_tools
│       ├── rag/                  ingest.py, vectorstore.py, docs/*.txt (knowledge base)
│       └── db/                   database.py, models.py, seed.py, migrate.py
└── frontend/
    ├── package.json, vite.config.js, index.html
    └── src/
        ├── App.jsx, api.js, cards.js, ErrorBoundary.jsx, styles.css
        └── components/           ChatWindow, ActionCard, AdminPanel
```

## 6. Setup (Windows, step by step)

You need: **Python 3.10+**, **Node.js 18+**, **PostgreSQL** (with pgAdmin or the SQL Shell), and a code editor.

### 6.1 Get the keys

| What | Where | Used for |
|---|---|---|
| Gemini API key | https://aistudio.google.com, "Get API key" (free) | all agents |
| Stripe test key (`sk_test_...`) | Stripe dashboard, Test mode, Developers, API keys | refunds |
| Gmail App Password | Google Account, Security, 2-Step Verification on, then App passwords | emails |

Never use a live Stripe key (`sk_live_`), and never share or commit your `.env`.

### 6.2 Create the database

Open **SQL Shell (psql)** as the `postgres` user and run:

```sql
CREATE USER support_user WITH PASSWORD 'support123';
CREATE DATABASE support OWNER support_user;
```

### 6.3 Backend

```powershell
cd backend
python -m venv venv
venv\Scripts\activate            # PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env           # then edit .env (see the table below)
python -m app.db.seed            # creates tables + demo customers and orders
python -m app.rag.ingest         # builds the knowledge base (first run downloads a ~90 MB model)
uvicorn app.main:app --reload --port 8000
```

Check http://localhost:8000/api/health, it should return `{"status":"ok"}`. API docs: http://localhost:8000/docs

### 6.4 Frontend (a second terminal, no venv needed)

```powershell
cd frontend
npm install
npm run dev
```

- Customer chat: http://localhost:5173
- Admin page: http://localhost:5173/#admin (the customer page shows no admin tab)

### 6.5 The `.env` file (`backend/.env`)

| Variable | Meaning |
|---|---|
| `GOOGLE_API_KEY` | Gemini API key |
| `LLM_MODEL` | Gemini model name. Choose one available to your key with enough free requests per day (see the rate-limit page in AI Studio) |
| `DATABASE_URL` | `postgresql+psycopg2://support_user:support123@localhost:5432/support` |
| `SMTP_EMAIL`, `SMTP_APP_PASSWORD` | Gmail address and its App Password (not the normal password) |
| `SUPPORT_TEAM_EMAIL` | Inbox that gets an email for every new ticket (empty = off) |
| `ADMIN_PASSWORD` | Password for the admin page (empty = admin disabled) |
| `STRIPE_SECRET_KEY` | Stripe **test** secret key |
| `CORS_ORIGINS` | Optional. Only if the frontend runs on another address |
| `LANGSMITH_*` | Optional tracing |

### 6.6 Demo data

`python -m app.db.seed` creates:

| Order | Item | Amount | Status | Customer |
|---|---|---|---|---|
| 1001 | Wireless Earbuds | $45 | shipped | Ali Khan |
| 1002 | Phone Case | $12 | delivered | Ali Khan |
| 1003 | Laptop Stand | $30 | processing | Sara Ahmed |
| 1004 | Smart Watch | $250 | delivered | Sara Ahmed |
| 1005 | Bluetooth Speaker | $60 | cancelled | Usman Raza |

The seed emails end in `@example.com` and do not exist. To receive the emails yourself, change them in the database:

```sql
UPDATE customers SET email = 'your_inbox@gmail.com' WHERE id = 1;
UPDATE tickets   SET contact_email = 'your_inbox@gmail.com' WHERE customer_id = 1;
```

Emails must be unique per customer. Gmail delivers `yourname+sara@gmail.com` to the same inbox.

New orders and customers can be added without SQL: open the Admin page, **Orders** tab, **+ Add order**. By default this also creates a **Stripe test payment** for the order and stores its id (shown in the Payment column), so a later refund from the chat refunds that payment. If Stripe is not reachable the order is still saved and a yellow warning is shown; the seed orders (1001 to 1005) have no payment of their own. For everything else in pgAdmin see [docs/PGADMIN_GUIDE.md](docs/PGADMIN_GUIDE.md).

## 7. API

| Method and path | Access | Purpose |
|---|---|---|
| `GET /api/health` | public | server check |
| `POST /api/chat` | public | chat, streamed as Server-Sent Events |
| `POST /api/admin/login`, `POST /api/admin/logout` | public / token | admin session |
| `GET /api/tickets` | admin | list tickets |
| `PATCH /api/tickets/{id}` | admin | set status, store a message, optionally email the customer |
| `GET /api/orders` | admin | list orders |
| `POST /api/orders` | admin | add an order (for an existing customer or a new one) and, unless switched off, a Stripe test payment; ids are assigned by the server |
| `GET /api/customers` | admin | list customers (used by the Add order form) |

## 8. Security notes

- Admin endpoints need a login token (valid 8 hours, kept in server memory). 5 wrong passwords block that IP for 5 minutes. Without `ADMIN_PASSWORD` the admin is disabled instead of open.
- Customer-facing tools never show another customer's data: ticket status needs both ticket number and email, and order tools need a verified conversation.
- **Email code details:** 6 digits, stored only as a salted hash, valid 10 minutes, single use, 5 wrong tries per code. A verified chat stays verified for 30 minutes. At most 3 codes per customer and per chat in 15 minutes, and 10 wrong codes per customer in an hour lock verification for that customer for an hour. Asking for a code for an order number that does not exist gives the same answer as for a real one, so order numbers cannot be probed.
- Secrets stay in `.env`, which is in `.gitignore`. Stripe is in test mode only, and the code refuses any key that does not start with `sk_test_` or `rk_test_`.
- Email subjects are cleaned of line breaks to prevent header injection.

## 9. Known limitations and future work

- Conversation memory and admin tokens live in server memory, so a restart clears them. Use a database-backed checkpointer and signed tokens for production.
- The email a customer types for a ticket is not verified. Production should send a verification code.
- The email code proves that someone can read the inbox of the order's email address. It is not a website login. Codes and verified chats live in server memory (a restart clears them), the chat endpoint has no per-IP rate limit yet, and anyone who steals a chat's `thread_id` during its 30 verified minutes could act as that customer.
- Orders made in the Admin page store the id of their Stripe test payment and refunds use it. The seed orders have no payment on record, so for them the refund tool first creates a test payment and then refunds it (a shortcut for the demo). In a real shop the payment comes from the checkout, not from the support system.
- The 7-day refund window from the policy text is not checked in code (orders have no delivery date).
- The free Gemini tier has small daily limits. The app retries on 503/429 but cannot work around a used-up quota.
- The full list of what to change before using this on a real website is in section 10.

## 10. Moving to a real website (future work)

The architecture (router + specialised agents, business rules inside the tools, RAG, streaming, ticket flow) can stay. What must change is mostly **identity, security and infrastructure**. This is the order I would work in.

### 10.1 Must do before going live

| Area | Prototype today | For a real website |
|---|---|---|
| **Customer identity** (most important) | An email code per chat proves ownership of an order; the tools check `order.customer_id` against the verified customer | Chat only for **logged-in customers**. The backend takes the customer id from the website session and passes it to the tools (the same ownership check as today, but without asking for codes). Guests get only the Knowledge Agent, or the email code. Never trust an id typed in the chat or chosen by the LLM. |
| **Real shop data** | Seeded demo orders in PostgreSQL | Connect the tools to the shop's own orders system (own API, Shopify, WooCommerce). Tool names and rules stay, only the data source changes. |
| **Payments** | Orders added in the admin page store their Stripe test payment id and are refunded on it; seed orders use a create-then-refund shortcut | The PaymentIntent id comes from the real checkout and is stored on every order; refund that payment. Live key only in a secret manager. Use an idempotency key so a double click cannot refund twice. Check the delivery date and the 7-day window in code. |
| **Admin access** | One shared password, tokens in server memory | A separate admin site/subdomain, one account per staff member, roles, 2FA, signed tokens or secure cookies, an audit log of every action. |
| **Email** | Personal Gmail account and App Password | A transactional service (SendGrid, Amazon SES, Resend) on the company domain with SPF/DKIM. Keep the rule that confirmation emails go only to the verified customer (already enforced in code). Verify a customer's email with an OTP before attaching it to a ticket. |
| **Abuse and cost** | No limits on `/api/chat` | Rate limits per user and IP, message size limits, CAPTCHA for guests, a monthly LLM budget with alerts. Treat all customer text and knowledge-base text as untrusted (prompt injection): permissions are decided by code, never by the model. |
| **Transport and secrets** | `http://localhost`, `.env` file | HTTPS, secrets in a cloud secret manager, CORS limited to the shop's domain. |

### 10.2 Soon after launch

| Item | Today | Better |
|---|---|---|
| Conversation memory | In-memory `MemorySaver` (lost on restart) | PostgreSQL checkpointer, so restarts and several servers work |
| Admin tokens, login rate limit | In memory | Redis or signed tokens |
| Schema changes | Small `ensure_columns` helper | Alembic migrations |
| Sending emails | Inside the request (adds 1-2 seconds) | Background queue (Celery or RQ) |
| LLM | Free tier with a daily limit | Paid plan, plus a second provider as fallback |
| Knowledge base | Files plus a manual `ingest` command | Upload page for staff, automatic re-ingest, managed vector database |
| Testing | Manual demo script | Automated tests, a router-accuracy test set, security tests |

### 10.3 Putting the chat on the shop's site

- Turn the chat page into a **floating widget** or a component inside the shop's React app, and pass the shop's login token to the API.
- Build with `npm run build`, serve the static files from a CDN or Nginx, and set `VITE_API_URL` to the real API domain.
- Add real token-by-token streaming (today the whole reply arrives at once and the typing effect is drawn in the browser), proper branding, mobile and accessibility checks.

### 10.4 Deployment

- Docker images for backend and frontend, a reverse proxy (Nginx or Caddy), managed PostgreSQL, and a host such as Render, Railway, AWS or Azure.
- Keep proxy buffering off and timeouts long for streaming (the app already sends `X-Accel-Buffering: no`).
- CI/CD (for example GitHub Actions) that runs the tests, a staging environment, and monitoring (Sentry, logs, LangSmith). Plan memory for the embedding model (a few hundred MB).

### 10.5 Product features still missing

- Cancel-order tool, return flow (goods coming back), a separate `partially_refunded` status, and a delivery-date check for refunds.
- Real courier tracking, several currencies (USD is fixed today), and a multi-language knowledge base.
- Live chat hand-over to a human agent (today: ticket plus email), ticket assignment and an SLA timer.
- Tell customers they are talking to an AI. Traces and logs contain customer data, so define what is stored and for how long, and check the data-protection rules that apply where the shop operates.

### 10.6 Suggested phases

1. **Safe MVP:** customer login with ownership checks in every tool, live Stripe done properly, admin accounts, recipient lock for emails, rate limits, HTTPS, PostgreSQL memory, paid LLM plan.
2. **Integration:** real order system, background email queue, Docker and CI/CD, chat widget.
3. **Growth:** live hand-over, cancel and return flows, evaluation dashboard, more languages.

The single most important lesson: **authorization must live in code, not in the prompt.** The LLM decides what to say and which tool to try; the tool decides whether the logged-in customer is allowed to do it.

## 11. Demo and viva

See [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) for a step by step demo and likely questions with answers.
