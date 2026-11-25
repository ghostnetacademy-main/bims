#!/usr/bin/env bash
#
# setup_pi.sh -- turn a Raspberry Pi into the CTF range appliance.
# Installs both apps as systemd services under gunicorn so they auto-start on boot.
#
# Run from the project root ON THE PI:
#     ./pi/setup_pi.sh [INSTRUCTOR_TOKEN]
#
# Re-runnable: safe to run again after you pull changes or change the token.
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_USER="$(whoami)"
TOKEN="${1:-change-me}"
PORTAL_PORT=5050
SCORE_PORT=5001

echo "==> Project : $PROJECT_DIR"
echo "==> User    : $RUN_USER"
echo "==> Token   : $TOKEN"

# 1. Virtualenv + dependencies (Raspberry Pi OS blocks system-wide pip, so use a venv)
echo "==> Installing python venv + dependencies ..."
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip
python3 -m venv "$PROJECT_DIR/venv"
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install Flask==3.0.3 gunicorn

GUNICORN="$PROJECT_DIR/venv/bin/gunicorn"

# 2. systemd unit: the vulnerable portal (the target)
#    --preload runs the app's one-time seeding once, before workers fork.
echo "==> Writing systemd services ..."
sudo tee /etc/systemd/system/ghostnet-portal.service >/dev/null <<EOF
[Unit]
Description=GhostNet CTF - Barangay Services Portal (deliberately vulnerable target)
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$PROJECT_DIR/portal
ExecStart=$GUNICORN --preload -w 2 -b 0.0.0.0:$PORTAL_PORT app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# 3. systemd unit: the scoreboard (carries the instructor token)
sudo tee /etc/systemd/system/ghostnet-scoreboard.service >/dev/null <<EOF
[Unit]
Description=GhostNet CTF - Scoreboard
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$PROJECT_DIR/scoreboard
Environment=CTF_INSTRUCTOR_TOKEN=$TOKEN
ExecStart=$GUNICORN --preload -w 2 -b 0.0.0.0:$SCORE_PORT app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# 4. Enable + (re)start
echo "==> Enabling services ..."
sudo systemctl daemon-reload
sudo systemctl enable ghostnet-portal ghostnet-scoreboard
sudo systemctl restart ghostnet-portal ghostnet-scoreboard

IP="$(hostname -I | awk '{print $1}')"
echo
echo "========================================================"
echo " Range is live and will auto-start on every boot."
echo "   Portal (target) : http://$IP:$PORTAL_PORT"
echo "   Scoreboard      : http://$IP:$SCORE_PORT"
echo "   Instructor      : http://$IP:$SCORE_PORT/instructor   (token: $TOKEN)"
echo "========================================================"
echo
echo " Between rounds (over SSH):"
echo "   cd $PROJECT_DIR && ./venv/bin/python reset_flags.py --round 2"
echo "   (no restart needed -- the portal re-reads flags and DB on the next request)"
echo
echo " Handy:"
echo "   sudo systemctl status ghostnet-portal ghostnet-scoreboard"
echo "   journalctl -u ghostnet-portal -f"
