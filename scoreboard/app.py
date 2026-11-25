"""
================================================================================
 ATTACK-DEFENSE SCOREBOARD  --  CTF control side of the Barangay Malinaw range
================================================================================
 Runs on the INSTRUCTOR machine (not on the target). Players reach it over the
 range network; the target box never holds this code, the scores or the token.

 Players
   /            welcome page: scenario, countdown, choose Red or Blue
   /register    create a team (name + password + side)
   /login       sign back in, or join your team from another laptop
   /play        submit flags (Red) or fix reports (Blue) while the clock runs
   /board       live standings and, at the end, the winner (project this)

 Admin  (separate login, never linked from player pages)
   /admin       instructor token -> schedule, start, pause, extend, verify,
                reset. Every admin page and action requires the admin session.

 Competition clock (server time on this machine is the only clock that counts)
   waiting -> scheduled -> live -> ended      (live can be paused / extended)
   Submissions are accepted only while the phase is "live".

 Points come from ../flags.json, shared with the target's flag values.
================================================================================
"""

import os
import hmac
import json
import time
import sqlite3
import secrets
import datetime
from flask import (
    Flask, request, redirect, url_for, session,
    render_template, flash, abort, jsonify,
)
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
DB_PATH     = os.path.join(BASE_DIR, "scoreboard.db")
FLAGS_PATH  = os.path.join(PROJECT_DIR, "flags.json")
FLAGS2_PATH = os.path.join(PROJECT_DIR, "flags2.json")
KEY_PATH    = os.path.join(BASE_DIR, ".session_key")

VULN_LABELS = {
    "default_password": "Default admin password",
    "sql_injection":    "SQL injection on login",
    "file_upload":      "Unrestricted upload / web shell",
    "exposed_config":   "Exposed config with credentials",
}

# Who may submit while the clock is live.
MODES = {1: "Red only", 2: "Blue only", 3: "Red and Blue"}
DEFAULT_MINUTES = 30
DEFAULT_TITLE   = "CyberSkills 102: Barangay Malinaw Attack-Defense"


# ---------------------------------------------------------------------------
#  Secrets: never fall back to a guessable default
# ---------------------------------------------------------------------------
def _session_key():
    """Random key, kept on disk so team logins survive a scoreboard restart."""
    env = os.environ.get("CTF_SECRET_KEY")
    if env:
        return env
    if not os.path.exists(KEY_PATH):
        fd = os.open(KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(secrets.token_hex(32))
    with open(KEY_PATH) as fh:
        return fh.read().strip()


def _instructor_token():
    token = os.environ.get("CTF_INSTRUCTOR_TOKEN", "").strip()
    if token:
        return token
    token = secrets.token_urlsafe(9)
    print("\n" + "=" * 62)
    print(" CTF_INSTRUCTOR_TOKEN was not set. Generated one for this run:")
    print(f"   {token}")
    print(" Use it at /admin. Set CTF_INSTRUCTOR_TOKEN to choose your own.")
    print("=" * 62 + "\n", flush=True)
    return token


app = Flask(__name__)
app.secret_key = _session_key()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_NAME="ctf_scoreboard",
    MAX_CONTENT_LENGTH=64 * 1024,
)
INSTRUCTOR_TOKEN = _instructor_token()


# ---------------------------------------------------------------------------
#  Flags / points  (authoritative copy is ../flags.json on THIS machine)
# ---------------------------------------------------------------------------
def load_flags():
    with open(FLAGS_PATH) as fh:
        return json.load(fh)


def points_for(key):
    return load_flags()["flags"][key]["points"]


def flag_lookup():
    """Return {flag_value: vuln_key} across all target boxes (flags.json + flags2.json)."""
    lookup = {}
    for path in (FLAGS_PATH, FLAGS2_PATH):
        try:
            with open(path) as fh:
                data = json.load(fh)
        except (FileNotFoundError, ValueError):
            continue
        for k, v in data.get("flags", {}).items():
            lookup[v["value"]] = k
    return lookup


# ---------------------------------------------------------------------------
#  Database
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS teams (
            id      INTEGER PRIMARY KEY,
            name    TEXT UNIQUE,
            side    TEXT,              -- 'red' or 'blue'
            pw_hash TEXT
        );
        CREATE TABLE IF NOT EXISTS captures (
            id      INTEGER PRIMARY KEY,
            team_id INTEGER,
            vuln    TEXT,
            points  INTEGER,
            ts      REAL,
            UNIQUE(team_id, vuln)
        );
        CREATE TABLE IF NOT EXISTS patches (
            id      INTEGER PRIMARY KEY,
            team_id INTEGER,
            vuln    TEXT,
            report  TEXT,
            status  TEXT,          -- 'pending' | 'verified' | 'rejected'
            points  INTEGER,
            ts      REAL,
            UNIQUE(team_id, vuln)
        );
        CREATE TABLE IF NOT EXISTS state (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    # Upgrade a scoreboard.db created by the earlier version of this kit.
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(teams)")]
    if "pw_hash" not in cols:
        conn.execute("ALTER TABLE teams ADD COLUMN pw_hash TEXT")
    defaults = {
        "mode": "3",
        "comp_start": "0",
        "comp_duration": str(DEFAULT_MINUTES * 60),
        "planned_minutes": str(DEFAULT_MINUTES),
        "comp_paused_at": "0",
        "target_url": "",
        "event_title": DEFAULT_TITLE,
    }
    for key, value in defaults.items():
        conn.execute("INSERT OR IGNORE INTO state (key,value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


def state_all():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM state").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def state_set(**pairs):
    conn = get_db()
    for key, value in pairs.items():
        conn.execute(
            "INSERT INTO state (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
#  Competition clock
# ---------------------------------------------------------------------------
def _minutes(raw, fallback):
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return fallback
    return value if 1 <= value <= 600 else fallback


def fmt_when(epoch):
    """Local wall-clock time of this machine, e.g. 'Fri Nov 20, 1:00 PM'."""
    t = time.localtime(epoch)
    hour = t.tm_hour % 12 or 12
    return time.strftime("%a %b %d, ", t) + f"{hour}:{t.tm_min:02d} " + ("AM" if t.tm_hour < 12 else "PM")


def clock():
    """Everything the pages need to know about the competition window."""
    st = state_all()
    now = time.time()
    start = float(st.get("comp_start", "0") or 0)
    duration = float(st.get("comp_duration", DEFAULT_MINUTES * 60) or 0)
    paused_at = float(st.get("comp_paused_at", "0") or 0)
    try:
        mode = int(st.get("mode", "3"))
    except ValueError:
        mode = 3
    if mode not in MODES:
        mode = 3
    end = start + duration

    if start <= 0:
        phase, target, remaining = "waiting", 0, int(duration)
    elif paused_at > 0:
        phase, target, remaining = "paused", 0, max(0, int(end - paused_at))
    elif now < start:
        phase, target, remaining = "scheduled", start, int(duration)
    elif now < end:
        phase, target, remaining = "live", end, max(0, int(end - now))
    else:
        phase, target, remaining = "ended", 0, 0

    return {
        "phase": phase,
        "now": now,
        "start": start,
        "end": end,
        "duration": duration,
        "minutes": max(1, round(duration / 60)),
        "planned": _minutes(st.get("planned_minutes"), DEFAULT_MINUTES),  # for form defaults
        "target": target,                 # epoch the countdown runs toward
        "remaining": remaining,           # seconds of play left
        "mode": mode,
        "mode_label": MODES[mode],
        "start_text": fmt_when(start) if start > 0 else "",
        "end_text": fmt_when(end) if start > 0 else "",
        "target_url": st.get("target_url", ""),
        "event_title": st.get("event_title") or DEFAULT_TITLE,
        # Changes whenever the clock state changes; pages poll and react.
        "version": f"{phase}:{int(start)}:{int(duration)}:{int(paused_at)}:{mode}",
    }


def side_open(side, ck=None):
    """True only while the clock is live AND this side is allowed to submit."""
    ck = ck or clock()
    if ck["phase"] != "live":
        return False
    if ck["mode"] == 1:
        return side == "red"
    if ck["mode"] == 2:
        return side == "blue"
    return True


def closed_reason(side, ck):
    if ck["phase"] == "waiting":
        return "The competition has not started yet. Wait for the instructor."
    if ck["phase"] == "scheduled":
        return f"The competition has not started yet. It opens {ck['start_text']}."
    if ck["phase"] == "paused":
        return "The competition is paused. Hands off until the instructor resumes."
    if ck["phase"] == "ended":
        return "Time is up. Submissions are closed."
    return f"Your side is not open right now ({ck['mode_label']})."


# ---------------------------------------------------------------------------
#  Scoring
# ---------------------------------------------------------------------------
def team_scores():
    """Ranked by points, then by who reached their score first."""
    conn = get_db()
    teams = conn.execute("SELECT id, name, side FROM teams").fetchall()
    caps = conn.execute(
        "SELECT team_id, SUM(points) AS pts, MAX(ts) AS last FROM captures GROUP BY team_id"
    ).fetchall()
    pats = conn.execute(
        "SELECT team_id, SUM(points) AS pts, MAX(ts) AS last FROM patches "
        "WHERE status='verified' GROUP BY team_id"
    ).fetchall()
    conn.close()
    cap = {r["team_id"]: r for r in caps}
    pat = {r["team_id"]: r for r in pats}
    scored = []
    for t in teams:
        row = (cap if t["side"] == "red" else pat).get(t["id"])
        scored.append({
            "name": t["name"],
            "side": t["side"],
            "points": int(row["pts"]) if row else 0,
            "last": float(row["last"]) if row else None,
        })
    scored.sort(key=lambda s: (-s["points"], s["last"] if s["last"] is not None else float("inf"),
                               s["name"].lower()))
    return scored


def results(scores):
    """Winner summary for the end screen."""
    def best(rows):
        rows = [r for r in rows if r["points"] > 0]
        return rows[0] if rows else None

    winner = best(scores)
    tie = bool(winner and len(scores) > 1 and scores[1]["points"] == winner["points"])
    conn = get_db()
    pending = conn.execute("SELECT COUNT(*) FROM patches WHERE status='pending'").fetchone()[0]
    conn.close()
    return {
        "winner": winner,
        "tie": tie,
        "best_red": best([s for s in scores if s["side"] == "red"]),
        "best_blue": best([s for s in scores if s["side"] == "blue"]),
        "pending": pending,
    }


def board_version(ck, scores):
    conn = get_db()
    pending = conn.execute("SELECT COUNT(*) FROM patches WHERE status='pending'").fetchone()[0]
    conn.close()
    body = "|".join(f"{s['name']}:{s['side']}:{s['points']}" for s in scores)
    return f"{ck['version']}#{pending}#{body}"


# ---------------------------------------------------------------------------
#  Sessions: players and admin are separate
# ---------------------------------------------------------------------------
def current_team():
    tid = session.get("team_id")
    if not tid:
        return None
    conn = get_db()
    row = conn.execute("SELECT * FROM teams WHERE id=?", (tid,)).fetchone()
    conn.close()
    if row is None:               # team was wiped by a full reset
        session.pop("team_id", None)
    return row


def is_admin():
    return session.get("admin") is True


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def require_admin():
    """Guard for every admin page and action. Players get a plain 404."""
    if not is_admin():
        abort(404)
    if request.method == "POST":
        sent = request.form.get("csrf", "")
        if not hmac.compare_digest(sent, session.get("csrf", "")):
            abort(400)


# Slow down guessing of the admin token and of team passwords.
_FAILS = {}
MAX_FAILS, LOCK_SECONDS = 5, 60


def _locked(bucket):
    count, until = _FAILS.get(bucket, (0, 0))
    return until > time.time()


def _fail(bucket):
    count, until = _FAILS.get(bucket, (0, 0))
    count += 1
    if count >= MAX_FAILS:
        _FAILS[bucket] = (0, time.time() + LOCK_SECONDS)
    else:
        _FAILS[bucket] = (count, 0)


def _ok(bucket):
    _FAILS.pop(bucket, None)


@app.context_processor
def inject_common():
    return {
        "ck": clock(),
        "me": current_team(),
        "admin": is_admin(),
        "csrf": csrf_token,
        "labels": VULN_LABELS,
    }


@app.after_request
def harden(resp):
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Cache-Control", "no-store")
    return resp


# ---------------------------------------------------------------------------
#  Public pages
# ---------------------------------------------------------------------------
@app.route("/")
def welcome():
    flags = load_flags()["flags"]
    return render_template(
        "welcome.html",
        points={k: flags[k]["points"] for k in VULN_LABELS},
        total=sum(flags[k]["points"] for k in VULN_LABELS),
    )


@app.route("/board")
def scoreboard():
    ck = clock()
    scores = team_scores()
    flags = load_flags()["flags"]
    return render_template(
        "scoreboard.html",
        scores=scores,
        res=results(scores),
        points={k: flags[k]["points"] for k in VULN_LABELS},
        page_version=board_version(ck, scores),
    )


@app.route("/api/status")
def api_status():
    ck = clock()
    return jsonify({
        "phase": ck["phase"],
        "now": ck["now"],
        "target": ck["target"],
        "remaining": ck["remaining"],
        "clock": ck["version"],
        "board": board_version(ck, team_scores()),
    })


# ---------------------------------------------------------------------------
#  Player accounts
# ---------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    side_hint = request.args.get("side", "")
    if request.method == "POST":
        name = " ".join(request.form.get("name", "").split())
        side = request.form.get("side", "")
        pw = request.form.get("password", "")
        if not (2 <= len(name) <= 40) or side not in ("red", "blue"):
            flash("Pick a team name (2 to 40 characters) and a side.")
            return redirect(url_for("register", side=side if side in ("red", "blue") else None))
        if len(pw) < 6 or len(pw) > 128:
            flash("Choose a team password of at least 6 characters.")
            return redirect(url_for("register", side=side))
        conn = get_db()
        try:
            # Team names are unique regardless of capitals ("Alpha" == "alpha").
            if conn.execute("SELECT 1 FROM teams WHERE name=? COLLATE NOCASE", (name,)).fetchone():
                raise sqlite3.IntegrityError
            cur = conn.execute(
                "INSERT INTO teams (name, side, pw_hash) VALUES (?,?,?)",
                (name, side, generate_password_hash(pw)),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("That team name is taken. If it is your team, sign in instead.")
            return redirect(url_for("register", side=side))
        session["team_id"] = cur.lastrowid
        conn.close()
        return redirect(url_for("play"))
    return render_template("register.html", side_hint=side_hint if side_hint in ("red", "blue") else "")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = " ".join(request.form.get("name", "").split())
        pw = request.form.get("password", "")
        bucket = ("team", request.remote_addr, name.lower())
        if _locked(bucket):
            flash("Too many wrong tries. Wait a minute and try again.")
            return redirect(url_for("login"))
        conn = get_db()
        row = conn.execute("SELECT * FROM teams WHERE name=? COLLATE NOCASE", (name,)).fetchone()
        conn.close()
        if row is None or not row["pw_hash"] or not check_password_hash(row["pw_hash"], pw):
            _fail(bucket)
            flash("Wrong team name or password.")
            return redirect(url_for("login"))
        _ok(bucket)
        session["team_id"] = row["id"]
        return redirect(url_for("play"))
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("team_id", None)
    return redirect(url_for("welcome"))


@app.route("/play")
def play():
    team = current_team()
    if not team:
        return redirect(url_for("login"))
    ck = clock()
    conn = get_db()
    caps = conn.execute(
        "SELECT vuln, points FROM captures WHERE team_id=?", (team["id"],)
    ).fetchall()
    pats = conn.execute(
        "SELECT vuln, status, points FROM patches WHERE team_id=?", (team["id"],)
    ).fetchall()
    conn.close()
    flags = load_flags()["flags"]
    is_open = side_open(team["side"], ck)
    my_points = (sum(c["points"] for c in caps) if team["side"] == "red"
                 else sum(p["points"] for p in pats if p["status"] == "verified"))
    return render_template(
        "play.html",
        team=team,
        captures={c["vuln"]: c["points"] for c in caps},
        patches={p["vuln"]: p for p in pats},
        open_for_me=is_open,
        closed_reason="" if is_open else closed_reason(team["side"], ck),
        points={k: flags[k]["points"] for k in VULN_LABELS},
        my_points=my_points,
    )


# --- Red: submit a captured flag -------------------------------------------
@app.route("/submit-flag", methods=["POST"])
def submit_flag():
    team = current_team()
    if not team:
        return redirect(url_for("login"))
    if team["side"] != "red":
        flash("Only Red teams submit flags.")
        return redirect(url_for("play"))
    ck = clock()
    if not side_open("red", ck):
        flash(closed_reason("red", ck))
        return redirect(url_for("play"))

    submitted = request.form.get("flag", "").strip()[:200]
    match = flag_lookup().get(submitted)
    if not match:
        flash("That flag is not valid.")
        return redirect(url_for("play"))

    pts = points_for(match)
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO captures (team_id, vuln, points, ts) VALUES (?,?,?,?)",
            (team["id"], match, pts, time.time()),
        )
        conn.commit()
        flash(f"Captured: {VULN_LABELS[match]} (+{pts}).")
    except sqlite3.IntegrityError:
        flash("Your team already scored that flag.")
    conn.close()
    return redirect(url_for("play"))


# --- Blue: file a fix report -----------------------------------------------
@app.route("/submit-patch", methods=["POST"])
def submit_patch():
    team = current_team()
    if not team:
        return redirect(url_for("login"))
    if team["side"] != "blue":
        flash("Only Blue teams file fix reports.")
        return redirect(url_for("play"))
    ck = clock()
    if not side_open("blue", ck):
        flash(closed_reason("blue", ck))
        return redirect(url_for("play"))

    vuln = request.form.get("vuln", "")
    report = request.form.get("report", "").strip()[:2000]
    if vuln not in VULN_LABELS:
        flash("Unknown weakness.")
        return redirect(url_for("play"))
    if len(report) < 20:
        flash("Describe the weakness and your fix in at least a sentence or two.")
        return redirect(url_for("play"))

    pts = points_for(vuln)
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO patches (team_id, vuln, report, status, points, ts) "
            "VALUES (?,?,?,?,?,?)",
            (team["id"], vuln, report, "pending", pts, time.time()),
        )
        conn.commit()
        flash("Report filed. Waiting for the instructor to verify it.")
    except sqlite3.IntegrityError:
        flash("Your team already filed a report for that weakness.")
    conn.close()
    return redirect(url_for("play"))


# ---------------------------------------------------------------------------
#  Admin (instructor) panel: separate login, hidden from players
# ---------------------------------------------------------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    if request.method == "POST" and not is_admin():
        bucket = ("admin", request.remote_addr)
        if _locked(bucket):
            flash("Too many wrong tries. Wait a minute.")
            return redirect(url_for("admin_panel"))
        sent = request.form.get("token", "")
        if hmac.compare_digest(sent.encode(), INSTRUCTOR_TOKEN.encode()):
            _ok(bucket)
            session["admin"] = True
            session["csrf"] = secrets.token_hex(16)
        else:
            _fail(bucket)
            flash("Wrong instructor token.")
        return redirect(url_for("admin_panel"))

    if not is_admin():
        return render_template("instructor_login.html")

    conn = get_db()
    reports = conn.execute(
        """SELECT p.id, t.name, t.side, p.vuln, p.report, p.points, p.status
           FROM patches p JOIN teams t ON t.id=p.team_id
           ORDER BY (p.status='pending') DESC, p.ts DESC"""
    ).fetchall()
    teams = conn.execute("SELECT id, name, side FROM teams ORDER BY side, name").fetchall()
    conn.close()
    ck = clock()
    default_start = time.localtime(ck["start"] if ck["start"] > 0 else time.time() + 600)
    return render_template(
        "instructor.html",
        reports=reports,
        teams=teams,
        scores=team_scores(),
        modes=MODES,
        form_date=time.strftime("%Y-%m-%d", default_start),
        form_time=time.strftime("%H:%M", default_start),
        server_time=fmt_when(time.time()),
        tz_name=time.strftime("%Z"),
    )


@app.route("/instructor")
def instructor_alias():
    """Old address from the first version of the kit."""
    if not is_admin():
        abort(404)
    return redirect(url_for("admin_panel"))


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    require_admin()
    session.pop("admin", None)
    return redirect(url_for("welcome"))


@app.route("/admin/schedule", methods=["POST"])
def admin_schedule():
    require_admin()
    minutes = _minutes(request.form.get("minutes"), DEFAULT_MINUTES)
    try:
        mode = int(request.form.get("mode", "3"))
    except ValueError:
        mode = 3
    if mode not in MODES:
        mode = 3
    title = " ".join(request.form.get("event_title", "").split())[:80] or DEFAULT_TITLE
    target_url = request.form.get("target_url", "").strip()[:120]
    if target_url and not target_url.startswith(("http://", "https://")):
        target_url = "http://" + target_url

    settings = dict(mode=mode, planned_minutes=minutes, event_title=title, target_url=target_url)
    if clock()["phase"] in ("waiting", "scheduled", "ended"):
        # Never shorten or stretch a round that is running; use Add minutes for that.
        settings["comp_duration"] = minutes * 60
    date_s = request.form.get("date", "").strip()
    time_s = request.form.get("time", "").strip()
    if date_s and time_s:
        try:
            # Naive local time of THIS machine (set the Mac to Philippine time).
            start = datetime.datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M").timestamp()
        except ValueError:
            flash("Could not read that date and time.")
            return redirect(url_for("admin_panel"))
        if start <= time.time():
            flash("That start time is already past. Pick a later time, or use Start now.")
            return redirect(url_for("admin_panel"))
        settings.update(comp_start=start, comp_paused_at=0)
        state_set(**settings)
        flash(f"Scheduled: opens {fmt_when(start)} for {minutes} minutes ({MODES[mode]}).")
    else:
        state_set(**settings)
        flash("Settings saved. No start time set yet.")
    return redirect(url_for("admin_panel"))


@app.route("/admin/clock/<action>", methods=["POST"])
def admin_clock(action):
    require_admin()
    ck = clock()
    now = time.time()
    if action == "start":
        minutes = _minutes(request.form.get("minutes"), ck["planned"])
        state_set(comp_start=now, comp_duration=minutes * 60, comp_paused_at=0, planned_minutes=minutes)
        flash(f"Competition started. {minutes} minutes on the clock.")
    elif action == "pause" and ck["phase"] == "live":
        state_set(comp_paused_at=now)
        flash("Paused. Submissions are closed until you resume.")
    elif action == "resume" and ck["phase"] == "paused":
        paused_at = float(state_all().get("comp_paused_at", "0"))
        state_set(comp_start=ck["start"] + (now - paused_at), comp_paused_at=0)
        flash("Resumed. The clock continues from where it stopped.")
    elif action == "extend" and ck["phase"] in ("live", "paused", "ended"):
        extra = _minutes(request.form.get("minutes"), 5) * 60
        if ck["phase"] == "ended":
            # Reopen for exactly the extra time, counted from now.
            state_set(comp_duration=(now - ck["start"]) + extra)
        else:
            state_set(comp_duration=ck["duration"] + extra)
        flash(f"Added {extra // 60} minutes.")
    elif action == "end" and ck["phase"] in ("live", "paused"):
        # A paused clock ends at the moment it was paused; a live one ends now.
        stop = float(state_all().get("comp_paused_at", "0")) or now
        state_set(comp_start=ck["start"] + (now - stop), comp_duration=now - (ck["start"] + (now - stop)),
                  comp_paused_at=0)
        flash("Competition ended. Submissions are closed.")
    elif action == "clear":
        state_set(comp_start=0, comp_paused_at=0)
        flash("Schedule cleared. The competition is back to waiting.")
    else:
        flash("That action does not apply right now.")
    return redirect(url_for("admin_panel"))


@app.route("/admin/verify/<int:pid>/<decision>", methods=["POST"])
def admin_verify(pid, decision):
    require_admin()
    if decision not in ("approve", "reject"):
        abort(400)
    status = "verified" if decision == "approve" else "rejected"
    conn = get_db()
    conn.execute("UPDATE patches SET status=? WHERE id=?", (status, pid))
    conn.commit()
    conn.close()
    flash(f"Report #{pid} {status}.")
    return redirect(url_for("admin_panel"))


@app.route("/admin/team/<int:tid>/password", methods=["POST"])
def admin_team_password(tid):
    """A team forgot its password: set a new one for them."""
    require_admin()
    pw = request.form.get("password", "")
    if len(pw) < 6:
        flash("Team passwords need at least 6 characters.")
        return redirect(url_for("admin_panel"))
    conn = get_db()
    conn.execute("UPDATE teams SET pw_hash=? WHERE id=?", (generate_password_hash(pw), tid))
    conn.commit()
    conn.close()
    flash("Team password changed.")
    return redirect(url_for("admin_panel"))


@app.route("/admin/reset/<what>", methods=["POST"])
def admin_reset(what):
    require_admin()
    conn = get_db()
    if what == "scores":
        conn.execute("DELETE FROM captures")
        conn.execute("DELETE FROM patches")
        conn.commit()
        conn.close()
        flash("Scores cleared. Teams and schedule kept.")
    elif what == "all":
        conn.execute("DELETE FROM captures")
        conn.execute("DELETE FROM patches")
        conn.execute("DELETE FROM teams")
        conn.commit()
        conn.close()
        state_set(comp_start=0, comp_paused_at=0)
        flash("Full reset: teams, scores and schedule cleared.")
    else:
        conn.close()
        abort(400)
    return redirect(url_for("admin_panel"))


init_db()

if __name__ == "__main__":
    # Never run this with debug=True: the range network is full of attackers.
    app.run(host="0.0.0.0", port=5001, debug=False)
