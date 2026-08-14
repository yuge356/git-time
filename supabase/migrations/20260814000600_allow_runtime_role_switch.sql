-- PostgreSQL 16+ records SET permission separately from role membership.
-- Keep inheritance disabled, but allow the Supabase project connection owner
-- to enter the least-privilege runtime role explicitly on pooled connections.

grant dayflow_app to postgres with set true;
