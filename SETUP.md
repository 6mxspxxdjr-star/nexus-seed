# LeadFlow Setup Guide

## 1. Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign in (or create an account)
2. Click **New project**
3. Choose your organization, enter a project name (e.g. "leadflow"), set a strong database password, and choose a region close to you
4. Wait ~2 minutes for the project to spin up

## 2. Run the Schema

1. In your Supabase dashboard, go to **SQL Editor** (left sidebar)
2. Click **New query**
3. Copy and paste the entire contents of `supabase/schema.sql`
4. Click **Run** (or press Cmd+Enter)
5. You should see "Success. No rows returned."

## 3. Configure Authentication

1. In Supabase dashboard, go to **Authentication → URL Configuration**
2. Add your site URL (e.g. `https://your-app.vercel.app` or `http://localhost:3000`)
3. Under **Redirect URLs**, add:
   - `https://your-app.vercel.app/auth/callback`
   - `http://localhost:3000/auth/callback`

## 4. Get Your API Keys

1. In Supabase dashboard, go to **Project Settings → API**
2. Copy:
   - **Project URL** (e.g. `https://abcdefghijkl.supabase.co`)
   - **anon/public** key

## 5. Set Environment Variables

Update `.env.local` with your real values:

```
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key_here
```

## 6. Run Locally

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). You'll be redirected to the login page. Enter your email to get a magic link.

## 7. Deploy to Vercel

1. Push this repo to GitHub
2. Go to [vercel.com](https://vercel.com) and click **New Project**
3. Import your GitHub repo
4. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
5. Click **Deploy**
6. Once deployed, update your Supabase redirect URLs with your Vercel domain

## 8. Adding Team Members (Aidan + Dylan)

LeadFlow uses **magic link authentication** — no passwords needed.

1. Go to your deployed app (or localhost)
2. Enter your team member's email on the login page
3. They'll receive a magic link in their email
4. On first login, their account is created automatically

**Create user profiles (optional display names):**

In Supabase SQL Editor, run:
```sql
-- After each person logs in for the first time, update their profile:
UPDATE profiles SET full_name = 'Aidan' WHERE id = (
  SELECT id FROM auth.users WHERE email = 'aidan@yourcompany.com'
);

UPDATE profiles SET full_name = 'Dylan' WHERE id = (
  SELECT id FROM auth.users WHERE email = 'dylan@yourcompany.com'
);
```

## Invite-only Access

To restrict access to specific emails only, you can enable email allowlisting in Supabase:
- Go to **Authentication → Policies** or use a custom sign-up hook to validate emails.
- Alternatively, just share the magic link URL only with your team — the app is still protected by Supabase auth.
