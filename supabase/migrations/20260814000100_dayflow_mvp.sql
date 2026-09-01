-- DayFlow MVP schema for Supabase Auth + hosted Postgres.
-- The browser uses Supabase only for authentication. FastAPI remains the
-- trusted business layer and sets app.current_user_id for every transaction.

create extension if not exists citext;

create type public.task_status as enum (
  'TODO', 'IN_PROGRESS', 'PAUSED', 'BLOCKED', 'DONE'
);
create type public.session_status as enum ('RUNNING', 'PAUSED', 'COMPLETED');
create type public.daily_plan_item_status as enum ('TODO', 'IN_PROGRESS', 'PAUSED', 'DONE');
create type public.partnership_status as enum ('PENDING', 'ACCEPTED', 'DECLINED');
create type public.encouragement_type as enum (
  'KEEP_GOING', 'GREAT_JOB', 'WELL_DONE', 'YOU_CAN_DO_IT'
);
create type public.notification_type as enum (
  'PARTNER_INVITE', 'PARTNER_ACCEPTED', 'PLAN_SHARED', 'ENCOURAGEMENT', 'TASK_COMPLETED'
);

create table public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  email citext unique,
  phone varchar(32) unique,
  password_hash varchar(255),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index ix_users_email on public.users(email);
create index ix_users_phone on public.users(phone);

create table public.profiles (
  id uuid primary key references public.users(id) on delete cascade,
  username citext not null unique,
  display_name varchar(80) not null,
  avatar_url text,
  bio varchar(300),
  timezone varchar(64) not null default 'Asia/Shanghai',
  is_searchable boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index ix_profiles_username on public.profiles(username);

create or replace function public.app_current_user_id()
returns uuid
language sql
stable
set search_path = ''
as $$
  select nullif(current_setting('app.current_user_id', true), '')::uuid
$$;

create or replace function public.app_is_service()
returns boolean
language sql
stable
set search_path = ''
as $$
  select coalesce(current_setting('app.bypass_rls', true), '') = 'on'
$$;

create table public.tasks (
  id uuid not null,
  owner_id uuid not null references public.users(id) on delete cascade,
  parent_id uuid,
  node_type varchar(16) not null,
  title varchar(200) not null,
  priority varchar(16) not null default 'MEDIUM',
  due_date date,
  status public.task_status not null default 'TODO',
  estimated_seconds integer not null default 0,
  budget_mode varchar(16) not null default 'ROLLUP',
  fixed_budget_seconds integer,
  default_estimated_seconds integer,
  default_repeat_rule varchar(16),
  default_daily_reminder_time time,
  repeat_rule varchar(16) not null default 'NONE',
  repeat_end_date date,
  daily_reminder_time time,
  sort_order integer not null default 0,
  completed_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (id),
  constraint uq_tasks_id_owner unique (id, owner_id),
  constraint fk_tasks_parent_same_owner
    foreign key (parent_id, owner_id)
    references public.tasks(id, owner_id) on delete cascade,
  constraint ck_tasks_estimated_seconds check (estimated_seconds >= 0),
  constraint ck_tasks_fixed_budget_seconds
    check (fixed_budget_seconds is null or fixed_budget_seconds >= 0),
  constraint ck_tasks_default_estimated_seconds
    check (default_estimated_seconds is null or default_estimated_seconds >= 0),
  constraint ck_tasks_not_own_parent check (parent_id is null or parent_id <> id)
);
create index ix_tasks_owner_parent_sort on public.tasks(owner_id, parent_id, sort_order);
create index ix_tasks_owner_node_type on public.tasks(owner_id, node_type);
create index ix_tasks_owner_status on public.tasks(owner_id, status);
create index ix_tasks_owner_updated on public.tasks(owner_id, updated_at);

create table public.task_dependencies (
  task_id uuid not null,
  depends_on_task_id uuid not null,
  owner_id uuid not null,
  primary key (task_id, depends_on_task_id),
  constraint fk_task_dependencies_task_same_owner
    foreign key (task_id, owner_id)
    references public.tasks(id, owner_id) on delete cascade,
  constraint fk_task_dependencies_prerequisite_same_owner
    foreign key (depends_on_task_id, owner_id)
    references public.tasks(id, owner_id) on delete cascade,
  constraint ck_task_dependencies_not_self check (task_id <> depends_on_task_id)
);
create index ix_task_dependencies_owner_task
  on public.task_dependencies(owner_id, task_id);
create index ix_task_dependencies_owner_prerequisite
  on public.task_dependencies(owner_id, depends_on_task_id);

create table public.daily_plans (
  id uuid not null,
  owner_id uuid not null references public.users(id) on delete cascade,
  plan_date date not null,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (id),
  constraint uq_daily_plans_id_owner unique (id, owner_id),
  constraint uq_daily_plans_owner_date unique (owner_id, plan_date)
);
create index ix_daily_plans_owner_date on public.daily_plans(owner_id, plan_date);

create table public.daily_plan_items (
  id uuid primary key,
  daily_plan_id uuid not null,
  owner_id uuid not null references public.users(id) on delete cascade,
  task_id uuid references public.tasks(id) on delete set null,
  title varchar(200) not null,
  status public.daily_plan_item_status not null default 'TODO',
  estimated_seconds integer not null default 0,
  sort_order integer not null default 0,
  completed_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint fk_daily_plan_items_plan_same_owner
    foreign key (daily_plan_id, owner_id)
    references public.daily_plans(id, owner_id) on delete cascade,
  constraint ck_daily_plan_items_estimated_seconds check (estimated_seconds >= 0)
);
create index ix_daily_plan_items_plan_sort
  on public.daily_plan_items(daily_plan_id, sort_order);
create index ix_daily_plan_items_owner_updated
  on public.daily_plan_items(owner_id, updated_at);

create table public.sessions (
  id uuid primary key,
  owner_id uuid not null references public.users(id) on delete cascade,
  task_id uuid references public.tasks(id) on delete set null,
  daily_plan_item_id uuid references public.daily_plan_items(id) on delete set null,
  status public.session_status not null,
  started_at timestamptz not null,
  ended_at timestamptz,
  duration_seconds integer not null default 0,
  last_resumed_at timestamptz,
  client_id uuid not null,
  client_updated_at timestamptz not null,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ck_sessions_duration_seconds check (duration_seconds >= 0),
  constraint ck_sessions_has_subject
    check (task_id is not null or daily_plan_item_id is not null),
  constraint ck_sessions_state_timestamps check (
    (status = 'RUNNING' and last_resumed_at is not null and ended_at is null)
    or (status = 'PAUSED' and last_resumed_at is null and ended_at is null)
    or (status = 'COMPLETED' and last_resumed_at is null and ended_at is not null)
  )
);
create index ix_sessions_owner_started on public.sessions(owner_id, started_at);
create index ix_sessions_task_started on public.sessions(task_id, started_at);
create index ix_sessions_daily_item_started
  on public.sessions(daily_plan_item_id, started_at);
create index ix_sessions_owner_updated on public.sessions(owner_id, updated_at);
create unique index uq_sessions_one_active_owner on public.sessions(owner_id)
  where status in ('RUNNING', 'PAUSED') and deleted_at is null;

create table public.partnerships (
  id uuid primary key,
  requester_id uuid not null references public.users(id) on delete cascade,
  addressee_id uuid not null references public.users(id) on delete cascade,
  pair_key varchar(73) not null,
  status public.partnership_status not null default 'PENDING',
  responded_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ck_partnerships_distinct_users check (requester_id <> addressee_id)
);
create index ix_partnerships_requester_status
  on public.partnerships(requester_id, status);
create index ix_partnerships_addressee_status
  on public.partnerships(addressee_id, status);
create unique index uq_partnerships_active_pair on public.partnerships(pair_key)
  where deleted_at is null;

create table public.user_blocks (
  id uuid primary key,
  blocker_id uuid not null references public.users(id) on delete cascade,
  blocked_id uuid not null references public.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  constraint uq_user_blocks_pair unique (blocker_id, blocked_id),
  constraint ck_user_blocks_distinct_users check (blocker_id <> blocked_id)
);
create index ix_user_blocks_blocked on public.user_blocks(blocked_id);

create table public.daily_plan_shares (
  id uuid primary key,
  daily_plan_id uuid not null references public.daily_plans(id) on delete cascade,
  owner_id uuid not null references public.users(id) on delete cascade,
  partner_id uuid not null references public.users(id) on delete cascade,
  share_duration boolean not null default false,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ck_daily_plan_shares_distinct_users check (owner_id <> partner_id)
);
create index ix_daily_plan_shares_owner
  on public.daily_plan_shares(owner_id, created_at);
create index ix_daily_plan_shares_partner
  on public.daily_plan_shares(partner_id, created_at);
create unique index uq_daily_plan_shares_active_recipient
  on public.daily_plan_shares(daily_plan_id, partner_id)
  where deleted_at is null;

create table public.encouragements (
  id uuid primary key,
  share_id uuid not null references public.daily_plan_shares(id) on delete cascade,
  sender_id uuid not null references public.users(id) on delete cascade,
  receiver_id uuid not null references public.users(id) on delete cascade,
  encouragement_type public.encouragement_type not null,
  created_at timestamptz not null default now(),
  constraint ck_encouragements_distinct_users check (sender_id <> receiver_id)
);
create index ix_encouragements_share_created
  on public.encouragements(share_id, created_at);
create index ix_encouragements_receiver_created
  on public.encouragements(receiver_id, created_at);

create table public.notifications (
  id uuid primary key,
  user_id uuid not null references public.users(id) on delete cascade,
  actor_id uuid references public.users(id) on delete set null,
  notification_type public.notification_type not null,
  payload jsonb not null default '{}'::jsonb,
  read_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index ix_notifications_user_created
  on public.notifications(user_id, created_at);
create index ix_notifications_user_unread on public.notifications(user_id)
  where read_at is null;

create or replace function public.prevent_task_cycle()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.parent_id is null then
    return new;
  end if;
  if new.parent_id = new.id or exists (
    with recursive ancestors(id, parent_id) as (
      select id, parent_id from public.tasks
      where id = new.parent_id and owner_id = new.owner_id
      union all
      select task.id, task.parent_id
      from public.tasks task
      join ancestors on task.id = ancestors.parent_id
      where task.owner_id = new.owner_id
    )
    select 1 from ancestors where id = new.id
  ) then
    raise exception 'task hierarchy cannot contain a cycle' using errcode = '23514';
  end if;
  return new;
end
$$;

create or replace function public.enforce_task_node_hierarchy()
returns trigger
language plpgsql
set search_path = public
as $$
declare parent_type text;
begin
  if new.node_type = 'PROJECT' then
    if new.parent_id is not null then
      raise exception 'projects must stay at the top level' using errcode = '23514';
    end if;
    return new;
  end if;
  if new.parent_id is null then
    raise exception 'module and task nodes require a parent' using errcode = '23514';
  end if;
  select node_type into parent_type from public.tasks
  where id = new.parent_id and owner_id = new.owner_id;
  if (new.node_type = 'MODULE' and parent_type is distinct from 'PROJECT')
     or (new.node_type = 'TASK' and parent_type is distinct from 'MODULE') then
    raise exception 'invalid project/module/task hierarchy' using errcode = '23514';
  end if;
  return new;
end
$$;

create trigger tasks_prevent_cycle
before insert or update of parent_id, owner_id on public.tasks
for each row execute function public.prevent_task_cycle();
create trigger tasks_enforce_node_hierarchy
before insert or update of parent_id, owner_id, node_type on public.tasks
for each row execute function public.enforce_task_node_hierarchy();

create or replace function public.validate_session_task_owner()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.task_id is not null and not exists (
    select 1 from public.tasks
    where id = new.task_id and owner_id = new.owner_id
  ) then
    raise exception 'session task must belong to the same owner' using errcode = '23514';
  end if;
  return new;
end
$$;

create or replace function public.validate_daily_item_task_owner()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.task_id is not null and not exists (
    select 1 from public.tasks
    where id = new.task_id and owner_id = new.owner_id
  ) then
    raise exception 'daily item task must belong to the same owner' using errcode = '23514';
  end if;
  return new;
end
$$;

create or replace function public.validate_session_daily_item_owner()
returns trigger
language plpgsql
set search_path = public
as $$
declare linked_task uuid;
begin
  if new.daily_plan_item_id is not null then
    select task_id into linked_task from public.daily_plan_items
    where id = new.daily_plan_item_id
      and owner_id = new.owner_id
      and deleted_at is null;
    if not found then
      raise exception 'session daily item must belong to the same owner'
        using errcode = '23514';
    end if;
    if linked_task is distinct from new.task_id then
      raise exception 'session task must match daily item task' using errcode = '23514';
    end if;
  end if;
  return new;
end
$$;

create trigger sessions_validate_task_owner
before insert or update of task_id, owner_id on public.sessions
for each row execute function public.validate_session_task_owner();
create trigger daily_items_validate_task_owner
before insert or update of task_id, owner_id on public.daily_plan_items
for each row execute function public.validate_daily_item_task_owner();
create trigger sessions_validate_daily_item_owner
before insert or update of daily_plan_item_id, task_id, owner_id on public.sessions
for each row execute function public.validate_session_daily_item_owner();

create or replace function public.validate_partnership_pair_key()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.pair_key <> least(new.requester_id::text, new.addressee_id::text)
    || ':' || greatest(new.requester_id::text, new.addressee_id::text) then
    raise exception 'invalid partnership pair key' using errcode = '23514';
  end if;
  return new;
end
$$;
create trigger partnerships_validate_pair_key
before insert or update of requester_id, addressee_id, pair_key on public.partnerships
for each row execute function public.validate_partnership_pair_key();

create or replace function public.validate_plan_share_access()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.daily_plans
    where id = new.daily_plan_id and owner_id = new.owner_id and deleted_at is null
  ) then
    raise exception 'share owner must own the daily plan' using errcode = '23514';
  end if;
  if not exists (
    select 1 from public.partnerships
    where pair_key = least(new.owner_id::text, new.partner_id::text)
      || ':' || greatest(new.owner_id::text, new.partner_id::text)
      and status = 'ACCEPTED' and deleted_at is null
  ) then
    raise exception 'active partnership required' using errcode = '23514';
  end if;
  if exists (
    select 1 from public.user_blocks
    where (blocker_id = new.owner_id and blocked_id = new.partner_id)
       or (blocker_id = new.partner_id and blocked_id = new.owner_id)
  ) then
    raise exception 'blocked users cannot share plans' using errcode = '23514';
  end if;
  return new;
end
$$;
create trigger daily_plan_shares_validate_access
before insert or update of daily_plan_id, owner_id, partner_id on public.daily_plan_shares
for each row execute function public.validate_plan_share_access();

-- Every application table has RLS enabled. FastAPI supplies the current user
-- through a transaction-local setting before issuing any business query.
alter table public.users enable row level security;
alter table public.users force row level security;
alter table public.profiles enable row level security;
alter table public.profiles force row level security;
alter table public.tasks enable row level security;
alter table public.tasks force row level security;
alter table public.task_dependencies enable row level security;
alter table public.task_dependencies force row level security;
alter table public.daily_plans enable row level security;
alter table public.daily_plans force row level security;
alter table public.daily_plan_items enable row level security;
alter table public.daily_plan_items force row level security;
alter table public.sessions enable row level security;
alter table public.sessions force row level security;
alter table public.partnerships enable row level security;
alter table public.partnerships force row level security;
alter table public.user_blocks enable row level security;
alter table public.user_blocks force row level security;
alter table public.daily_plan_shares enable row level security;
alter table public.daily_plan_shares force row level security;
alter table public.encouragements enable row level security;
alter table public.encouragements force row level security;
alter table public.notifications enable row level security;
alter table public.notifications force row level security;

create policy users_owner_all on public.users for all
using (id = public.app_current_user_id() or public.app_is_service())
with check (id = public.app_current_user_id() or public.app_is_service());
create policy profiles_owner_all on public.profiles for all
using (id = public.app_current_user_id() or public.app_is_service())
with check (id = public.app_current_user_id() or public.app_is_service());

create policy tasks_owner_select on public.tasks for select
using (owner_id = public.app_current_user_id());
create policy tasks_owner_insert on public.tasks for insert
with check (owner_id = public.app_current_user_id());
create policy tasks_owner_update on public.tasks for update
using (owner_id = public.app_current_user_id())
with check (owner_id = public.app_current_user_id());
create policy tasks_owner_delete on public.tasks for delete
using (owner_id = public.app_current_user_id());

create policy task_dependencies_owner_select on public.task_dependencies for select
using (owner_id = public.app_current_user_id());
create policy task_dependencies_owner_insert on public.task_dependencies for insert
with check (owner_id = public.app_current_user_id());
create policy task_dependencies_owner_update on public.task_dependencies for update
using (owner_id = public.app_current_user_id())
with check (owner_id = public.app_current_user_id());
create policy task_dependencies_owner_delete on public.task_dependencies for delete
using (owner_id = public.app_current_user_id());

create policy daily_plans_owner_select on public.daily_plans for select
using (owner_id = public.app_current_user_id());
create policy daily_plans_owner_insert on public.daily_plans for insert
with check (owner_id = public.app_current_user_id());
create policy daily_plans_owner_update on public.daily_plans for update
using (owner_id = public.app_current_user_id())
with check (owner_id = public.app_current_user_id());
create policy daily_plans_owner_delete on public.daily_plans for delete
using (owner_id = public.app_current_user_id());

create policy daily_plan_items_owner_select on public.daily_plan_items for select
using (owner_id = public.app_current_user_id());
create policy daily_plan_items_owner_insert on public.daily_plan_items for insert
with check (owner_id = public.app_current_user_id());
create policy daily_plan_items_owner_update on public.daily_plan_items for update
using (owner_id = public.app_current_user_id())
with check (owner_id = public.app_current_user_id());
create policy daily_plan_items_owner_delete on public.daily_plan_items for delete
using (owner_id = public.app_current_user_id());

create policy sessions_owner_select on public.sessions for select
using (owner_id = public.app_current_user_id());
create policy sessions_owner_insert on public.sessions for insert
with check (owner_id = public.app_current_user_id());
create policy sessions_owner_update on public.sessions for update
using (owner_id = public.app_current_user_id())
with check (owner_id = public.app_current_user_id());
create policy sessions_owner_delete on public.sessions for delete
using (owner_id = public.app_current_user_id());

create policy partnerships_participant_select on public.partnerships for select
using (
  requester_id = public.app_current_user_id()
  or addressee_id = public.app_current_user_id()
);
create policy partnerships_requester_insert on public.partnerships for insert
with check (requester_id = public.app_current_user_id());
create policy partnerships_participant_update on public.partnerships for update
using (
  requester_id = public.app_current_user_id()
  or addressee_id = public.app_current_user_id()
)
with check (
  requester_id = public.app_current_user_id()
  or addressee_id = public.app_current_user_id()
);
create policy partnerships_participant_delete on public.partnerships for delete
using (
  requester_id = public.app_current_user_id()
  or addressee_id = public.app_current_user_id()
);

create policy user_blocks_participant_select on public.user_blocks for select
using (
  blocker_id = public.app_current_user_id()
  or blocked_id = public.app_current_user_id()
);
create policy user_blocks_blocker_insert on public.user_blocks for insert
with check (blocker_id = public.app_current_user_id());
create policy user_blocks_blocker_delete on public.user_blocks for delete
using (blocker_id = public.app_current_user_id());

create policy profiles_discovery_select on public.profiles for select
using (
  (
    is_searchable
    or exists (
      -- A pending invitation grants the same narrow read an accepted one
      -- does, so the recipient can always see who invited them even if the
      -- requester later turns discovery off.
      select 1 from public.partnerships
      where status in ('ACCEPTED', 'PENDING') and deleted_at is null
        and (
          (requester_id = profiles.id and addressee_id = public.app_current_user_id())
          or (addressee_id = profiles.id and requester_id = public.app_current_user_id())
        )
    )
  )
  and not exists (
    select 1 from public.user_blocks
    where (blocker_id = profiles.id and blocked_id = public.app_current_user_id())
       or (blocked_id = profiles.id and blocker_id = public.app_current_user_id())
  )
);

create policy daily_plan_shares_participant_select on public.daily_plan_shares for select
using (
  owner_id = public.app_current_user_id()
  or partner_id = public.app_current_user_id()
);
create policy daily_plan_shares_owner_insert on public.daily_plan_shares for insert
with check (owner_id = public.app_current_user_id());
create policy daily_plan_shares_participant_update on public.daily_plan_shares for update
using (
  owner_id = public.app_current_user_id()
  or partner_id = public.app_current_user_id()
)
with check (
  owner_id = public.app_current_user_id()
  or partner_id = public.app_current_user_id()
);

create policy encouragements_participant_select on public.encouragements for select
using (
  sender_id = public.app_current_user_id()
  or receiver_id = public.app_current_user_id()
);
create policy encouragements_sender_insert on public.encouragements for insert
with check (sender_id = public.app_current_user_id());

create policy notifications_owner_select on public.notifications for select
using (user_id = public.app_current_user_id());
create policy notifications_recipient_insert on public.notifications for insert
with check (
  user_id = public.app_current_user_id()
  or actor_id = public.app_current_user_id()
);
create policy notifications_owner_update on public.notifications for update
using (user_id = public.app_current_user_id())
with check (user_id = public.app_current_user_id());

create policy daily_plans_shared_select on public.daily_plans for select
using (
  exists (
    select 1 from public.daily_plan_shares
    where daily_plan_id = daily_plans.id
      and partner_id = public.app_current_user_id()
      and deleted_at is null
  )
);
create policy daily_plan_items_shared_select on public.daily_plan_items for select
using (
  exists (
    select 1 from public.daily_plan_shares
    where daily_plan_id = daily_plan_items.daily_plan_id
      and partner_id = public.app_current_user_id()
      and deleted_at is null
  )
);
create policy sessions_shared_duration_select on public.sessions for select
using (
  exists (
    select 1
    from public.daily_plan_items
    join public.daily_plan_shares
      on daily_plan_shares.daily_plan_id = daily_plan_items.daily_plan_id
    where daily_plan_items.id = sessions.daily_plan_item_id
      and daily_plan_shares.partner_id = public.app_current_user_id()
      and daily_plan_shares.share_duration
      and daily_plan_shares.deleted_at is null
  )
);

-- Supabase Auth owns credentials. This trigger mirrors only public identity
-- fields into DayFlow's application tables.
create or replace function public.handle_dayflow_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  seed_username text;
  seed_display_name text;
begin
  perform set_config('app.bypass_rls', 'on', true);
  seed_username := lower(coalesce(
    nullif(new.raw_user_meta_data->>'username', ''),
    'user_' || left(replace(new.id::text, '-', ''), 10)
  ));
  seed_display_name := coalesce(
    nullif(new.raw_user_meta_data->>'display_name', ''),
    seed_username
  );

  insert into public.users(id, email, phone, password_hash, is_active)
  values (new.id, new.email, new.phone, null, true)
  on conflict (id) do update
  set email = excluded.email,
      phone = excluded.phone,
      is_active = true,
      updated_at = now();

  insert into public.profiles(id, username, display_name)
  values (new.id, seed_username, left(seed_display_name, 80))
  on conflict (id) do nothing;
  return new;
end
$$;

create trigger dayflow_auth_user_changed
after insert or update of email, phone, raw_user_meta_data on auth.users
for each row execute function public.handle_dayflow_auth_user();

create table public.alembic_version (
  version_num varchar(32) primary key
);
insert into public.alembic_version(version_num) values ('0011');
