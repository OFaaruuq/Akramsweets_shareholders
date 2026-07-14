-- Run once in pgAdmin or psql as the postgres superuser.
-- Creates the app database and user used by AKRAM SWEET Shareholders Project.

CREATE USER akram_user WITH PASSWORD 'akram_pass';

CREATE DATABASE akram_shareholders
    WITH OWNER = akram_user
    ENCODING = 'UTF8';

GRANT ALL PRIVILEGES ON DATABASE akram_shareholders TO akram_user;
