#!/bin/sh
set -e

echo "==> Waiting for database..."
if [ -n "$DATABASE_URL" ]; then
    # Simple python wait-for-db check
    python << END
import sys, time, os
import environ

env = environ.Env()
db_url = os.environ.get("DATABASE_URL", "")

if "postgres" in db_url or "psycopg" in db_url:
    import psycopg
    db_config = env.db_url_config(db_url)
    max_tries = 30
    for i in range(max_tries):
        try:
            conn = psycopg.connect(
                dbname=db_config['NAME'],
                user=db_config['USER'],
                password=db_config['PASSWORD'],
                host=db_config['HOST'],
                port=db_config.get('PORT', 5432)
            )
            conn.close()
            print("PostgreSQL is available!")
            sys.exit(0)
        except Exception as e:
            print(f"Waiting for PostgreSQL... ({i+1}/{max_tries}): {e}")
            time.sleep(1)
    sys.exit(1)
END
fi

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Starting application..."
exec "$@"
