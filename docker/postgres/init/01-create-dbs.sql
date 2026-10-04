-- Runs once, when the pgdata volume is first initialised (docker-entrypoint-initdb.d).
-- The default database (POSTGRES_DB) is created by the image; these are the five R2R databases.
CREATE DATABASE erp_sim;
CREATE DATABASE lims_sim;
CREATE DATABASE qms_sim;
CREATE DATABASE app;
CREATE DATABASE dagster;
