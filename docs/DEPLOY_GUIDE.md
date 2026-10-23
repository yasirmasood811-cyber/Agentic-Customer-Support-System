# Deploying to free cloud hosts (the `deploy` branch)

This guide puts the app online with free plans: **Neon** (database), **Brevo** (email), **Render** (backend), **Vercel** (frontend). The `main` branch is not touched; everything here lives on the `deploy` branch.

```
Browser  ->  Vercel (React)  ->  Render (FastAPI + agents)  ->  Neon (PostgreSQL)
                                        |-> Gemini API (LLM + embeddings)
                                        |-> Brevo API (emails)
                                        |-> Stripe (test mode)
```

Free plans change often. If a button or limit differs from this guide, trust the provider's page.

## What is different from `main`

| File | Change |
|---|---|
| `backend/app/config.py` | New settings; a `postgresql://` link from Neon is fixed automatically |
| `backend/app/tools/email_tools.py` | Sends through the Brevo API when `BREVO_API_KEY` is set (free hosts block Gmail SMTP). Gmail SMTP still works when it is empty |
| `backend/app/rag/vectorstore.py`, `ingest.py`, `backend/app/tools/kb_tools.py` | Gemini embeddings and an in-memory store (no torch, no chromadb), built when the server starts |
| `backend/app/main.py` | Builds the knowledge base at startup |
| `backend/requirements-deploy.txt` (new) | Small dependency list for the cloud build |
| `backend/.env.example`, `README.md`, `docs/DEPLOY_GUIDE.md` | Documentation |

## 1. Create the `deploy` branch
In the project folder (where `README.md` is):
```
git checkout main
git pull
git checkout -b deploy
```
Copy the files from the deploy zip over your project (overwrite when asked). Then:
```
git status
```
Only the files in the table above should appear as modified or new. Check that no `.env` is listed, then:
```
git add .
git commit -m "Deployment changes"
git push -u origin deploy
```
Switch back any time with `git checkout main` (nothing from `deploy` is in it).

## 2. Database: Neon
1. Sign up at neon.com and create a project (any name, region near you).
2. Open **Connection details** and copy the connection string (it starts with `postgresql://`). Keep it private.
3. **Fill the database once from your laptop.** In PowerShell, in `backend/` with your venv active:
   ```
   $env:DATABASE_URL = "PASTE_THE_NEON_STRING_HERE"
   python -m app.db.seed
   ```
   It should print `Seeded 3 customers and 5 orders.` (Tables are also created by the server itself.)
4. The seed emails (`ali@example.com`...) do not exist. Open the **SQL Editor** in Neon and give the demo customers real inboxes you can open:
   ```sql
   UPDATE customers SET email = 'yourname+ali@gmail.com'  WHERE id = 1;
   UPDATE customers SET email = 'yourname+sara@gmail.com' WHERE id = 2;
   ```
   (Each email must be different. Gmail delivers `+alias` addresses to your own inbox.)

## 3. Email: Brevo
1. Sign up at brevo.com (the free plan needs no card, 300 emails a day).
2. **Senders, Domains & Dedicated IPs** -> **Senders** -> add a sender: use an address whose inbox you can open (for example your Gmail), and click the confirmation link Brevo emails you. Emails are only sent from a verified sender.
3. **SMTP & API** -> **API keys** -> create a key and copy it.
4. Values you will need later: `BREVO_API_KEY` (the key) and `EMAIL_SENDER` (the verified address).

Note: a free Gmail address as sender can make some mail providers put the message in spam. Check the spam folder during tests. A company domain avoids this.

## 4. Backend: Render
1. Sign up at render.com with your GitHub account. **New** -> **Web Service** -> choose your repository.
2. Settings:
   - **Branch:** `deploy`
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements-deploy.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance type:** Free
   - **Health Check Path** (under Advanced): `/api/health`
3. **Environment Variables** (type the value without quotes):

| Name | Value |
|---|---|
| `GOOGLE_API_KEY` | your Gemini key |
| `LLM_MODEL` | the Gemini model your key can use (see the rate-limit page in AI Studio) |
| `DATABASE_URL` | the Neon connection string |
| `STRIPE_SECRET_KEY` | your `sk_test_...` key (test keys only; live keys are refused) |
| `ADMIN_PASSWORD` | a strong password for the admin page |
| `SUPPORT_TEAM_EMAIL` | inbox for new-ticket alerts |
| `BREVO_API_KEY` | the Brevo key |
| `EMAIL_SENDER` | the verified Brevo sender |
| `CORS_ORIGINS` | the Vercel address (add it in step 6) |

`EMBEDDINGS_PROVIDER`, `VECTOR_STORE` and `GEMINI_EMBEDDING_MODEL` already have the right defaults for the cloud.

4. Press **Create Web Service**. The first build takes a few minutes. When it is live, open `https://YOUR-SERVICE.onrender.com/api/health`. It should show `{"status":"ok"}`.

## 5. Frontend: Vercel
1. Sign up at vercel.com with GitHub. **Add New** -> **Project** -> import the repository.
2. **Root Directory:** `frontend`. Framework: Vite (detected). Build `npm run build`, output `dist`.
3. **Environment Variables:** `VITE_API_URL` = the Render address (no `/` at the end). This holds no secret.
4. Deploy. Then make `deploy` the **Production Branch**: Project **Settings** -> **Git** (or **Environments** -> **Production** -> branch tracking) -> `deploy`, and redeploy. (Preview deployments can ask visitors to log in to Vercel, so the production address is the one to share.)
5. Your demo link is the Vercel address. Admin: the same address with `/#admin` at the end.

## 6. Connect the two
Back in Render, set `CORS_ORIGINS` to the Vercel address, for example `https://your-project.vercel.app` (no `/` at the end). Render redeploys by itself.

## 7. Test (in this order)
1. Open the Vercel link. The first message can take **30-60 seconds** (the free Render server sleeps).
2. Ask `Refund policy kya hai?` (tests Gemini and the knowledge base).
3. Ask about an order of the customer whose email you changed. Check the inbox (and spam) for the code, type it, and see the order card.
4. Open `/#admin`, log in, and add or update something.

## 8. Things to know about free plans
- **Sleeping server:** after about 15 minutes without visits Render stops the service; the next visit waits 30-60 seconds. Open the site a few minutes before a demo or a viva.
- **Gemini daily limit:** when it is used up the bot cannot answer. Keep a recorded demo video as a backup.
- **Chats and codes live in memory:** a restart or a new deploy clears conversations and verification sessions.
- **Neon sleeps** after a few idle minutes and wakes up on the next request.
- **Brevo:** emails only leave from the verified sender, at most 300 a day.
- **No customer login:** the link is public, so share it only with the people who must see it. Orders are protected by the emailed code, but anyone can ask for a code and use up your Gemini quota.

## 9. Updating
Push to the `deploy` branch (`git push`). Render and Vercel rebuild by themselves. Changing an environment variable on Render also redeploys it.

## 10. When something fails

| Problem | Check |
|---|---|
| Render build fails | Open the **Logs**. The root directory must be `backend` and the build command must use `requirements-deploy.txt`. If Python itself is the problem, set a `PYTHON_VERSION` environment variable such as `3.12.7` |
| Chat says it cannot reach the server | `VITE_API_URL` is wrong (it must start with `https://` and have no `/` at the end). After changing it, redeploy Vercel, because the value is built into the page |
| Browser console shows a CORS error | `CORS_ORIGINS` on Render does not match the Vercel address exactly |
| No emails arrive | Look at the Render logs for `Email failed: Brevo answered ...`. 401 means a wrong key; 400 often means the sender is not verified. Check spam too |
| `AI service is busy or its free limit is reached` | Gemini quota. Wait, or use another model in `LLM_MODEL` |
| The knowledge base does not answer | Render logs show `[knowledge base] could not be prepared: ...` when `GOOGLE_API_KEY` or the embedding model is wrong. Fix the variable; the server rebuilds it at the next start |
| Admin says the password is not configured | `ADMIN_PASSWORD` is empty on Render |
| Customers have `example.com` emails | Run the SQL from step 2.4 |

## 11. Security
- Keys live only in the Render and Vercel dashboards and in your own `.env`. Never put them in Git, a screenshot or a chat.
- If a key leaks, make a new one at the provider and update the dashboard.
- Use only Stripe **test** keys.
