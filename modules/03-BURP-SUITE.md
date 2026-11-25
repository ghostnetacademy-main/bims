# 🧰 Burp Suite Field Guide
### Barangay Malinaw BIMS — intercept, tamper, attack

> **Authorized training only.** Point Burp at the training BIMS on the isolated lab
> network and nothing else. Intercepting traffic to systems you don't own or aren't
> authorized to test is illegal under the Cybercrime Prevention Act of 2012 (RA 10175).

---

## What Burp Suite is

Burp Suite is a **proxy** that sits between your browser and the web server. Every
request your browser sends passes through Burp first — so you can **see it, pause it, and
change it** before it reaches the server. It's the tool professional web pentesters live
in.

You'll use three parts of it:

| Tool | What it does |
|------|--------------|
| **Proxy / Intercept** | Pauses each request so you can read or edit it |
| **Repeater** | Resend one request over and over, changing it each time |
| **Intruder** | Automatically fire many variations (e.g. a password list) |

**Burp Community Edition is free and already installed in Kali Linux** — nothing to
download. (Community throttles Intruder's speed, which is fine for our short lists.)

---

## Setup (2 minutes)

The BIMS is plain **HTTP**, so you can skip the Burp CA-certificate step that HTTPS sites
need. Easiest path:

1. In Kali, launch **Burp Suite Community** → *Next* → *Start Burp* (temporary project).
2. Go to the **Proxy** tab → click **Open browser** (Burp's built-in Chromium, already
   wired to the proxy — no config needed).
3. In that browser, go to `http://<range-ip>:5050` — your instructor will give the
   address. You should see the BIMS login.

> Prefer Firefox? Install the **FoxyProxy** add-on, add a proxy `127.0.0.1:8080`, turn it
> on, and browse. The built-in browser is simpler for a first run.

---

## Task 1 — Intercept your first request

1. Proxy tab → **Intercept is on**.
2. In the Burp browser, submit the BIMS login with any username/password.
3. Burp pauses. Read the raw request — you can see the `username=` and `password=` you
   typed, **in the clear**. That's the first lesson: HTTP shows everything.
4. Click **Forward** to let it through, or **Drop** to cancel.

---

## Task 2 — Repeater → SQL injection (the 20-pt bug)

1. With a login request captured (Intercept on), **right-click → Send to Repeater**.
2. Turn Intercept **off**. Open the **Repeater** tab.
3. In the request, change the username value to:
   ```
   ' OR '1'='1' --
   ```
   (URL-encode the spaces if needed — Burp can do it: select the text → Ctrl-U.)
4. Click **Send**. Watch the response: a **302 redirect** to `/dashboard` instead of the
   login error means you bypassed authentication. Open it in the browser to grab the flag.

Repeater lets you try payload after payload without re-typing the whole form — this is how
real testers tune an injection.

---

## Task 3 — Intruder → brute the default password (the 10-pt bug)

1. Capture a login POST for username `admin`, **right-click → Send to Intruder**.
2. **Positions** tab → *Clear §* → highlight just the **password value** → *Add §*.
3. **Payloads** tab → *Load* the wordlist `burp/passwords.txt` (from the training kit).
4. **Start attack.** In the results, sort by **Status** or **Length** — the winning
   password (`admin123`) stands out: it returns a **302** while every wrong guess returns
   **200**.
5. Log in with it in the browser to capture the default-password flag.

This is exactly how attackers find unchanged default credentials — at scale.

---

## Task 4 — Intercept & tamper the upload → web shell (the 30-pt bug)

1. Log in, go to **Data Import**. Turn Intercept **on**.
2. Choose any small file and submit the upload. Burp pauses on the multipart request.
3. In the intercepted request, change the filename to `shell.py` and replace the file body
   with a web shell:
   ```python
   import subprocess
   print(subprocess.getoutput("cat secret/shell_flag.txt"))
   ```
4. **Forward** the request. Back in the app, click **Process** next to `shell.py` — the
   server runs it and returns the flag.

You just modified a file upload in flight — a check that only runs in the browser is no
check at all.

---

## Task 5 — Repeater → path traversal (the 15-pt bug)

1. Browse to **System** and capture the download link request, or just build it: send any
   request to **Repeater** and change the path to:
   ```
   GET /download?file=../config.ini
   ```
2. **Send.** The response body is the system config — database and backup credentials, and
   the flag in the `[secrets]` section.

---

## Appendix — PortSwigger Web Security Academy (free, needs internet)

If the venue has reliable internet, PortSwigger's **Web Security Academy**
(<https://portswigger.net/web-security>) is the best place to practice these same skills on
guided labs. It's free — just make an account. These **apprentice** labs mirror the BIMS
bugs:

| BIMS bug | Academy lab to practice on |
|----------|----------------------------|
| Default password | *Authentication:* "Username enumeration via different responses" |
| SQL injection | *SQL injection:* "…allowing login bypass" and "…retrieval of hidden data" |
| File upload shell | *File upload:* "Remote code execution via web shell upload" |
| Exposed config | *Information disclosure:* "Information disclosure in error messages" |

Do them with Burp's Proxy → Repeater → Intruder, exactly as above. The labs are HTTPS, so
you'll install Burp's CA certificate once (Proxy → *Open browser* handles it automatically;
for Firefox, visit `http://burp` and download the cert).

---
*Barangay Malinaw BIMS CTF · CyberTumbler × GhostNet Academy · For authorized training use only.*
