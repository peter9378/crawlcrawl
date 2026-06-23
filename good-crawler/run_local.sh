#!/bin/sh
set -eu

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"
export HOST PORT
export WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"

exec gunicorn app:app -c gunicorn.conf.py
