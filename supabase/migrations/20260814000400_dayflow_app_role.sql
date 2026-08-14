-- FastAPI connects through the Supabase pooler as the project database owner,
-- then immediately SET ROLEs to this least-privilege runtime role. Alembic uses
-- a separate connection and therefore keeps migration privileges.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'dayflow_app') then
    create role dayflow_app
      nologin
      nosuperuser
      nocreatedb
      nocreaterole
      noinherit
      nobypassrls;
  end if;
end
$$;

grant usage on schema public, extensions to dayflow_app;
grant select, insert, update, delete on table
  public.users,
  public.profiles,
  public.tasks,
  public.task_dependencies,
  public.daily_plans,
  public.daily_plan_items,
  public.sessions,
  public.partnerships,
  public.user_blocks,
  public.daily_plan_shares,
  public.encouragements,
  public.notifications
to dayflow_app;
grant execute on function public.app_current_user_id() to dayflow_app;
grant execute on function public.app_is_service() to dayflow_app;

-- No default privileges are granted. Each future migration must explicitly
-- grant only the permissions its new runtime objects require.
