"""
================================================================================
 BARANGAY MALINAW -- INFORMATION MANAGEMENT SYSTEM (BIMS)
 DELIBERATELY VULNERABLE TRAINING TARGET
================================================================================
 A fictional Local Government Unit information system, populated with invented
 resident, household, certificate, business and blotter records, planted with
 four classic vulnerabilities for a controlled, host-only training range.

 !!  DO NOT DEPLOY ON A REAL OR INTERNET-FACING NETWORK  !!
     Insecure BY DESIGN. Run only inside an isolated VM or appliance.

 The four planted bugs (each hides a flag):
   [VULN-1] Default admin password ............... 10 pts  (default_password)
   [VULN-2] SQL injection on the login form ...... 20 pts  (sql_injection)
   [VULN-3] Unrestricted file upload -> web shell  30 pts  (file_upload)
   [VULN-4] Exposed config file with credentials . 15 pts  (exposed_config)

 Setting: Barangay Malinaw, Municipality of Bayanihan (fictional). All data
 invented. Flags read from ../flags.json so they rotate between rounds.
================================================================================
"""

import os
import io
import json
import sqlite3
import contextlib
from flask import (
    Flask, request, redirect, url_for, session,
    render_template, send_file, Response, abort,
)
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seed_bims

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
DB_PATH     = os.path.join(BASE_DIR, "portal.db")
UPLOAD_DIR  = os.path.join(BASE_DIR, "uploads")
SECRET_DIR  = os.path.join(BASE_DIR, "secret")
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")
FLAGS_PATH  = os.path.join(PROJECT_DIR, "flags.json")

BRGY = "Barangay Malinaw"
MUNI = "Municipality of Bayanihan"

app = Flask(__name__)
app.secret_key = "bims-malinaw-insecure-key"


# ---------------------------------------------------------------------------
#  Flags (shared with the scoreboard via flags.json)
# ---------------------------------------------------------------------------
def load_flags():
    with open(FLAGS_PATH) as fh:
        return json.load(fh)["flags"]

def flag(key):
    return load_flags()[key]["value"]

def load_round():
    with open(FLAGS_PATH) as fh:
        data = json.load(fh)
    return {"number": data.get("round"), "name": data.get("round_name")}


# ---------------------------------------------------------------------------
#  Database
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_seeded():
    if not os.path.exists(DB_PATH):
        seed_bims.build(DB_PATH, load_flags())

def ensure_config():
    if os.path.exists(CONFIG_PATH):
        return
    # [VULN-4] Live credentials AND a flag, meant to be unreachable but leaked
    #          by the /download path-traversal bug below.
    with open(CONFIG_PATH, "w") as fh:
        fh.write(
            "[database]\n"
            "engine = sqlite\n"
            "name = bims_malinaw\n"
            "user = bims_admin\n"
            "password = Mal1naw_DB!2021\n"
            "\n"
            "[backup]\n"
            "destination = /srv/bims/backup\n"
            "ftp_user = brgy_backup\n"
            "ftp_password = B@ckup2021!\n"
            "\n"
            "[smtp]\n"
            "user = notices@malinaw.example\n"
            "password = MailP@ss2021\n"
            "\n"
            "[secrets]\n"
            f"ctf_flag = {flag('exposed_config')}\n"
        )

def ensure_shell_flag():
    os.makedirs(SECRET_DIR, exist_ok=True)
    with open(os.path.join(SECRET_DIR, "shell_flag.txt"), "w") as fh:
        fh.write(flag("file_upload") + "\n")


# ---------------------------------------------------------------------------
#  Auth helpers
# ---------------------------------------------------------------------------
def current_user():
    return session.get("user")

def login_required():
    return "user" in session

def stats():
    conn = get_db()
    def n(q):
        return conn.execute(q).fetchone()[0]
    s = {
        "residents": n("SELECT COUNT(*) FROM residents"),
        "households": n("SELECT COUNT(*) FROM households"),
        "seniors": n("SELECT COUNT(*) FROM residents WHERE senior=1"),
        "voters": n("SELECT COUNT(*) FROM residents WHERE voter=1"),
        "pwd": n("SELECT COUNT(*) FROM residents WHERE pwd=1"),
        "businesses": n("SELECT COUNT(*) FROM businesses"),
        "certs": n("SELECT COUNT(*) FROM certificates"),
        "blotter_open": n("SELECT COUNT(*) FROM blotter WHERE status IN ('Pending','For mediation')"),
    }
    recent = conn.execute(
        "SELECT resident, type, date_issued FROM certificates ORDER BY date_issued DESC LIMIT 6").fetchall()
    officials = conn.execute("SELECT name, position FROM officials ORDER BY id LIMIT 4").fetchall()
    conn.close()
    return s, recent, officials


# ---------------------------------------------------------------------------
#  Routes -- auth
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
#  Public homepage (no login). Presentation only: none of the four training
#  exercises live here, and it shows nothing beyond public office information.
# ---------------------------------------------------------------------------
_AV_SKIN  = ["#f2cfae", "#e6b98f", "#d19f72", "#b98155"]
_AV_HAIR  = ["#17110e", "#241812", "#33251b", "#5b5b5b", "#9a9a9a"]
_AV_SHIRT = ["#0f5138", "#1f4d7a", "#7a2f2f", "#5a3a7a", "#8a6a1f", "#2f6f73"]
_AV_BACK  = ["#dcefe6", "#e3ecf7", "#f7e9d7", "#ece4f5", "#e2f1f2", "#f5e3e3"]
_AV_LONG  = {"Corazon", "Marilou", "Divina", "Josefa", "Analyn", "Maria", "Liza", "Rosalinda"}

def avatar(name):
    """Deterministic illustrated avatar (drawn in the template, no image files)."""
    clean = name.replace("Hon.", "").strip()
    parts = clean.split()
    seed = sum((i + 1) * ord(ch) for i, ch in enumerate(clean))
    first = parts[0] if parts else ""
    return {
        "skin":  _AV_SKIN[seed % len(_AV_SKIN)],
        "hair":  _AV_HAIR[(seed // 3) % len(_AV_HAIR)],
        "shirt": _AV_SHIRT[(seed // 7) % len(_AV_SHIRT)],
        "back":  _AV_BACK[(seed // 11) % len(_AV_BACK)],
        "style": "long" if first in _AV_LONG else ("short", "part")[seed % 2],
        "initials": (first[:1] + (parts[-1][:1] if len(parts) > 1 else "")).upper(),
    }

ANNOUNCEMENTS = [
    ("Nov 18", "Barangay Clean-Up Drive",
     "Saturday, 6:00 AM at the covered court. Bring gloves and a sack; snacks are on the barangay."),
    ("Nov 16", "Free Anti-Rabies Vaccination for Pets",
     "Municipal Veterinary Office visits Purok 3 on Nov 24, 8:00 AM to 12:00 NN. One owner per pet."),
    ("Nov 12", "Certificates Now Released Same Day",
     "Clearance and residency requests filed before 3:00 PM are released the same afternoon."),
    ("Nov 08", "Senior Citizens' Social Pension Payout",
     "Payout at the Barangay Hall on Nov 27. Bring your OSCA ID and one photocopy."),
]

SERVICES = [
    ("Barangay Clearance", "For employment, loans and other transactions.", "₱50"),
    ("Certificate of Residency", "Proof that you live in Barangay Malinaw.", "₱30"),
    ("Business Clearance", "Needed before a municipal business permit.", "₱100"),
    ("Certificate of Indigency", "For medical, burial and scholarship aid.", "Free"),
    ("Blotter and Mediation", "File a complaint or request Lupon mediation.", "Free"),
    ("First-Time Jobseeker", "Fee waiver under RA 11261.", "Free"),
]

@app.route("/")
def index():
    conn = get_db()
    people = conn.execute("SELECT name, position, term FROM officials ORDER BY id").fetchall()
    def n(q):
        return conn.execute(q).fetchone()[0]
    counts = {
        "residents": n("SELECT COUNT(*) FROM residents"),
        "households": n("SELECT COUNT(*) FROM households"),
        "businesses": n("SELECT COUNT(*) FROM businesses"),
        "puroks": n("SELECT COUNT(DISTINCT purok) FROM residents"),
    }
    conn.close()
    officials_list = [{"name": p["name"], "position": p["position"], "av": avatar(p["name"])}
                      for p in people]
    return render_template("home.html", brgy=BRGY, muni=MUNI, officials=officials_list,
                           announcements=ANNOUNCEMENTS, services=SERVICES, counts=counts,
                           active="home", **ctx())


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        conn = get_db()
        cur = conn.cursor()

        # ================================================================
        # [VULN-2] SQL INJECTION -- user input concatenated into the query
        # with no parameterization. ' OR '1'='1' --  bypasses auth; UNION
        # payloads can reach other tables (e.g. system_notes).
        #   FIX: cur.execute("...WHERE username=? AND password=?", (u, p))
        # ================================================================
        query = ("SELECT * FROM users "
                 f"WHERE username = '{username}' AND password = '{password}'")
        row = None
        try:
            row = cur.execute(query).fetchone()
        except sqlite3.Error as exc:
            error = f"Database error: {exc}"
        conn.close()

        if row is not None:
            legit = (row["username"] == username and row["password"] == password)
            if legit and row["role"] == "administrator" and password == "admin123":
                # [VULN-1] logged in with the untouched DEFAULT admin password
                session["user"] = row["username"]
                session["name"] = row["full_name"]
                session["role"] = row["role"]
                session["captured"] = ["default_password", flag("default_password")]
                return redirect(url_for("dashboard"))
            elif legit:
                session["user"] = row["username"]
                session["name"] = row["full_name"]
                session["role"] = row["role"]
                return redirect(url_for("dashboard"))
            else:
                # bypassed via SQL injection
                session["user"] = (row["username"] or "?") + " (via injection)"
                session["name"] = "Unknown"
                session["role"] = row["role"] or "administrator"
                session["captured"] = ["sql_injection", flag("sql_injection")]
                return redirect(url_for("dashboard"))
        elif error is None:
            error = "Invalid username or password."
    return render_template("login.html", error=error, brgy=BRGY, muni=MUNI)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
#  Routes -- the BIMS modules
# ---------------------------------------------------------------------------
@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))
    s, recent, officials = stats()
    captured = session.pop("captured", None)
    return render_template("dashboard.html", brgy=BRGY, muni=MUNI, s=s,
                           recent=recent, officials=officials,
                           captured=captured, **ctx())


@app.route("/residents")
def residents():
    if not login_required():
        return redirect(url_for("login"))
    q = request.args.get("q", "").strip()
    conn = get_db()
    # Parameterized on purpose -- the lesson here is the PII exposure once you're
    # authenticated, not a second injection point.
    if q:
        like = f"%{q}%"
        rows = conn.execute(
            """SELECT * FROM residents
               WHERE first_name LIKE ? OR last_name LIKE ? OR purok LIKE ? OR occupation LIKE ?
               ORDER BY last_name LIMIT 300""", (like, like, like, like)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM residents ORDER BY last_name LIMIT 300").fetchall()
    conn.close()
    return render_template("residents.html", rows=rows, q=q, brgy=BRGY, **ctx())


@app.route("/residents/<int:rid>")
def resident_detail(rid):
    if not login_required():
        return redirect(url_for("login"))
    conn = get_db()
    r = conn.execute("SELECT * FROM residents WHERE id=?", (rid,)).fetchone()
    hh = conn.execute("SELECT * FROM households WHERE id=?", (r["household_id"],)).fetchone() if r else None
    conn.close()
    if not r:
        abort(404)
    return render_template("resident_detail.html", r=r, hh=hh, brgy=BRGY, **ctx())


def _table_view(template_title, table, columns):
    if not login_required():
        return redirect(url_for("login"))
    conn = get_db()
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY id LIMIT 500").fetchall()
    conn.close()
    return render_template("table.html", title=template_title, rows=rows,
                           columns=columns, brgy=BRGY, **ctx())


@app.route("/households")
def households():
    return _table_view("Households", "households",
                       [("household_no", "HH No."), ("head", "Household Head"),
                        ("purok", "Purok"), ("address", "Address"),
                        ("members", "Members"), ("income_bracket", "Income")])

@app.route("/certificates")
def certificates():
    return _table_view("Certificates Issued", "certificates",
                       [("resident", "Resident"), ("type", "Type"), ("purpose", "Purpose"),
                        ("date_issued", "Date"), ("or_no", "OR No."), ("amount", "Amount"),
                        ("issued_by", "Issued By")])

@app.route("/businesses")
def businesses():
    return _table_view("Business Permits", "businesses",
                       [("name", "Business"), ("owner", "Owner"), ("type", "Type"),
                        ("purok", "Purok"), ("permit_no", "Permit No."), ("status", "Status")])

@app.route("/blotter")
def blotter():
    return _table_view("Blotter Records", "blotter",
                       [("date", "Date"), ("complainant", "Complainant"),
                        ("respondent", "Respondent"), ("nature", "Nature"),
                        ("status", "Status"), ("remarks", "Remarks")])

@app.route("/officials")
def officials():
    return _table_view("Barangay Officials", "officials",
                       [("name", "Name"), ("position", "Position"), ("term", "Term")])


# ---------------------------------------------------------------------------
# [VULN-3] UNRESTRICTED FILE UPLOAD -> WEB SHELL (RCE)
# The "Data Import / Report" tool accepts ANY file with no checks, saves it,
# and /run EXECUTES uploaded Python. Upload a web shell, read the server secret.
#   FIX: never execute uploads; whitelist types; store outside any code path.
# ---------------------------------------------------------------------------
@app.route("/reports", methods=["GET", "POST"])
def reports():
    if not login_required():
        return redirect(url_for("login"))
    message = None
    if request.method == "POST":
        f = request.files.get("report")
        if f and f.filename:
            f.save(os.path.join(UPLOAD_DIR, f.filename))  # no sanitization
            message = f"Imported '{f.filename}'. Use Process to generate the report."
    uploaded = sorted(os.listdir(UPLOAD_DIR))
    return render_template("reports.html", message=message, uploaded=uploaded, brgy=BRGY, **ctx())


@app.route("/run/<path:name>")
def run_report(name):
    if not login_required():
        return redirect(url_for("login"))
    target = os.path.join(UPLOAD_DIR, name)
    if not os.path.exists(target):
        abort(404)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            with open(target) as fh:
                exec(compile(fh.read(), name, "exec"), {"__name__": "__main__"})
        output = buf.getvalue() or "(no output)"
    except Exception as exc:  # noqa: BLE001
        output = f"{type(exc).__name__}: {exc}"
    return Response(output, mimetype="text/plain")


# ---------------------------------------------------------------------------
# [VULN-4] EXPOSED CONFIG VIA PATH TRAVERSAL
# /download joins user input onto a base path with no containment, so
# ?file=../config.ini leaks the system credentials file.
#   FIX: realpath + containment check; allow-list; secrets out of web root.
# ---------------------------------------------------------------------------
@app.route("/system")
def system_page():
    if not login_required():
        return redirect(url_for("login"))
    return render_template("system.html", brgy=BRGY, **ctx())

@app.route("/download")
def download():
    requested = request.args.get("file", "")
    public_dir = os.path.join(BASE_DIR, "public")
    os.makedirs(public_dir, exist_ok=True)
    full = os.path.join(public_dir, requested)   # no normalization/containment
    if not os.path.isfile(full):
        return Response("File not found. Available: forms/clearance-template.txt",
                        status=404, mimetype="text/plain")
    return send_file(full, as_attachment=True)


@app.route("/health")
def health():
    return {"status": "ok", "system": "BIMS Malinaw", "round": load_round()}


# ---------------------------------------------------------------------------
#  Template context + bootstrap
# ---------------------------------------------------------------------------
def ctx():
    return {"cur_user": session.get("name") or session.get("user"),
            "cur_role": session.get("role")}

def bootstrap():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ensure_seeded()
    ensure_config()
    ensure_shell_flag()
    public_dir = os.path.join(BASE_DIR, "public", "forms")
    os.makedirs(public_dir, exist_ok=True)
    tmpl = os.path.join(public_dir, "clearance-template.txt")
    if not os.path.exists(tmpl):
        with open(tmpl, "w") as fh:
            fh.write("BARANGAY MALINAW -- Clearance template. Public form.\n")

bootstrap()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
