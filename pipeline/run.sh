#!/usr/bin/env bash
# Each stage is independent and writes files; a failed stage never blocks the commit of the others.
set -u
mkdir -p data
[ -f data/raw/model_check.json ] || python pipeline/model_check.py || true
python pipeline/fetch_raw.py || echo "fetch_raw failed"
[ -f pipeline/build_snapshot.py ] && python pipeline/build_snapshot.py || true
