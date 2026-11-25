# Barangay Malinaw BIMS CTF Range

An **intentionally vulnerable** Barangay Information Management System (BIMS)
plus a Red/Blue team scoreboard, built as a hands-on Capture-The-Flag training
range. First used at the DICT Caraga Region Cybersecurity Capability
Enhancement & Cyber Defense Simulation Exercise (Butuan City, November 2026).

Released to the public domain — **no copyright, no conditions.** See `LICENSE`.

> ⚠️ **Read [ETHICAL_USE.md](ETHICAL_USE.md) first.** This app contains remote
> code execution *by design*. Run it only on an isolated lab network that you
> control. Never put it on a machine that holds anything you care about.

---

## What's inside

| Folder | What it is |
|---|---|
| `portal/` | The target: a Flask BIMS with ~160 fictional residents, households, certificates, businesses and blotter records |
| `scoreboard/` | Team registration, flag submission, Blue-team fix reports, instructor-run rounds |
| `reset_flags.py` | Rotates every flag and reseeds the data between rounds |
| `modules/` | Participant handouts — Red Team, Blue Team, Burp Suite |
| `facilitator/` | **Spoilers.** Answer key and helper scripts for the instructor |
| `pi/` | Setup script for running the target as a Raspberry Pi appliance |
| `mac/` | Instructor helper scripts (round control, pushing files to the target) |
| `burp/` | Small wordlist for the brute-force exercise |

### The four planted vulnerabilities

| # | Vulnerability | OWASP Top 10 | Points |
|---|---|---|---|
| 1 | Default administrator password | A07 Identification & Authentication Failures | 10 |
| 2 | SQL injection | A03 Injection | 20 |
| 3 | Unrestricted file upload → web shell (RCE) | A04 Insecure Design / A05 Misconfiguration | 30 |
| 4 | Exposed configuration file via path traversal | A01 Broken Access Control / A05 | 15 |

Each one hides a flag. **Blue scores the same as Red:** capture the flag, *or*
patch the bug and file a fix report the instructor verifies.

---

## Requirements

- Python **3.10+**
- Linux or macOS (Windows works under WSL)
- `git`
- For participants: any machine with a browser. Kali Linux + Burp Suite
  Community recommended for the Red team.
- Optional: a Raspberry Pi 3 or newer, or a small throwaway cloud VM
  (512 MB–1 GB RAM), to act as the dedicated target

---

## Option A — Run everything on one machine (quickest, for self-study)

```bash
git clone https://github.com/ghostnetacademy-main/bims.git
cd bims

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Choose your own instructor token (otherwise the scoreboard makes a random one
and prints it at startup):

```bash
export CTF_INSTRUCTOR_TOKEN="pick-a-long-token-here"
```

The scoreboard's session secret is created automatically in
`scoreboard/.session_key` on first run (or set `CTF_SECRET_KEY`). It is in
`.gitignore`. Never commit it, and never reuse someone else's.

Start the target (terminal 1). It builds and seeds its own database
(`portal/portal.db`) on first start:

```bash
cd portal
python3 app.py
```

Start the scoreboard (terminal 2):

```bash
source .venv/bin/activate
export CTF_INSTRUCTOR_TOKEN="pick-a-long-token-here"
cd scoreboard
python3 app.py
```

| App | URL |
|---|---|
| Target portal | `http://localhost:5050` |
| Scoreboard | `http://localhost:5001` |
| Instructor page | printed in the scoreboard terminal at startup (log in with your token) |

Work through `modules/01-RED-TEAM.md`, then `modules/02-BLUE-TEAM.md`.

---

## Option B — Dedicated target appliance (recommended for a class or event)

### 1. Install the appliance

On a Raspberry Pi (Raspberry Pi OS / Debian) or a fresh Ubuntu/Debian VM:

```bash
git clone https://github.com/ghostnetacademy-main/bims.git
cd bims
chmod +x pi/setup_pi.sh
./pi/setup_pi.sh "your-instructor-token"
```

The script creates a venv, installs Flask and gunicorn, and registers both apps
as systemd services that start on every boot:

| App | Port |
|---|---|
| Target portal | `5050` |
| Scoreboard | `5001` |

It prints the portal, scoreboard and instructor URLs when it finishes. Re-run it
any time to change the token or after pulling updates. Full notes are in
[`pi/README-PI.md`](pi/README-PI.md).

Then change the device's own login password and lock SSH to your admin IP.
The *app* is meant to be broken. The *box* should not be.

### 2. Stricter setup: scoreboard on a separate machine

With both apps on one box, a participant who gets a shell through bug #3 is on
the same machine as the scores. For anything competitive, run the scoreboard on
the instructor's machine (Option A steps) and disable the scoreboard service on
the target (see `pi/README-PI.md`):

```
 participants ──►  TARGET (Pi or throwaway VM)      portal on :5050
      │
      └────────►  INSTRUCTOR MACHINE                scoreboard on :5001
```

### 3. Isolate the network

Put the target and the participants on a switch or travel router **with no
internet uplink**, or firewall the target so it can't make outbound
connections. A web shell that can't call out is a lesson. A web shell that
can is a botnet node.

---

## Running an exercise

1. Participants register their teams on the scoreboard.
2. Brief everyone on the rules of engagement (`modules/README.md`): only the
   target address given in the room is in scope.
3. Run the timed rounds from the instructor page: **attack-only**,
   **defend-only**, then a **finale** with both sides live.
4. Between rounds, rotate the flags and reseed the data:
   ```bash
   python3 reset_flags.py
   ```
5. Blue teams submit fix reports. Approve or reject them on the
   instructor page.
6. Debrief with `facilitator/SOLUTIONS.md`. Show the target's web logs on the
   projector so the class sees its own attacks from the defender's side.

After the event, **wipe the target** (reflash the SD card or destroy the VM).

---

## Troubleshooting

**Portal homepage shows a 500 error / "no such table: officials"**
An empty `portal/portal.db` was created before seeding finished. Stop the
portal, delete `portal/portal.db`, and start the portal again. It reseeds on
startup.

**Flags don't match after a reset**
Make sure `reset_flags.py` ran on the *target* and the scoreboard reads the same
flag set. Restart both apps.

**Participants can't reach the target**
Check that every device is on the same isolated network, then confirm with
`curl http://<target-ip>:5050/` from a participant machine.

**Lost the instructor token**
Set `CTF_INSTRUCTOR_TOKEN` and restart the scoreboard, or re-run
`./pi/setup_pi.sh "new-token"` on the appliance.

---

## Do not put this on the public internet

If you want an always-on online practice range, use a target built for that,
like [OWASP Juice Shop](https://owasp.org/www-project-juice-shop/). Its bugs
stay inside the app. This one hands out a real shell. If you expose it anyway,
block all outbound traffic, reset it nightly, and use a VM you're prepared to
lose.

---

## Contributing

Pull requests are welcome: new vulnerabilities, translations of the modules
(Filipino, Bisaya), better fixes for the Blue track. Keep all data fictional.

## Credits

Built by the GhostNet Academy / CyberTumbler training team for educators and
defenders everywhere. Dedicated to the public domain.
