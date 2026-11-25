# Facilitator cheat-sheet — intended solutions & patches

Keep this file off the players' machines. It is the answer key plus the Blue-team fixes.

---

## VULN-1 — Default admin password (10 pts)

**Attack.** Go to `/login`, sign in with `admin` / `admin123`. The dashboard prints the flag.

**Why it's there.** The seeded admin account was never rotated from its factory password.

**Blue patch.** Force a password change on first login; remove the seeded default; store
password hashes (e.g. `werkzeug.security.generate_password_hash`) instead of plaintext.

---

## VULN-2 — SQL injection on the login form (20 pts)

**Attack (auth bypass path).** Username: `' OR '1'='1' --`  Password: anything.
A row returns but the password doesn't actually match → the app detects the bypass and
prints the SQL-injection flag.

**The real teaching moment.** Once logged in (by bypass or by the default password), the
attacker can browse the full **Residents** registry — 160 fictional constituents with
birthdates, addresses, contact and PhilSys numbers. That PII exposure is the point; the
flag just scores it. (The flag is also seeded into the `system_notes` table as the admin's
private note — any injection-based login reveals it on the dashboard.)

**Blue patch.** Parameterize the query:
```python
cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
```
Never build SQL with f-strings/`%`. Add input validation and generic error messages.

---

## VULN-3 — Unrestricted file upload → web shell (30 pts)

**Attack.** Log in (any valid or injected session), go to `/reports`, upload
`facilitator/webshell_report.py` (or any Python), then click **Run**. `/run` executes it
and returns the output — the web shell reads `secret/shell_flag.txt`.

**Blue patch.** Never execute uploaded content. Whitelist extensions, verify content-type
and size, randomize stored filenames, store uploads outside any code path, and serve them
with `Content-Disposition: attachment` only. Delete the `/run` endpoint entirely.

---

## VULN-4 — Exposed config file with credentials (15 pts)

**Attack.** The `/download` endpoint has a path-traversal flaw. Request:
`/download?file=../config.ini`
The returned file contains DB/SMTP creds and the `exposed_config` flag in `[secrets]`.

**Blue patch.** Resolve and contain the path:
```python
full = os.path.realpath(os.path.join(public_dir, requested))
if not full.startswith(os.path.realpath(public_dir) + os.sep): abort(403)
```
Reject `..` and absolute paths; keep secrets out of any web-served directory; load config
from an env/secret store.

---

## Running the rounds

| Round | Name | Open | Set it with |
|------|------|------|-------------|
| 1 | Attack | Red flag submission | Instructor panel → Round 1, timer e.g. 25 min |
| 2 | Defend | Blue patch reports | `reset_flags.py --round 2` on portal box, then Instructor → Round 2 |
| 3 | Finale | Both | `reset_flags.py --round 3` on portal box, then Instructor → Round 3 |

Between rounds: **(a)** run `reset_flags.py` on the portal box to rotate flags + re-seed
the target, **(b)** copy `flags.json` to the scoreboard box if it's separate, **(c)**
restart the portal, **(d)** in the Instructor panel click *Clear scores (keep teams)* and
set the new round/timer.
