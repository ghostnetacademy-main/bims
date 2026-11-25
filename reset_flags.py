#!/usr/bin/env python3
"""
reset_flags.py  --  Reset the Barangay Services Portal CTF between rounds.

What it does:
  1. Rotates every flag value in flags.json (fresh random suffix) so a flag
     captured in an earlier round cannot be reused later.
  2. Optionally sets the round number/name written into flags.json.
  3. Re-seeds the portal database (restores the default admin password and the
     classified SQLi flag).
  4. Rewrites the exposed config.ini (restores creds + exposed_config flag).
  5. Rewrites secret/shell_flag.txt (the file the upload web shell reads).
  6. Clears everything attackers dropped in portal/uploads/.

Run it ON THE PORTAL BOX. If the scoreboard runs on a SEPARATE VM, copy the
updated flags.json over to it afterwards (see README) so validation stays in sync.

Usage:
  python3 reset_flags.py                 # rotate flags, re-seed, keep round
  python3 reset_flags.py --round 2       # also set round 2 (defend)
  python3 reset_flags.py --round 3 --no-rotate   # keep flag values, just re-seed
"""

import os
import json
import glob
import secrets
import argparse

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
FLAGS_PATH  = os.path.join(PROJECT_DIR, "flags.json")
PORTAL_DIR  = os.path.join(PROJECT_DIR, "portal")
UPLOAD_DIR  = os.path.join(PORTAL_DIR, "uploads")
DB_PATH     = os.path.join(PORTAL_DIR, "portal.db")
CONFIG_PATH = os.path.join(PORTAL_DIR, "config.ini")

ROUND_NAMES = {1: "attack", 2: "defend", 3: "finale"}

# Human-readable stems; a random suffix is appended on each rotation.
STEMS = {
    "default_password": "d3fault_adm1n",
    "sql_injection":    "0r_1_3qu4ls_1",
    "file_upload":      "upl04d3d_sh3ll",
    "exposed_config":   "c0nf1g_l34k",
}


def rotate_flags(data, do_rotate):
    for key, meta in data["flags"].items():
        if do_rotate:
            suffix = secrets.token_hex(3)   # 6 hex chars
            meta["value"] = f"FLAG{{{STEMS[key]}_{suffix}}}"
    return data


def main():
    ap = argparse.ArgumentParser(description="Reset the CTF between rounds.")
    ap.add_argument("--round", type=int, choices=[1, 2, 3], help="set round number")
    ap.add_argument("--no-rotate", action="store_true", help="keep current flag values")
    args = ap.parse_args()

    with open(FLAGS_PATH) as fh:
        data = json.load(fh)

    data = rotate_flags(data, do_rotate=not args.no_rotate)
    if args.round:
        data["round"] = args.round
        data["round_name"] = ROUND_NAMES[args.round]

    with open(FLAGS_PATH, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")

    # Remove the portal DB and config so the portal re-creates them from the
    # fresh flags on its next start (or immediately, below).
    for path in (DB_PATH, CONFIG_PATH):
        if os.path.exists(path):
            os.remove(path)

    # Clear attacker uploads.
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    for f in glob.glob(os.path.join(UPLOAD_DIR, "*")):
        os.remove(f)

    # Re-seed immediately by importing the portal's bootstrap with the new flags.
    import importlib.util
    spec = importlib.util.spec_from_file_location("portal_app", os.path.join(PORTAL_DIR, "app.py"))
    portal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(portal)   # bootstrap() runs on import

    print("Reset complete.")
    print(f"  round : {data['round']} ({data.get('round_name')})")
    print(f"  rotate: {'no' if args.no_rotate else 'yes'}")
    for key, meta in data["flags"].items():
        print(f"  {key:18} {meta['points']:>3} pts  {meta['value']}")
    print("\nIf the scoreboard runs on a different VM, copy flags.json to it now.")
    print("Restart the portal (Ctrl-C and re-run) if it was already running.")


if __name__ == "__main__":
    main()
