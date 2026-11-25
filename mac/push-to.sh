#!/usr/bin/env bash
# Run on the MAC AFTER round.sh. Pushes the CURRENT flags/target to an
# additional Pi WITHOUT rotating, so every target matches the scoreboard.
# Usage: ./mac/push-to.sh pi@192.168.0.185
set -euo pipefail
PI="${1:?usage: push-to.sh pi@IP}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
echo "[1/2] Pushing current target to $PI (no rotation)..."
rsync -az --delete --exclude 'portal.db-journal' --exclude '__pycache__' \
  portal flags.json "$PI":/tmp/bims-push/
echo "[2/2] Installing and restarting on $PI..."
ssh -t "$PI" '
  sudo rsync -a --delete /tmp/bims-push/portal/ /opt/barangay-ctf/portal/ &&
  sudo cp /tmp/bims-push/flags.json /opt/barangay-ctf/flags.json &&
  sudo chown -R ctf:ctf /opt/barangay-ctf &&
  sudo systemctl restart ghostnet-portal &&
  sleep 2 && curl -s -o /dev/null -w "BIMS HTTP %{http_code}\n" http://127.0.0.1/ &&
  rm -rf /tmp/bims-push'
echo "Done. $PI now matches the Mac flags.json."
