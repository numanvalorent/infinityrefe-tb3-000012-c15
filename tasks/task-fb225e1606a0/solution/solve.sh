#!/bin/bash
set -euo pipefail
cp /solution/propagate.py /app/propagate.py
python3 -I /app/propagate.py /app/data/input.json /app/output.json
