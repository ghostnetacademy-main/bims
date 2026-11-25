"""
seed_bims.py -- generates the fictional Barangay Information Management System
dataset for the training target.

ALL DATA IS INVENTED. Names, addresses, numbers and records are fictional and
generated deterministically (fixed random seed) so the "barangay" is the same
every time the range resets -- only the planted CTF flags rotate.

Setting: Barangay Malinaw, Municipality of Bayanihan (both fictional).
"""

import os
import random
import sqlite3
import datetime

SEED = 1337  # deterministic -> same residents every reseed

FIRST_M = ["Juan", "Pedro", "Jose", "Antonio", "Ricardo", "Danilo", "Rogelio", "Eduardo",
           "Manuel", "Rolando", "Ernesto", "Alfredo", "Benigno", "Teodoro", "Marcelo",
           "Noel", "Arnel", "Jerome", "Christian", "Mark", "Reymart", "Jayson", "Dexter"]
FIRST_F = ["Maria", "Rosa", "Josefa", "Corazon", "Luzviminda", "Teresita", "Gloria", "Imelda",
           "Divina", "Nenita", "Marilou", "Evangeline", "Jocelyn", "Analyn", "Girlie",
           "Angelica", "Jenny", "Kristine", "Mary Grace", "Shaina", "Precious", "Honey"]
MID = ["Dela Cruz", "Santos", "Reyes", "Bautista", "Villanueva", "Mendoza", "Aquino",
       "Gonzales", "Flores", "Ramos", "Castillo", "Torres", "Domingo", "Salcedo", "Abad"]
LAST = ["Dela Cruz", "Santos", "Reyes", "Bautista", "Villanueva", "Mendoza", "Aquino",
        "Gonzales", "Flores", "Ramos", "Castillo", "Torres", "Domingo", "Salcedo", "Abad",
        "Cabrera", "Navarro", "Lagumbay", "Pacana", "Montances", "Ebarle", "Calo", "Plaza"]
OCC = ["Farmer", "Tricycle Driver", "Market Vendor", "Teacher", "Barangay Tanod", "Fisherfolk",
       "Sari-sari Store Owner", "Carpenter", "Housekeeper", "Student", "OFW Dependent",
       "Seamstress", "Welder", "Call Center Agent", "Unemployed", "Government Employee"]
CIVIL = ["Single", "Married", "Widowed", "Separated"]
CERT_TYPES = ["Barangay Clearance", "Certificate of Indigency", "Certificate of Residency",
              "Barangay Business Clearance", "Certificate of Good Moral", "First-Time Jobseeker"]
BIZ_TYPES = ["Sari-sari Store", "Carinderia", "Vulcanizing Shop", "Rice Retailer",
             "Water Refilling Station", "Hardware", "Internet Cafe", "Poultry Supply",
             "Beauty Parlor", "Motorcycle Parts"]
BLOTTER_NATURE = ["Noise complaint", "Boundary dispute", "Unsettled debt", "Stray animals",
                  "Minor altercation", "Property damage", "Curfew violation", "Lost item report"]
BLOTTER_STATUS = ["Settled", "For mediation", "Referred to PNP", "Pending", "Dismissed"]


def _phil_id(rng):
    return f"{rng.randint(1000,9999)}-{rng.randint(1000,9999)}-{rng.randint(1000,9999)}"


def _mobile(rng):
    return "09" + "".join(str(rng.randint(0, 9)) for _ in range(9))


def build(db_path, flags):
    """(Re)build the BIMS database at db_path. `flags` is the dict from flags.json."""
    rng = random.Random(SEED)
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT,
            full_name TEXT, role TEXT );
        CREATE TABLE residents (
            id INTEGER PRIMARY KEY, first_name TEXT, middle_name TEXT, last_name TEXT,
            sex TEXT, birthdate TEXT, civil_status TEXT, purok TEXT, occupation TEXT,
            contact_no TEXT, philsys_no TEXT, voter INTEGER, senior INTEGER, pwd INTEGER,
            household_id INTEGER );
        CREATE TABLE households (
            id INTEGER PRIMARY KEY, household_no TEXT, head TEXT, purok TEXT,
            address TEXT, members INTEGER, income_bracket TEXT );
        CREATE TABLE officials (
            id INTEGER PRIMARY KEY, name TEXT, position TEXT, term TEXT );
        CREATE TABLE certificates (
            id INTEGER PRIMARY KEY, resident TEXT, type TEXT, purpose TEXT,
            date_issued TEXT, or_no TEXT, amount REAL, issued_by TEXT );
        CREATE TABLE businesses (
            id INTEGER PRIMARY KEY, name TEXT, owner TEXT, type TEXT, purok TEXT,
            permit_no TEXT, status TEXT );
        CREATE TABLE blotter (
            id INTEGER PRIMARY KEY, date TEXT, complainant TEXT, respondent TEXT,
            nature TEXT, status TEXT, remarks TEXT );
        -- SQL-injection flag target: the admin's private system note.
        CREATE TABLE system_notes ( id INTEGER PRIMARY KEY, note TEXT );
        """
    )

    # --- staff accounts (login vulns live here) -------------------------------
    c.executemany(
        "INSERT INTO users (username,password,full_name,role) VALUES (?,?,?,?)",
        [
            # [VULN-1] default admin password, never rotated
            ("admin", "admin123", "System Administrator", "administrator"),
            ("bsecretary", "Malinaw@2021", "Josefa R. Montances", "secretary"),
            ("btreasurer", "funds2022", "Rogelio P. Calo", "treasurer"),
            ("encoder1", "encode123", "Analyn S. Pacana", "encoder"),
        ],
    )

    # --- officials ------------------------------------------------------------
    officials = [
        ("Hon. Teodoro V. Lagumbay", "Punong Barangay", "2023-2025"),
        ("Hon. Corazon D. Ebarle", "Barangay Kagawad", "2023-2025"),
        ("Hon. Arnel M. Navarro", "Barangay Kagawad", "2023-2025"),
        ("Hon. Marilou A. Plaza", "Barangay Kagawad", "2023-2025"),
        ("Hon. Benigno T. Cabrera", "Barangay Kagawad", "2023-2025"),
        ("Hon. Divina R. Flores", "Barangay Kagawad", "2023-2025"),
        ("Hon. Noel B. Aquino", "Barangay Kagawad", "2023-2025"),
        ("Hon. Jerome C. Torres", "SK Chairperson", "2023-2025"),
        ("Josefa R. Montances", "Barangay Secretary", "appointed"),
        ("Rogelio P. Calo", "Barangay Treasurer", "appointed"),
    ]
    c.executemany("INSERT INTO officials (name,position,term) VALUES (?,?,?)", officials)

    # --- households + residents ----------------------------------------------
    puroks = [f"Purok {i}" for i in range(1, 8)]
    n_households = 55
    hh_ids = []
    for h in range(1, n_households + 1):
        purok = rng.choice(puroks)
        hh_no = f"HH-{h:04d}"
        members = rng.randint(1, 7)
        income = rng.choice(["Below 10k", "10k-20k", "20k-40k", "Above 40k"])
        head = f"{rng.choice(FIRST_M+FIRST_F)} {rng.choice(LAST)}"
        addr = f"{rng.randint(1,299)} {purok}, Barangay Malinaw"
        c.execute("INSERT INTO households (household_no,head,purok,address,members,income_bracket) VALUES (?,?,?,?,?,?)",
                  (hh_no, head, purok, addr, members, income))
        hh_ids.append(h)

    n_res = 160
    this_year = 2026
    for _ in range(n_res):
        sex = rng.choice(["Male", "Female"])
        fn = rng.choice(FIRST_M if sex == "Male" else FIRST_F)
        ln = rng.choice(LAST)
        mn = rng.choice(MID)
        age = rng.randint(1, 88)
        by = this_year - age
        bd = f"{by}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"
        civ = "Single" if age < 18 else rng.choice(CIVIL)
        occ = "Student" if age < 18 else rng.choice(OCC)
        c.execute(
            """INSERT INTO residents
               (first_name,middle_name,last_name,sex,birthdate,civil_status,purok,
                occupation,contact_no,philsys_no,voter,senior,pwd,household_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fn, mn, ln, sex, bd, civ, rng.choice(puroks), occ, _mobile(rng),
             _phil_id(rng), 1 if age >= 18 else 0, 1 if age >= 60 else 0,
             1 if rng.random() < 0.05 else 0, rng.choice(hh_ids)),
        )

    # --- certificates issued --------------------------------------------------
    res_names = [r[0] for r in c.execute(
        "SELECT first_name||' '||last_name FROM residents").fetchall()]
    for i in range(72):
        d = datetime.date(2026, rng.randint(1, 11), rng.randint(1, 28)).isoformat()
        c.execute(
            "INSERT INTO certificates (resident,type,purpose,date_issued,or_no,amount,issued_by) VALUES (?,?,?,?,?,?,?)",
            (rng.choice(res_names), rng.choice(CERT_TYPES),
             rng.choice(["Employment", "Scholarship", "Loan requirement", "Medical assistance",
                         "Business permit", "Travel", "PhilHealth"]),
             d, f"OR-{rng.randint(10000,99999)}", float(rng.choice([0, 30, 50, 100])),
             rng.choice(["admin", "bsecretary", "encoder1"])),
        )

    # --- businesses -----------------------------------------------------------
    for i in range(28):
        c.execute(
            "INSERT INTO businesses (name,owner,type,purok,permit_no,status) VALUES (?,?,?,?,?,?)",
            (rng.choice(["Aling", "Mang", "RJ", "LJ", "Three Sisters", "Golden", "St. Jude",
                         "Buenas", "Lucky", "Primex"]) + " " + rng.choice(BIZ_TYPES).split()[0] + " Store"
             if rng.random() < 0.5 else rng.choice(BIZ_TYPES),
             rng.choice(res_names), rng.choice(BIZ_TYPES), rng.choice(puroks),
             f"BP-2026-{rng.randint(100,999)}", rng.choice(["Active", "Active", "Expired", "For renewal"])),
        )

    # --- blotter (kept mild; fictional) --------------------------------------
    for i in range(18):
        d = datetime.date(2026, rng.randint(1, 11), rng.randint(1, 28)).isoformat()
        c.execute(
            "INSERT INTO blotter (date,complainant,respondent,nature,status,remarks) VALUES (?,?,?,?,?,?)",
            (d, rng.choice(res_names), rng.choice(res_names), rng.choice(BLOTTER_NATURE),
             rng.choice(BLOTTER_STATUS), rng.choice(["Amicably settled", "For follow-up",
             "Both parties advised", "Endorsed to Lupon", "No show"]))
        )

    # --- the SQLi flag, hidden as the admin's private note --------------------
    c.execute("INSERT INTO system_notes (note) VALUES (?)",
              (f"ADMIN PRIVATE -- master backup passphrase on file. {flags['sql_injection']['value']}",))

    conn.commit()
    conn.close()
