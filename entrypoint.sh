#!/bin/bash
set -e

# Map Railway DATABASE_URL -> POSTGRES_* vars
if [ -n "$DATABASE_URL" ] && [ -z "$POSTGRES_HOST" ]; then
  export POSTGRES_USER=$(echo "$DATABASE_URL" | python3 -c "import sys,urllib.parse as u; print(u.urlparse(sys.stdin.read().strip()).username or 'postgres')")
  export POSTGRES_PASSWORD=$(echo "$DATABASE_URL" | python3 -c "import sys,urllib.parse as u; print(u.urlparse(sys.stdin.read().strip()).password or 'postgres')")
  export POSTGRES_HOST=$(echo "$DATABASE_URL" | python3 -c "import sys,urllib.parse as u; print(u.urlparse(sys.stdin.read().strip()).hostname or 'localhost')")
  PORT=$(echo "$DATABASE_URL" | python3 -c "import sys,urllib.parse as u; p=u.urlparse(sys.stdin.read().strip()).port; print(p if p else 5432)")
  export POSTGRES_PORT=$PORT
  export POSTGRES_DB=$(echo "$DATABASE_URL" | python3 -c "import sys,urllib.parse as u; print(u.urlparse(sys.stdin.read().strip()).path.lstrip('/') or 'rag_qa')")
  echo "Mapped DATABASE_URL -> postgres"
fi

# Map Railway REDIS_URL -> REDIS vars
if [ -n "$REDIS_URL" ] && [ -z "$REDIS_HOST" ]; then
  export REDIS_HOST=$(echo "$REDIS_URL" | python3 -c "import sys,urllib.parse as u; print(u.urlparse(sys.stdin.read().strip()).hostname or 'localhost')")
  PORT=$(echo "$REDIS_URL" | python3 -c "import sys,urllib.parse as u; p=u.urlparse(sys.stdin.read().strip()).port; print(p if p else 6379)")
  export REDIS_PORT=$PORT
  echo "Mapped REDIS_URL -> redis"
fi

exec "$@"
