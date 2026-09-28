#!/bin/sh
set -e

cd /usr/src/app

if [ ! -d node_modules/.bin ]; then
  echo "[frontend] node_modules not found. Installing dependencies..."
  npm install
fi

PORT="${VITE_PORT:-3000}"

exec npm run dev -- --host 0.0.0.0 --port "${PORT}"
