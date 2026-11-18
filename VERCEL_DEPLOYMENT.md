# Manual Vercel deployment and PostgreSQL setup

This repository does not contain a Vercel auto-deployment workflow. **Deploy manually** using the Vercel CLI. Keep the Vercel project unlinked from GitHub to prevent automatic deployments on push.

## Provision PostgreSQL first

Create a persistent managed PostgreSQL database, such as Neon. Set its **direct connection URL** as `DATABASE_URL` in the Vercel **Production** environment. Example:

`postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require`

Use TLS, URL-encode password characters, and ensure the database role has schema creation rights and permission for `btree_gist` (needed for the room-overlap exclusion constraint). The database server must already exist; migrations create the application's tables.

Set `JWT_SECRET` to a random secret at least 32 characters long. Optionally set `CORS_ORIGINS` to a JSON array of trusted frontend origins. Keep all credentials in Vercel environment settings, not in Git.

## Link a manual deployment project

```bash
npm install -g vercel
vercel login
vercel link
```

Decline the Git repository connection prompt. If you previously connected the project to Git, disconnect it in **Project Settings > Git**. GitHub Actions in this repository runs tests only.

## Deploy to production

```bash
vercel --prod
```

`vercel.json` runs `python scripts/vercel_build.py` during the build. The script installs dependencies and runs `alembic upgrade head` **only for production deployments**. This creates or upgrades PostgreSQL tables before the deployment succeeds. A failed migration stops the build; preview deployments never run migrations. The production environment variables must be available during build and runtime.

**Caution:** migrations change the production database before the new deployment is live. Make future migrations backward-compatible with the currently running API. This is appropriate for a portfolio MVP, not a zero-downtime migration orchestration system. Never migrate on each serverless request or function cold start.

## Verify

Open `/docs` for Swagger and `/health/ready` to verify PostgreSQL connectivity. Existing database data persists across redeployments. Use the CLI to create an admin account against the same database from a secure local environment; do not expose a public create-admin endpoint.

## Database operations

Use a managed provider with backups, TLS, and connection limits. For higher traffic, use connection pooling supported by your provider. Keep the direct connection available for migrations, and configure a pooled URL separately for runtime if necessary.