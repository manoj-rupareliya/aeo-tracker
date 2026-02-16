# Deployment Guide for llmscm.com

## Overview

llmscm.com consists of two main components:
- **Frontend**: Next.js 14 app deployed to Vercel
- **Backend**: FastAPI + Celery deployed to Railway/Render/Fly.io

---

## Frontend Deployment (Vercel)

### Step 1: Prepare Repository

Ensure your repository structure is correct:
```
llmscm/
├── frontend/           # Next.js app (deploy this folder)
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── package.json
│   ├── vercel.json
│   └── ...
├── backend/
└── ...
```

### Step 2: Connect to Vercel

1. Go to [vercel.com](https://vercel.com) and sign in
2. Click "Add New Project"
3. Import your Git repository
4. **Important**: Set the root directory to `frontend`
   - Click "Root Directory" and select `frontend`

### Step 3: Configure Environment Variables

In Vercel project settings, add these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | `https://api.llmscm.com` |

### Step 4: Deploy

Click "Deploy". Vercel will automatically:
- Install dependencies
- Run `npm run build`
- Deploy to global CDN

### Step 5: Custom Domain (Optional)

1. Go to Project Settings > Domains
2. Add your custom domain (e.g., `llmscm.com`)
3. Configure DNS with provided records

---

## Backend Deployment (Railway)

### Step 1: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Create new project
3. Add PostgreSQL and Redis from marketplace

### Step 2: Deploy API

1. Click "Add New Service"
2. Select "GitHub Repo"
3. Configure:
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Step 3: Environment Variables

Set these in Railway:

```bash
# Application
APP_ENV=production
DEBUG=false
SECRET_KEY=your-strong-secret-key

# Database (Railway provides this)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Redis (Railway provides this)
REDIS_URL=${{Redis.REDIS_URL}}

# JWT
JWT_SECRET_KEY=your-jwt-secret-key

# LLM API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
PERPLEXITY_API_KEY=pplx-...

# Celery
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}

# CORS
CORS_ORIGINS=https://llmscm.com,https://www.llmscm.com
```

### Step 4: Deploy Celery Worker

1. Add another service
2. Same repo, but different start command:
   - Start Command: `celery -A app.workers.celery_app worker --loglevel=info`

### Step 5: Deploy Celery Beat (Scheduler)

1. Add another service
2. Same repo, but different start command:
   - Start Command: `celery -A app.workers.celery_app beat --loglevel=info`

---

## Alternative: Docker Compose (Self-Hosted)

For self-hosted deployments, use Docker Compose:

```yaml
version: '3.8'

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://llmscm:password@db:5432/llmscm
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      - db
      - redis
    restart: always

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.workers.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://llmscm:password@db:5432/llmscm
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      - db
      - redis
    restart: always

  beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.workers.celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://llmscm:password@db:5432/llmscm
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    depends_on:
      - redis
    restart: always

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
    depends_on:
      - api
    restart: always

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=llmscm
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=llmscm
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: always

volumes:
  postgres_data:
  redis_data:
```

---

## Database Migrations

After deployment, run database migrations:

```bash
# SSH into API service or run via Railway CLI
python -c "from app.utils import init_db; import asyncio; asyncio.run(init_db())"
```

---

## Health Checks

### API Health Check
```
GET /health
Response: {"status": "healthy", "version": "2.0.0"}
```

### Frontend Health Check
```
GET /api/health
Response: {"status": "ok"}
```

---

## Monitoring (Recommended)

1. **Sentry** - Error tracking
   - Add `SENTRY_DSN` to environment variables

2. **Vercel Analytics** - Frontend performance
   - Enable in Vercel dashboard

3. **Railway Metrics** - Backend performance
   - Built into Railway dashboard

---

## Post-Deployment Checklist

- [ ] API responds at production URL
- [ ] Frontend loads correctly
- [ ] Authentication works (login/register)
- [ ] LLM queries execute successfully
- [ ] Celery workers processing tasks
- [ ] CORS configured correctly
- [ ] SSL certificates active
- [ ] Database backups scheduled
- [ ] Error monitoring active
- [ ] Custom domain configured

---

## Troubleshooting

### "CORS error" on frontend
- Ensure `CORS_ORIGINS` includes your frontend domain
- Check for trailing slashes in URLs

### "Database connection failed"
- Verify `DATABASE_URL` format
- Check PostgreSQL is running and accessible

### "Celery tasks not processing"
- Check Redis connection
- Verify worker service is running
- Check `CELERY_BROKER_URL` is correct

### "LLM queries failing"
- Verify API keys are set correctly
- Check rate limits on LLM providers
- Look for error logs in worker service

---

## Scaling

### Horizontal Scaling
- Frontend: Vercel handles automatically
- API: Add more Railway service instances
- Workers: Add more Celery worker instances

### Vertical Scaling
- Increase Railway service resources
- Upgrade PostgreSQL plan
- Upgrade Redis plan

---

## Security Checklist

- [ ] All API keys stored as environment variables
- [ ] `DEBUG=false` in production
- [ ] Strong `SECRET_KEY` and `JWT_SECRET_KEY`
- [ ] HTTPS enabled everywhere
- [ ] Rate limiting configured
- [ ] CORS restricted to specific origins
- [ ] Database not publicly accessible
