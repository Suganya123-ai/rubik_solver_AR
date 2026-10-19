#!/usr/bin/env bash
# Downloads the open-source projects the benchmarks run against, pinned to
# the exact commits that were tested. Run from bench/.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p third_party

clone() {  # name url commit
  if [ ! -d "third_party/$1" ]; then
    git clone -q "$2" "third_party/$1"
  fi
  git -C "third_party/$1" checkout -q "$3"
}

clone qbr                 https://github.com/kkoomen/qbr.git                              28c7514115991ef680072bf794e453f1642219b0
clone rubiks-cube-tracker https://github.com/dwalton76/rubiks-cube-tracker.git            40f372982430ba8d7e4c9070bdb429e1ab0450ba
clone ephynes             https://github.com/ephynes/AR-Optimal-Rubiks-Cube-solver.git    8b5e435938cb4d42accfcfadcdeead06a18e7324

# cubejs (JavaScript two-phase solver) for bench_solvers.py
mkdir -p third_party/node
(cd third_party/node && [ -f package.json ] || npm init -y >/dev/null; npm install --silent cubejs@1.3.2)

echo "third_party ready"
