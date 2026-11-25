# 🟦 Blue Team Field Guide
### Barangay Malinaw BIMS — Attack-Defense CTF

> **Authorized training only.** You are hardening the training portal on the isolated
> lab network. The skills here are for defending systems you own or are authorized to
> protect.

---

## Your mission

Red team broke into the portal. You fix it. For each of the four bugs you:

1. **Find the root cause** in the code,
2. **Patch** it,
3. **File an attack report** that explains how the attack worked and how you stopped it.

A patch that the instructor **verifies** scores the same points as the matching flag:

| Bug | Points |
|-----|-------:|
| Default admin password | 10 |
| SQL injection on login | 20 |
| Unrestricted file upload → web shell | 30 |
| Exposed config file | 15 |

## Where the code lives

The portal is one file: **`portal/app.py`**. On the range box (the Raspberry Pi or the
instructor's machine) you'll edit it there. Each bug is marked in the code with a
comment like `# [VULN-2] SQL INJECTION`, so you can find them fast — but the goal is to
**recognize the pattern**, because real code won't label its own bugs.

To view it on the Pi:
```bash
cd ~/barangay-ctf/portal
nano app.py          # or: code app.py / vim app.py
```

After any edit, restart the portal so the change takes effect:
```bash
sudo systemctl restart ghostnet-portal
```

> Working on your own copy? Each Blue team should patch **their own** instance so you
> don't overwrite each other. Your instructor will tell you which box is yours.

---

## Defense 1 — Default admin password (10 pts)

**How the attack works.** The `admin` account ships with password `admin123` and nobody
changed it. Anyone who knows the default logs in as administrator.

**Root cause.** A seeded default credential that is never rotated, and passwords stored
in plain text.

**The patch.**
- Remove the default account, or force a password change on first login.
- Never store passwords in plain text — store a **hash**.

```python
from werkzeug.security import generate_password_hash, check_password_hash

# when creating a user:
# password_hash = generate_password_hash(chosen_password)

# when checking at login:
# if check_password_hash(stored_hash, submitted_password): ...
```

**Verify your fix.** `admin` / `admin123` should no longer work, and a strong unique
password should be required.

---

## Defense 2 — SQL injection on login (20 pts)

**How the attack works.** Input is concatenated straight into the SQL string, so
`' OR '1'='1' --` rewrites the query and bypasses the password check.

**Root cause.** Find this pattern in `login()`:

```python
query = ("SELECT * FROM users "
         f"WHERE username = '{username}' AND password = '{password}'")
row = cur.execute(query).fetchone()
```

User input is **inside** the query text. That is the bug, every time, in any language.

**The patch.** Use **parameterized queries** — let the database driver handle the values,
so input can never change the query's structure:

```python
row = cur.execute(
    "SELECT * FROM users WHERE username = ? AND password = ?",
    (username, password),
).fetchone()
```

Never build SQL with f-strings, `%`, or `+`. Also return a generic "invalid credentials"
message rather than leaking database errors.

**Verify your fix.** `' OR '1'='1' --` in the username should now simply fail to log in.

---

## Defense 3 — Unrestricted file upload → web shell (30 pts)

**How the attack works.** The Data Import accepts any uploaded file and then
**executes** it as Python. An attacker uploads a web shell and runs commands on the
server.

**Root cause.** Two mistakes together — no validation of the upload, and a `/run`
endpoint that executes uploaded content:

```python
f.save(dest)                       # saves ANY file, any name
...
exec(compile(fh.read(), name, "exec"))   # executes the upload
```

**The patch.** The single most important fix: **never execute uploaded files.** Delete
the `/run` endpoint entirely. Then harden the upload itself:

- **Whitelist** allowed extensions (e.g. only `.pdf`, `.csv`), and check the file's real
  content type, not just its name.
- **Rename** stored files to a random name you control.
- Store uploads **outside** any directory the app serves or runs code from.
- Limit file size.

**Verify your fix.** Uploading a `.py` web shell should no longer run — ideally the
upload is rejected, and there is no endpoint that executes it.

---

## Defense 4 — Exposed config file (15 pts)

**How the attack works.** `/download?file=../config.ini` uses `../` to climb out of the
public folder and read the credentials file.

**Root cause.** The requested filename is joined onto a base path with no containment
check:

```python
full = os.path.join(public_dir, requested)   # '../config.ini' escapes public_dir
return send_file(full, as_attachment=True)
```

**The patch.** Resolve the final path and confirm it stays **inside** the public folder;
reject anything that escapes:

```python
public_real = os.path.realpath(public_dir)
full = os.path.realpath(os.path.join(public_dir, requested))
if not full.startswith(public_real + os.sep):
    abort(403)
```

Better still, serve only an **allow-list** of known files, and keep secrets out of any
web-served directory entirely (use environment variables or a secrets store).

**Verify your fix.** `/download?file=../config.ini` should return `403` (forbidden), while
`/download?file=readme.txt` still works.

---

## Writing the attack report

For each bug, file a short report on your team page. A good report answers three things:

1. **What was the vulnerability?** (name it, and where it lived)
2. **How was it exploited?** (the attack, in one or two sentences)
3. **How did you fix it?** (the patch, and how you confirmed it works)

> *Example — SQL injection:* "The login query concatenated user input directly into the
> SQL string. The payload `' OR '1'='1' --` in the username bypassed authentication. I
> replaced it with a parameterized query using `?` placeholders; the payload now fails
> and valid logins still work."

This is the same note you would hand a real incident team. The instructor verifies the
fix and the report, then awards the points.

---

## The bigger picture — what Blue carries back to work

The four bugs map to habits, not one-off fixes:

- **Change every default.** No shipped credential survives first boot; store hashes.
- **Trust no input.** Parameterize queries, validate uploads, contain file paths.
- **Keep secrets out of reach.** Credentials belong in a secret store, never in a
  web-served file.
- **Detect, report, respond.** The win isn't only the patch — it's the reflex of
  documenting and escalating what you find.

### Mapping to NIST CSF (for the report-back)

| Function | In this exercise |
|----------|------------------|
| **Identify** | Read the app, find the inputs and the bugs |
| **Protect** | Patch: auth, input validation, path containment, secret storage |
| **Detect** | Recognize the attack patterns in logs and behavior |
| **Respond** | Write and escalate the incident report |
| **Recover** | Reset to a known-good state, confirm the fix holds |

### Stretch hardening (bonus, beyond the four)

- Turn off debug mode in production; don't expose stack traces.
- Add a strong session secret and secure session cookies.
- Rate-limit the login form; log failed attempts.
- Put the app behind HTTPS.

---
*Barangay Services Portal CTF · CyberTumbler × GhostNet Academy · For authorized training use only.*
