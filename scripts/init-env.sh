#!/bin/sh
# Creates .env from .env.example, filling every empty *_PASSWORD and *_SECRET_KEY with a random value.
# Other values (LLM_API_KEY and the rest) are copied as they are: hosted-LLM settings are the operator's.
# Never overwrites an existing file (exits 0 and says so). Optional argument: the file to create (default: .env at the
# repository root); infra/tests/smoke.sh uses it for throwaway stacks.
set -eu
case ${1:-} in
  "") out="$(cd "$(dirname "$0")/.." && pwd)/.env" ;;
  /*|[A-Za-z]:/*) out=$1 ;;
  *) out="$(pwd)/$1" ;;  # relative to the caller, not the repository
esac
cd "$(dirname "$0")/.."
if [ -e "$out" ] || [ -L "$out" ]; then
  # Not an error: a repeated Quick Start run keeps the existing secrets.
  echo "$out already exists, not touching it"
  exit 0
fi
gen() { openssl rand -hex 24; }
umask 077
tmp=$(mktemp "$out.XXXXXX")
trap 'rm -f "$tmp"' EXIT
cr=$(printf '\r')
while IFS= read -r line || [ -n "$line" ]; do
  line=${line%"$cr"}  # a CRLF checkout of .env.example must still match the secret lines
  case $line in
    \#*) printf '%s\n' "$line" ;;
    *_PASSWORD=|*_SECRET_KEY=)
      value=$(gen) || value=  # without openssl, fall through to the message below instead of dying on set -e
      if [ ${#value} -lt 32 ]; then
        echo "could not generate secrets (is openssl installed?)" >&2
        exit 1
      fi
      printf '%s%s\n' "$line" "$value" ;;
    *) printf '%s\n' "$line" ;;
  esac
done < .env.example > "$tmp"
mv "$tmp" "$out"
trap - EXIT
echo "Created $out (mode 600) with random secrets."
