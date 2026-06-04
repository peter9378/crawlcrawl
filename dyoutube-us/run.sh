#!/bin/sh

uvicorn app:app --host 0.0.0.0 --port 80 --reload --log-level info

