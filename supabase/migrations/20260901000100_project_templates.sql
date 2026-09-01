-- Reusable project blueprints. A template is JSON, not task rows, so it never
-- shows up on the projects page, in analytics or in a daily plan until the
-- user applies it to a new project.

create table if not exists public.project_templates (
  id uuid primary key,
  owner_id uuid not null references public.users (id) on delete cascade,
  name varchar(80) not null,
  description varchar(300),
  icon varchar(8),
  preset_key varchar(40),
  budget_mode varchar(16) not null default 'ROLLUP',
  fixed_budget_seconds integer,
  default_estimated_seconds integer,
  default_repeat_rule varchar(16),
  structure json not null default '[]'::json,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  constraint ck_project_templates_fixed_budget_seconds
    check (fixed_budget_seconds is null or fixed_budget_seconds >= 0),
  constraint ck_project_templates_default_estimated_seconds
    check (default_estimated_seconds is null or default_estimated_seconds >= 0)
);

create index if not exists ix_project_templates_owner_sort
  on public.project_templates (owner_id, sort_order);

alter table public.project_templates enable row level security;
alter table public.project_templates force row level security;

drop policy if exists project_templates_owner_all on public.project_templates;
create policy project_templates_owner_all on public.project_templates for all
using (owner_id = public.app_current_user_id())
with check (owner_id = public.app_current_user_id());

grant select, insert, update, delete on table public.project_templates to dayflow_app;
