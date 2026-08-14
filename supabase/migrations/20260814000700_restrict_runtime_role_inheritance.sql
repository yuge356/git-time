-- PostgreSQL 17 stores membership options per grantor. Explicitly prevent the
-- project connection owner from inheriting runtime permissions before SET ROLE.

grant dayflow_app to postgres with inherit false, set true;
