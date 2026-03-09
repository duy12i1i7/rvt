#!/usr/bin/env bash
set -e
python run_experiments.py --mode ablations --device cpu --results-dir results/ablations
