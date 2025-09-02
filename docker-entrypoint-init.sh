#!/bin/bash
set -e

# Check if the DB_REBUILD environment variable is set to 'true'
if [ "$DB_REBUILD" = "true" ]; then
  echo "DB_REBUILD is true. Dropping and rebuilding the database..."
  
  # Connect to the 'postgres' default database to drop your application database
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    REVOKE CONNECT ON DATABASE "$POSTGRES_DB" FROM public;
    SELECT pg_terminate_backend(pg_stat_activity.pid)
    FROM pg_stat_activity
    WHERE pg_stat_activity.datname = '$POSTGRES_DB';
    DROP DATABASE IF EXISTS "$POSTGRES_DB";
EOSQL
  
  echo "Database '$POSTGRES_DB' dropped."
  
  # Recreate the application database with the correct owner
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    CREATE DATABASE "$POSTGRES_DB" WITH OWNER "$POSTGRES_USER";
EOSQL

  echo "Database '$POSTGRES_DB' rebuilt."
fi

# Pass control to the original PostgreSQL entrypoint script
/usr/local/bin/docker-entrypoint.sh "$@"