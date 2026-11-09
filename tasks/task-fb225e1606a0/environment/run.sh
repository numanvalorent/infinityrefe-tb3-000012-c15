#!/bin/bash
set -euo pipefail
python3 -I /app/propagate.py /app/data/input.json /app/output.json
