#!/usr/bin/env bash
# Run on the MAC between rounds (and once before the event).
# Rotates flags, re-seeds the target, pushes the result to the Pi, restarts it.
# Usage: ./mac/round.sh [pi-host]     default pi@192.168.0.112
set -euo pipefail
PI="${1:-pi@192.168.0.112}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

echo "[1/4] Rotating flags and re-seeding local copy..."
python3 reset_flags.py

echo "[2/4] Pushing target files to the Pi..."
rsync -az --delete --exclude 'portal.db-journal' --exclude '__pycache__' \
  portal flags.json "$PI":/tmp/bims-push/

echo "[3/4] Installing on the Pi and restarting..."
ssh -t "$PI" '
  sudo rsync -a --delete /tmp/bims-push/portal/ /opt/barangay-ctf/portal/ &&
  sudo cp /tmp/bims-push/flags.json /opt/barangay-ctf/flags.json &&
  sudo chown -R ctf:ctf /opt/barangay-ctf &&
  sudo systemctl restart ghostnet-portal &&
  sleep 2 && curl -s -o /dev/null -w "BIMS HTTP %{http_code}\n" http://127.0.0.1/ &&
  rm -rf /tmp/bims-push'

echo "[4/4] Done. The scoreboard reads ../flags.json, so it is already in sync."
echo "      Check the admin panel, then start the clock."
