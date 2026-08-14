-- Keep extensions outside the API-exposed public schema. The project search
-- path already includes `extensions`, so existing citext columns keep working.

alter extension citext set schema extensions;
