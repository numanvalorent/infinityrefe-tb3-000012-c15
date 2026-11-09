#!/usr/bin/env bash
set -uo pipefail
mkdir -p /logs/verifier
python3 -m pytest /tests/test_outputs.py -p ctrf --ctrf=/logs/verifier/ctrf.json -q
if [ $? -eq 0 ]; then printf '1' > /logs/verifier/reward.txt; else printf '0' > /logs/verifier/reward.txt; fi
