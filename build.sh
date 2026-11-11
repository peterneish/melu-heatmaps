#!/usr/bin/env bash
# Rebuild everything: fetch from ALA, build the matrices, write docs/index.html
set -e
python clean_names.py
python collector_years.py
python combine.py
