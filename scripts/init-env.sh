#!/bin/sh
# Creates .env from .env.example, filling every empty *_PASSWORD and *_SECRET_KEY with a random value.
# Other values (LLM_API_KEY and the rest) are copied as they are: hosted-LLM settings are the operator's.
# Never overwrites an existing file (exits 0 and says so). Optional argument: the file to create (default: .env at the
# repository root); infra/tests/smoke.sh uses it for throwaway stacks.
# --local-llm: the free open-model path in one command (ADR 0304). Also writes LLM_BASE_URL/LLM_MODEL/LLM_API_KEY for
# the bundled Ollama, the embeddings endpoint and COMPOSE_PROFILES=llm, so a plain `docker compose up --build` starts
# Ollama, pulls the models and has analytics use them. The model is gemma3:4b, or $LOCAL_LLM_MODEL (an Ollama tag).
set -eu
local_llm=0 target=
for arg in "$@"; do
  case $arg in
    --local-llm) local_llm=1 ;;
    -*) echo "usage: $0 [--local-llm] [file]" >&2; exit 2 ;;
    *) [ -z "$target" ] || { echo "usage: $0 [--local-llm] [file]" >&2; exit 2; }; target=$arg ;;
  esac
done
case $target in
  "") out="$(cd "$(dirname "$0")/.." && pwd)/.env" ;;
  /*|[A-Za-z]:/*) out=$target ;;
  *) out="$(pwd)/$target" ;;  # relative to the caller, not the repository
esac
model=${LOCAL_LLM_MODEL:-gemma3:4b}
case $model in *[!A-Za-z0-9._:/-]*) echo "LOCAL_LLM_MODEL must be an Ollama tag (letters, digits, . _ : / -)" >&2; exit 2 ;; esac
cd "$(dirname "$0")/.."
if [ -e "$out" ] || [ -L "$out" ]; then
  # Not an error: a repeated Quick Start run keeps the existing secrets.
  echo "$out already exists, not touching it"
  [ "$local_llm" = 0 ] || echo "--local-llm was not applied: move $out aside and rerun, or set the LLM_* and COMPOSE_PROFILES lines by hand (infra/README.md)"
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
    LLM_BASE_URL=|LLM_MODEL=|LLM_API_KEY=|OLLAMA_PULL_MODELS=*)
      if [ "$local_llm" = 0 ]; then printf '%s\n' "$line"; continue; fi
      case $line in
        LLM_BASE_URL=*) printf 'LLM_BASE_URL=http://ollama:11434/v1\n' ;;
        LLM_MODEL=*) printf 'LLM_MODEL=%s\n' "$model" ;;
        LLM_API_KEY=*) printf 'LLM_API_KEY=ollama\n' ;;  # Ollama ignores it, analytics needs a non-empty value
        *) printf 'OLLAMA_PULL_MODELS="%s bge-m3"\n' "$model" ;;
      esac ;;
    *) printf '%s\n' "$line" ;;
  esac
done < .env.example > "$tmp"
if [ "$local_llm" = 1 ]; then
  cat >> "$tmp" <<'EOF'

# Added by init-env.sh --local-llm: local open model (ADR 0304). Plain `docker compose up --build` now also starts
# ollama and pulls the models (several GB, once). Analytics runs rules-only until the pull has finished.
COMPOSE_PROFILES=llm
EMBED_BASE_URL=http://ollama:11434/v1
EOF
fi
mv "$tmp" "$out"
trap - EXIT
echo "Created $out (mode 600) with random secrets."
