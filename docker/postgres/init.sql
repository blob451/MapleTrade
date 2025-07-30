-- Initialize MapleTrade database
-- This script runs when PostgreSQL container starts for the first time

-- Create database if it doesn't exist
SELECT 'CREATE DATABASE mapletrade_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mapletrade_db')\gexec

-- Connect to the database
\c mapletrade_db;

-- Create extensions that might be useful for financial data
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create a role for the application (future use)
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'mapletrade_app') THEN
      CREATE ROLE mapletrade_app LOGIN PASSWORD 'mapletrade_app_password';
   END IF;
END
$$;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE mapletrade_db TO mapletrade_app;

-- Log initialization
INSERT INTO pg_catalog.pg_stat_statements_info (dealloc) VALUES (0) ON CONFLICT DO NOTHING;

-- Create initial schema comment
COMMENT ON DATABASE mapletrade_db IS 'MapleTrade Financial Analytics Platform Database';