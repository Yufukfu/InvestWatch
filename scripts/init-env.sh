#!/bin/sh
# Creates .env from .env.example with random passwords. Never overwrites an existing .env.
set -eu
cd "$(dirname "$0")/.."
if [ -f .env ]; then
  echo ".env already exists, not touching it" >&2
  exit 1
fi
gen() { openssl rand -hex 24; }
admin_pw=$(gen)
app_pw=$(gen)
if [ ${#admin_pw} -lt 32 ] || [ ${#app_pw} -lt 32 ]; then
  echo "could not generate passwords (is openssl installed?)" >&2
  exit 1
fi
umask 077
sed -e "s|^POSTGRES_ADMIN_PASSWORD=.*|POSTGRES_ADMIN_PASSWORD=${admin_pw}|" \
    -e "s|^POSTGRES_APP_PASSWORD=.*|POSTGRES_APP_PASSWORD=${app_pw}|" .env.example > .env
echo "Created .env (mode 600) with random passwords."
