# Vercel Setup Guide

## Fixing 401 Unauthorized Errors

The 401 errors on preview deployment URLs are caused by **Vercel Deployment Protection**, which is a
dashboard-only setting — it cannot be disabled via `vercel.json`.

### Step 1 — Disable Deployment Protection

1. Go to your project in the [Vercel Dashboard](https://vercel.com/dashboard)
2. Navigate to **Settings → Deployment Protection**
3. Set protection to **None** (or configure a bypass secret if you want protection for some routes)
4. Click **Save**

Redeploy after changing this setting.

### Step 2 — Required Environment Variables

Set these in **Vercel Dashboard → Settings → Environment Variables** (or via `vercel env add`):

| Variable | Description | Required |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL | Yes |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Your Supabase anon/public key | Yes |

Both variables must be set for **Production**, **Preview**, and **Development** environments.

### Step 3 — Verify the Deployment

After disabling protection and setting env vars, check these endpoints:

```bash
# Should return: {"ok":true}
curl https://your-deployment-url.vercel.app/api/health

# Should load the login page (not redirect to Vercel auth)
curl -I https://your-deployment-url.vercel.app/login
```

### How App Auth Works

- `/login` and `/auth/*` — public, no Supabase session required
- `/api/health` — public, always returns `{"ok":true}`
- `/api/auth/*` — public, used by auth callbacks
- All other routes — redirect to `/login` if no active Supabase session

The auth flow uses Supabase magic links. After clicking the email link, users are redirected
to `/auth/callback` which exchanges the code for a session and redirects to `/dashboard`.
