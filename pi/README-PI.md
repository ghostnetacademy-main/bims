# Running the range on a Raspberry Pi

Turns the Pi into a self-contained CTF appliance: boot it, and both the vulnerable
portal and the scoreboard come up on their own. A Pi 3 (1 GB RAM) is plenty — the apps
are lightweight Flask on SQLite.

## 1. Get the files onto the Pi

From your Mac (replace the Pi's user/IP):

```bash
cd /Users/merlin/python/systems
scp -r dict  merlin@<pi-ip>:~/barangay-ctf
```

(or `git clone` if you've put it in a repo). Any folder works; the installer figures out
its own path.

## 2. Install (one command, on the Pi)

```bash
ssh merlin@<pi-ip>
cd ~/barangay-ctf
chmod +x pi/setup_pi.sh
./pi/setup_pi.sh "your-instructor-token"
```

It creates a venv, installs Flask + gunicorn, and registers two systemd services that
auto-start on every boot. When it finishes it prints the URLs:

- Portal (target): `http://<pi-ip>:5050`
- Scoreboard:      `http://<pi-ip>:5001`
- Instructor:      `http://<pi-ip>:5001/instructor`

## 3. Put the Pi on an isolated network

The Pi now plays the role the VM's host-only adapter did. Pick one:

- **Dedicated router/switch (recommended).** A cheap travel router or switch with **no
  internet uplink**. Plug in the Pi, give it a static IP (below), and have participants
  join that network. Simple and reliably isolated.
- **Pi as its own Wi-Fi hotspot.** Fully self-contained, no extra hardware — set up an
  access point with `hostapd` + `dnsmasq` and no uplink. More to configure; ask if you
  want the config.
- **Do not** put the vulnerable portal on the real office LAN or anything with internet.

### Give the Pi a fixed IP (so laptops always find it)

Raspberry Pi OS **Bookworm** (NetworkManager):
```bash
nmcli con mod "Wired connection 1" ipv4.addresses 192.168.50.10/24 ipv4.method manual
sudo nmcli con up "Wired connection 1"
```
Older **Bullseye** (`/etc/dhcpcd.conf`): add
```
interface eth0
static ip_address=192.168.50.10/24
```
then `sudo systemctl restart dhcpcd`.

## 4. Between rounds (over SSH)

```bash
cd ~/barangay-ctf
./venv/bin/python reset_flags.py --round 2     # rotate flags, re-seed, clear uploads
```
No restart needed — the portal re-reads `flags.json` and the DB on the next request.
Then open the **instructor panel** and click *Clear scores (keep teams)* + set the round.

## Service controls

```bash
sudo systemctl status  ghostnet-portal ghostnet-scoreboard
sudo systemctl restart ghostnet-portal
journalctl -u ghostnet-portal -f            # live logs
sudo systemctl disable --now ghostnet-scoreboard   # e.g. if you run the scoreboard on your Mac instead
```

## Notes

- Running under **gunicorn turns Flask debug mode OFF**. That's deliberate for a box on a
  shared room network — debug mode would expose the Werkzeug debugger, a second way onto
  the Pi beyond the intended web-shell challenge. **All four planted bugs are unaffected**;
  they live in the app, not the server.
- Scoreboard on your Mac instead? Disable the Pi's scoreboard service (above), run it on
  the Mac, and `scp` `flags.json` from the Pi to the Mac after each `reset_flags.py` so
  flag validation matches. One box (both on the Pi) avoids that sync entirely.
