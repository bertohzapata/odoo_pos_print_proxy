#!/usr/bin/env bash
# Unico camino de mutacion de feature_list.json. Ver AGENTS.md.
exec python3 "$(dirname "$0")/estado.py" "$@"
