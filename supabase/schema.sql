-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- Leads table
create table leads (
  id uuid primary key default uuid_generate_v4(),
  created_at timestamptz default now(),
  updated_at timestamptz default now(),

  -- Contact info
  company_name text not null,
  contact_name text,
  phone text,
  email text,
  website text,
  address text,
  city text,
  state text,
  zip text,

  -- Business info
  service_type text,
  estimated_deal_size numeric,
  employees_count text,

  -- Pipeline
  status text not null default 'new' check (status in ('new', 'contacted', 'follow_up', 'quoted', 'closed_won', 'onboarding', 'active', 'dead')),
  priority text default 'medium' check (priority in ('low', 'medium', 'high')),

  -- Assignment
  assigned_to uuid references auth.users(id),

  -- Follow up
  next_follow_up timestamptz,

  -- Source
  source text,

  notes text,
  tags text[]
);

-- Call logs
create table call_logs (
  id uuid primary key default uuid_generate_v4(),
  created_at timestamptz default now(),
  lead_id uuid not null references leads(id) on delete cascade,
  called_by uuid references auth.users(id),

  outcome text check (outcome in ('answered', 'voicemail', 'no_answer', 'callback_scheduled', 'not_interested', 'interested', 'quoted', 'closed')),
  duration_minutes integer,
  notes text,
  next_action text,
  follow_up_date timestamptz
);

-- Onboarding checklist items
create table onboarding_tasks (
  id uuid primary key default uuid_generate_v4(),
  created_at timestamptz default now(),
  lead_id uuid not null references leads(id) on delete cascade,

  task text not null,
  completed boolean default false,
  completed_at timestamptz,
  completed_by uuid references auth.users(id),
  due_date timestamptz,
  notes text
);

-- User profiles
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  role text default 'agent'
);

-- RLS Policies
alter table leads enable row level security;
alter table call_logs enable row level security;
alter table onboarding_tasks enable row level security;
alter table profiles enable row level security;

create policy "authenticated users can do everything on leads" on leads for all to authenticated using (true) with check (true);
create policy "authenticated users can do everything on call_logs" on call_logs for all to authenticated using (true) with check (true);
create policy "authenticated users can do everything on onboarding_tasks" on onboarding_tasks for all to authenticated using (true) with check (true);
create policy "users can read all profiles" on profiles for select to authenticated using (true);
create policy "users can update own profile" on profiles for update to authenticated using (auth.uid() = id);

-- Updated_at trigger
create or replace function update_updated_at()
returns trigger as $$ begin new.updated_at = now(); return new; end; $$ language plpgsql;
create trigger leads_updated_at before update on leads for each row execute function update_updated_at();
