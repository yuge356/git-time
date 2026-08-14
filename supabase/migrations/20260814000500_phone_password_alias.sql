-- Supabase's hosted Phone provider requires SMS credentials even when OTP is
-- not part of DayFlow's MVP. Phone/password accounts therefore use a reserved,
-- deterministic email alias inside Auth while the public mirror exposes only
-- the original E.164 phone number.

create or replace function public.handle_dayflow_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  seed_username text;
  seed_display_name text;
  identity_email text;
  identity_phone text;
  phone_digits text;
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

  phone_digits := substring(
    lower(coalesce(new.email, ''))
    from '^phone\.([1-9][0-9]{7,14})@phone\.dayflow\.invalid$'
  );
  if new.phone is null and phone_digits is not null then
    identity_email := null;
    identity_phone := '+' || phone_digits;
  else
    identity_email := new.email;
    identity_phone := new.phone;
  end if;

  insert into public.users(id, email, phone, password_hash, is_active)
  values (new.id, identity_email, identity_phone, null, true)
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

revoke execute on function public.handle_dayflow_auth_user() from public, anon, authenticated;

update public.alembic_version set version_num = '0012' where version_num = '0011';
