-- Harden helper functions exposed through the public schema and add the
-- covering indexes reported by Supabase's database advisors.

revoke execute on function public.handle_dayflow_auth_user() from public, anon, authenticated;
revoke execute on function public.rls_auto_enable() from public, anon, authenticated;

-- Alembic's bookkeeping row contains no user data and must remain readable by
-- migration tooling; it does not need row-level policies.
alter table public.alembic_version disable row level security;

create index if not exists ix_daily_plan_items_task_id
  on public.daily_plan_items(task_id);
create index if not exists ix_daily_plan_items_plan_owner
  on public.daily_plan_items(daily_plan_id, owner_id);
create index if not exists ix_encouragements_sender_id
  on public.encouragements(sender_id);
create index if not exists ix_notifications_actor_id
  on public.notifications(actor_id);
create index if not exists ix_task_dependencies_task_owner
  on public.task_dependencies(task_id, owner_id);
create index if not exists ix_task_dependencies_prerequisite_owner
  on public.task_dependencies(depends_on_task_id, owner_id);
create index if not exists ix_tasks_parent_owner
  on public.tasks(parent_id, owner_id);
