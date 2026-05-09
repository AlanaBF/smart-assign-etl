# make_fake_flowcase_reports.py
import csv, os, random, uuid
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker
import re, unicodedata
from dataclasses import dataclass

random.seed(42)
fake = Faker()
Faker.seed(42)

NUM_USERS = 500
MAX_CVS_PER_USER = 1
MAX_ITEMS_PER_SECTION = 6
LANG_CODES = ["int"]

# ---------------------------
# little helpers
# ---------------------------
def _ascii_slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)

def _email_from_name(first: str, last: str, used: set, domains=("example.org","example.com","mail.test")) -> str:
    base = f"{first}.{last}".lower()
    base = re.sub(r"[^a-z0-9.]", "", base)
    candidate = f"{base}@{random.choice(domains)}"
    i = 2
    while candidate in used:
        candidate = f"{base}{i}@{random.choice(domains)}"
        i += 1
    used.add(candidate)
    return candidate

@dataclass
class Person:
    user_id: str
    full_name: str
    email: str
    upn: str
    nationality_ml: str  # e.g. "int:British|no:Britisk"

def get_quarter_folder_name():
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    return f"Q{quarter}{now.year}"

def ts_in_years_back(max_years=3):
    days = random.randint(0, 365 * max_years)
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

def rand_bool():
    return random.choice([True, False])

def maybe(value, p=0.1):
    return value if random.random() > p else ""

def multilang_text(base):
    t = {"int": base}
    lang_choices = LANG_CODES[1:]
    max_k = min(len(lang_choices), 2)
    for lc in random.sample(lang_choices, k=random.randint(0, max_k)):
        t[lc] = f"{base} ({lc})"
    return "|".join([f"{k}:{v}" for k, v in t.items()])

def month_year_pair(start_year=2012, end_year=datetime.now().year):
    y1 = random.randint(start_year, end_year - 1)
    y2 = random.randint(y1, min(y1 + 5, end_year))
    m1 = random.randint(1, 12)
    m2 = random.randint(1, 12)
    return m1, y1, m2, y2

def make_ids():
    return str(uuid.uuid4())[:8]

def get_lang_value(pipe_str, code="int"):
    if not pipe_str:
        return ""
    parts = [p.split(":", 1) for p in pipe_str.split("|") if ":" in p]
    mapping = {k: v for k, v in parts}
    return mapping.get(code, next(iter(mapping.values()), ""))

def _weighted_choice(weight_map: dict[str, float]) -> str:
    keys, weights = zip(*weight_map.items())
    return random.choices(keys, weights=weights, k=1)[0]

# ---------- CPD / SFIA mapping ----------
ROLE_TO_SFIA = {
    "Associate": 2,   # CPD1E
    "Consultant": 3,  # CPD2E
    "Senior": 4,      # CPD3E
    "Principal": 5,   # CPD3L
    "Lead": 6,        # CPD4E
    "Head": 6,        # CPD4E
    "Director": 6
}

def sfia_to_cpd(sfia: int) -> tuple[int, str, str]:
    """
    Returns (cpd_level, cpd_band, cpd_label)
    Your rules:
      SFIA 3 = CPD2L
      SFIA 4 = CPD3E
      SFIA 5 = CPD3M - CPD3L (pick one; we pick L in strict v1)
      SFIA 6 = CPD4E
    Plus: Associate (SFIA 2) = CPD1E
    """
    if sfia <= 2:
        return (1, "E", "CPD1E")
    if sfia == 3:
        return (2, "L", "CPD2L")
    if sfia == 4:
        return (3, "E", "CPD3E")
    if sfia == 5:
        return (3, "L", "CPD3L")
    if sfia >= 6:
        return (4, "E", "CPD4E")
    return (3, "E", "CPD3E")

def cv_id_for_user(user_id: str) -> str:
    return f"cv_{user_id}"

# ---------- Unique leadership roster (one person each) ----------
LEADERSHIP_ROLES = [
    "Director of DDC Engineering",
    "Head of Data Engineering",
    "Head of AWS Engineering",
    "Head of Azure Engineering",
    "Head of Quality Engineering",
    "Head of Microsoft Apps Engineering",
    "Head of Software Engineering EU",
    "Head of Software Engineering IDC",
    "Director of Design",
    "Head of Business Analysis",
    "Head of Product and Service Design",
    "Head of UCD and Insights",
    "Head of Strategy and Advisory",
]

ENGINEERING_HEAD_BASES = {"AWS", "Azure", "Quality", "MS Apps", "Microsoft Apps", "Data"}

def canonicalise_leadership(title: str) -> str:
    """
    Normalize 'Head of X' -> 'Head of X Engineering' for DDC engineering heads.
    Keeps non-engineering Heads/Directors (like Design or BA) unchanged.
    """
    if title.startswith("Head of "):
        base = title[len("Head of "):].strip()
        # Normalize MS Apps naming
        if base == "MS Apps":
            base = "Microsoft Apps"
        needs_engineering = base in ENGINEERING_HEAD_BASES
        if needs_engineering and not base.endswith("Engineering"):
            return f"Head of {base} Engineering"
    return title


# ---------------------------
# Offices / regions / taxonomy
# ---------------------------
OFFICES = [
    # UK & IE
    {"flowcase_office_id":"OFF-UK-LON-001","name":"London","city":"London","region":"UK & IE","country_iso":"gb"},
    {"flowcase_office_id":"OFF-UK-EDI-001","name":"Edinburgh","city":"Edinburgh","region":"UK & IE","country_iso":"gb"},
    {"flowcase_office_id":"OFF-UK-NCL-001","name":"Newcastle","city":"Newcastle","region":"UK & IE","country_iso":"gb"},
    {"flowcase_office_id":"OFF-UK-BHM-001","name":"Birmingham","city":"Birmingham","region":"UK & IE","country_iso":"gb"},
    {"flowcase_office_id":"OFF-IE-DUB-001","name":"Dublin","city":"Dublin","region":"UK & IE","country_iso":"ie"},
    {"flowcase_office_id":"OFF-IE-CRK-001","name":"Cork","city":"Cork","region":"UK & IE","country_iso":"ie"},
    # US
    {"flowcase_office_id":"OFF-US-NYC-001","name":"New York","city":"New York","region":"US","country_iso":"us"},
    # ANZ
    {"flowcase_office_id":"OFF-AU-SYD-001","name":"Sydney","city":"Sydney","region":"ANZ","country_iso":"au"},
    # India
    {"flowcase_office_id":"OFF-IN-BLR-001","name":"Bangalore","city":"Bangalore","region":"India","country_iso":"in"},
    {"flowcase_office_id":"OFF-IN-PNQ-001","name":"Pune","city":"Pune","region":"India","country_iso":"in"},
    # Europe
    {"flowcase_office_id":"OFF-ES-AGP-001","name":"Malaga","city":"Malaga","region":"Europe","country_iso":"es"},
    {"flowcase_office_id":"OFF-SI-LJU-001","name":"Slovenia","city":"Ljubljana","region":"Europe","country_iso":"si"},
]

ISO_TO_COUNTRY = {
    "gb": "United Kingdom",
    "ie": "Ireland",
    "us": "USA",
    "au": "Australia",
    "in": "India",
    "es": "Spain",
    "si": "Slovenia",
}

# Region -> practice weights (shape your org)
REGION_PRACTICES = {
    "UK & IE": {"Architecture": 0.15, "Data Engineering": 0.35, "Software Engineering": 0.20, "Cloud Engineering": 0.15, "Delivery Management": 0.05, "AI/ML": 0.10},
    "US":      {"Architecture": 0.10, "Data Engineering": 0.30, "Software Engineering": 0.25, "Cloud Engineering": 0.20, "Delivery Management": 0.05, "AI/ML": 0.10},
    "Europe":  {"Architecture": 0.12, "Data Engineering": 0.30, "Software Engineering": 0.25, "Cloud Engineering": 0.18, "Delivery Management": 0.05, "AI/ML": 0.10},
    "ANZ":     {"Architecture": 0.10, "Data Engineering": 0.33, "Software Engineering": 0.22, "Cloud Engineering": 0.20, "Delivery Management": 0.05, "AI/ML": 0.10},
    "India":   {"Architecture": 0.05, "Data Engineering": 0.35, "Software Engineering": 0.30, "Cloud Engineering": 0.20, "Delivery Management": 0.03, "AI/ML": 0.07},
}

# Practice -> job family -> ladder
ROLE_TAXONOMY = {
    "Architecture": {
        "Solution Architect":   ["Associate","Consultant","Senior","Principal","Lead"],
        "Data Architect":       ["Consultant","Senior","Principal","Lead"],
        "Cloud Architect":      ["Consultant","Senior","Principal","Lead"],
        "Enterprise Architect": ["Senior","Principal","Lead"],
        "Head of Architecture": ["Head"],
    },
    "Data Engineering": {
        "Python Developer":     ["Associate","Consultant","Senior","Principal"],
        "Data Engineer":        ["Associate","Consultant","Senior","Principal","Lead"],
        "Data Platform Engineer":["Consultant","Senior","Principal","Lead"],
        "Databricks Engineer":  ["Consultant","Senior","Principal"],
        "MLOps Engineer":       ["Consultant","Senior","Principal"],
        "Analytics Engineer":   ["Consultant","Senior","Principal"],
    },
    "Software Engineering": {
        "C# Developer":         ["Associate","Consultant","Senior","Principal"],
        ".NET Engineer":        ["Associate","Consultant","Senior","Principal"],
        "Backend Engineer":     ["Associate","Consultant","Senior","Principal"],
        "Frontend Engineer":    ["Associate","Consultant","Senior","Principal"],
        "Full-stack Engineer":  ["Consultant","Senior","Principal"],
    },
    "Cloud Engineering": {
        "AWS Engineer":         ["Associate","Consultant","Senior","Principal"],
        "Azure Engineer":       ["Associate","Consultant","Senior","Principal"],
        "DevOps Engineer":      ["Associate","Consultant","Senior","Principal"],
        "Kubernetes Engineer":  ["Consultant","Senior","Principal"],
        "Oracle Engineer":      ["Consultant","Senior","Principal"],
    },
    "AI/ML": {
        "AI Engineer":          ["Associate","Consultant","Senior","Principal"],
        "Data Scientist":       ["Associate","Consultant","Senior","Principal"],
        "ML Engineer":          ["Associate","Consultant","Senior","Principal"],
    },
    "Delivery Management": {
        "Delivery Manager":     ["Consultant","Senior","Principal","Lead"],
        "Project Manager":      ["Consultant","Senior","Principal"],
        "Scrum Master":         ["Consultant","Senior"],
    },
}

def choose_practice_for_office(office: dict) -> str:
    return _weighted_choice(REGION_PRACTICES.get(office["region"], {"Data Engineering": 1.0}))

def choose_role_and_level(practice: str) -> tuple[str, str]:
    """
    Pick a family/level for normal users.
    - Exclude 'Head-only' families (e.g., 'Head of Architecture': ['Head'])
    - Exclude the 'Head' level from randomly chosen ladders
    """
    families = ROLE_TAXONOMY.get(practice, {})

    # 1) Exclude families that only contain 'Head'
    non_head_only_fams = [fam for fam, lvls in families.items() if not (len(lvls) == 1 and lvls[0] == "Head")]
    if not non_head_only_fams:
        # Fallback to any family if somehow all were excluded
        non_head_only_fams = list(families.keys())

    family = random.choice(non_head_only_fams)

    # 2) Exclude the 'Head' level from random selection
    lvl_candidates = [lv for lv in families[family] if lv != "Head"]
    level = random.choice(lvl_candidates) if lvl_candidates else random.choice(families[family])

    return family, level


def ladder_from_title(int_title: str) -> list[str]:
    """
    Build a simple career ladder ending at the given title.
    Understands:
      - "Head of <Family>"
      - "Director of <Family>"
      - "<Level> <Family>" where Level in core levels
    """
    core_levels = ["Associate", "Consultant", "Senior", "Principal", "Lead"]
    leadership_levels = ["Head", "Director"]

    title = int_title.strip()

    if title.startswith("Head of "):
        family = title[len("Head of "):].strip()
        return [f"Senior {family}", f"Principal {family}", f"Lead {family}", f"Head of {family}"]

    if title.startswith("Director of "):
        family = title[len("Director of "):].strip()
        return [f"Senior {family}", f"Principal {family}", f"Lead {family}", f"Head of {family}", f"Director of {family}"]

    parts = title.split()
    level = next((p for p in parts if p in core_levels + leadership_levels), None)
    if level is None:
        family = title
        return [f"Consultant {family}", f"Senior {family}", f"Principal {family}"]

    # Compute family by removing first occurrence of the level token
    family = title.replace(level, "", 1).strip()
    if level in leadership_levels:
        family = family.replace("of", "", 1).strip()

    if level == "Head":
        return [f"Senior {family}", f"Principal {family}", f"Lead {family}", f"Head of {family}"]

    if level == "Director":
        return [f"Senior {family}", f"Principal {family}", f"Lead {family}", f"Head of {family}", f"Director of {family}"]

    j = core_levels.index(level)
    window = core_levels[max(0, j-2):j+1]
    return [f"{lv} {family}" for lv in window]


# ---------------------------
# People + CV registry (canonical)
# ---------------------------
users = []
user_cvs = []
_people = []
_used_emails = set()

for _ in range(NUM_USERS):
    first = _ascii_slug(fake.first_name())
    last  = _ascii_slug(fake.last_name())
    full  = f"{first} {last}"
    email = _email_from_name(first, last, _used_emails)
    upn   = f"{first}{last}".lower()
    cv_partner_user_id = make_ids()
    nationality_ml = multilang_text(random.choice(["Norwegian","British","Swedish","Danish","Polish"]))
    _people.append(Person(
        user_id=cv_partner_user_id,
        full_name=full,
        email=email,
        upn=upn,
        nationality_ml=nationality_ml
    ))

# Assign each leadership title to a unique person
assert NUM_USERS >= len(LEADERSHIP_ROLES), "Not enough users for unique leadership roles"

leadership_people = random.sample(_people, k=len(LEADERSHIP_ROLES))
LEADER_BY_USER = {
    p.user_id: canonicalise_leadership(title)
    for title, p in zip(LEADERSHIP_ROLES, leadership_people)
}

for person in _people:
    office = random.choice(OFFICES)
    practice = choose_practice_for_office(office)
    role_family, role_level = choose_role_and_level(practice)

    # See if this person is a unique leader
    forced_title = LEADER_BY_USER.get(person.user_id)

    # Department column: show the functional home
    if forced_title:
        # e.g., "Head of Azure" or "Director of DDC Engineering"
        department_label = forced_title
    else:
        department_label = practice

    user_row = {
        "Name": person.full_name,
        "Name (multilang)": f"int:{person.full_name}",
        "Email": person.email,
        "UPN": person.upn,
        "External User ID": f"ext_{person.user_id}", 
        "CV Partner User ID": person.user_id,
        "Phone Number": fake.phone_number(),
        "Landline": fake.phone_number(),
        "Birth Year": random.randint(1968, 2002),
        "Department": department_label,
        "Country": ISO_TO_COUNTRY.get(office["country_iso"], "Unknown"),
        "Nationality": person.nationality_ml,
        "User created at": ts_in_years_back(8),
        "Access roles": random.choice(["Administrator","Country Manager","User"]),
        "Office ID": office["flowcase_office_id"],
        "Office Name": office["name"],
        "Office City": office["city"],
        "Office Country ISO": office["country_iso"],
    }
    users.append(user_row)

    # Create exactly one CV per person
    for _ in range(1):
        cv_partner_cv_id = cv_id_for_user(person.user_id)

        if forced_title:
            if forced_title.startswith("Head of "):
                fam = forced_title[len("Head of "):].strip()
                lvl = "Head"
            elif forced_title.startswith("Director of "):
                fam = forced_title[len("Director of "):].strip()
                lvl = "Director"
            else:
                fam = forced_title
                lvl = "Head"  
            title_text = forced_title
        else:
            fam, lvl = role_family, role_level
            title_text = fam if lvl == "Head" else f"{lvl} {fam}"

        # map title level -> SFIA -> CPD
        sfia = ROLE_TO_SFIA.get(lvl, 4)
        cpd_level, cpd_band, cpd_label = sfia_to_cpd(sfia)

        user_cvs.append({
            "CV Partner User ID": person.user_id,
            "CV Partner CV ID": cv_partner_cv_id,
            "Title (#{lang})": multilang_text(title_text),

            "SFIA Level": sfia,
            "CPD Level": cpd_level,
            "CPD Band": cpd_band,
            "CPD Label": cpd_label,

            "Years of education": random.randint(10, 20),
            "Years since first work experience": random.randint(1, 25),
            "Has profile image": rand_bool(),
            "Owns a reference project": rand_bool(),
            "Read and understood privacy notice": rand_bool(),
            "CV Last updated by owner": ts_in_years_back(1),
            "CV Last updated": ts_in_years_back(1),
            "Summary Of Qualifications": maybe(f"{title_text} in {practice.lower()} delivering data platforms & analytics.", p=0.3),
        })

# index for joins during generation
user_by_cv = { cv["CV Partner CV ID"]: next(u for u in users if u["CV Partner User ID"]==cv["CV Partner User ID"])
               for cv in user_cvs }
cvs_by_user = {}
for cv in user_cvs:
    cvs_by_user.setdefault(cv["CV Partner User ID"], []).append(cv["CV Partner CV ID"])

# ---------------------------
# column definitions per report
# ---------------------------
base_user_cols = [
    "Name","Name (multilang)","Title (#{lang})","Email","UPN","External User ID",
    "CV Partner User ID","CV Partner CV ID","Phone Number","Landline","Birth Year",
    "Department","Country"
]

report_fields = {
    "user_report": base_user_cols + [
        "User created at","CV Last updated by owner","CV Last updated",
        "Years of education","Years since first work experience","Access roles",
        "Has profile image","Owns a reference project","Read and understood privacy notice",
        "SFIA Level","CPD Level","CPD Band","CPD Label"
    ],
    "usage_report": base_user_cols + [
        "Nationality (#{lang})",
        "Owner last removed or added a section","Owner last updated CV","Last updated CV",
        "Summary Of Qualifications",
        "Owner last updated Qualifications",
        "Project Experiences","Unique roles","Owner last updated Project Experiences",
        "Highlighted roles","Owner last updated Highlighted roles",
        "Skill categories","Owner last updated Skill categories",
        "Educations","Years of education","Owner last updated Educations",
        "Work experiences","Years since first work experience","Owner last updated Work experiences",
        "Certifications","Owner last updated Certifications",
        "Courses","Owner last updated Courses",
        "Presentations","Owner last updated Presentations",
        "Recommendations","Owner last updated Recommendations",
        "Positions","Owner last updated Positions",
        "Mentoring","Owner last updated Mentoring",
        "Publications","Owner last updated Publications",
        "Honors and awards","Owner last updated Honors and awards",
        "Languages","Owner last updated Languages",
        "Owner last updated Unique roles",
    ],
    "project_experiences": base_user_cols + [
        "Nationality","CV Partner section ID","External unique ID",
        "Updated","Updated by owner",
        "Month from","Year from","Month to","Year to",
        "Customer (#{lang})","Customer (int)","Customer Anonymized (#{lang})","Customer Anonymized (int)",
        "Description (#{lang})","Description (int)","Long description (#{lang})","Long description (int)",
        "Industry (#{lang})","Industry (int)","Project type (#{lang})","Project type (int)",
        "Percent allocated",
        "Project extent (individual hours)","Project extent (hours)","Project extent total (hours)",
        "Project extent","Project extent (currency)","Project extent total","Project extent total (currency)",
        "Project area","Project area (unit)","Highlighted"
    ],
    "certifications": base_user_cols + [
        "Nationality","CV Partner section ID","External unique ID","Updated","Updated by owner",
        "Month","Year","Month expire","Year expire"
    ],
    "courses": base_user_cols + [
        "Nationality","CV Partner section ID","External unique ID","Updated","Updated by owner",
        "Month","Year","Name","Organiser","Long description","Highlighted",
        "Is official masterdata (in #{lang})","Attachments"
    ],
    "languages": base_user_cols + [
        "Nationality","CV Partner section ID","External unique ID","Updated","Updated by owner",
        "Highlighted","Is official masterdata (in #{lang})","Language","Level"
    ],
    "technologies": base_user_cols + [
        "Nationality","CV Partner skill ID","CV Partner skill category ID",
        "Skill name","Year experience","Proficiency (0-5)","Is official masterdata (in #{lang})"
    ],
    "key_qualifications": base_user_cols + [
        "Nationality","CV Partner section ID","External unique ID","Updated","Updated by owner",
        "Label","Summary of Qualifications","Short description"
    ],
    "educations": base_user_cols + [
        "Nationality","CV Partner section ID","External unique ID","Updated","Updated by owner",
        "Month from","Year from","Month to","Year to","Highlighted","Attachments","Place of study","Degree","Description"
    ],
    "work_experiences": base_user_cols + [
        "Nationality","CV Partner section ID","External unique ID","Updated","Updated by owner",
        "Month from","Year from","Month to","Year to","Highlighted","Employer","Description","Long Description"
    ],
    "positions": base_user_cols + [
        "Nationality","CV Partner section ID","External unique ID","Updated","Updated by owner",
        "Year from","Year to","Highlighted","Name","Description"
    ],
    "blogs": base_user_cols + [
        "Nationality","CV Partner section ID","External unique ID","Updated","Updated by owner",
        "Name","Description","Highlighted"
    ],
    "cv_roles": base_user_cols + [
        "Nationality","Updated","Updated by owner","Name","Description","Highlighted"
    ],
    "sc_clearance": [
        "Email","UPN","External User ID","CV Partner User ID",
        "Clearance","Valid From","Valid To","Verified By","Notes"
    ],
    "availability_report": [
        "Email","UPN","External User ID","CV Partner User ID",
        "Date","Percent Available","Source"
    ],
}

# ---------------------------
# generators for each report row
# ---------------------------
def base_from_cv(cv_row):
    u = user_by_cv[cv_row["CV Partner CV ID"]]
    base = {
        "Name": u["Name"],
        "Name (multilang)": u["Name (multilang)"],
        "Title (#{lang})": cv_row["Title (#{lang})"],
        "Email": u["Email"],
        "UPN": u["UPN"],
        "External User ID": u["External User ID"],
        "CV Partner User ID": u["CV Partner User ID"],
        "CV Partner CV ID": cv_row["CV Partner CV ID"],
        "Phone Number": u["Phone Number"],
        "Landline": u["Landline"],
        "Birth Year": u["Birth Year"],
        "Department": u["Department"],
        "Country": u["Country"],
    }
    return base, u

def gen_user_report_rows():
    rows = []
    for cv in user_cvs:
        base, u = base_from_cv(cv)
        rows.append({
            **base,
            "User created at": u["User created at"],
            "CV Last updated by owner": cv["CV Last updated by owner"],
            "CV Last updated": cv["CV Last updated"],
            "Years of education": cv["Years of education"],
            "Years since first work experience": cv["Years since first work experience"],
            "Access roles": u["Access roles"],
            "Has profile image": cv["Has profile image"],
            "Owns a reference project": cv["Owns a reference project"],
            "Read and understood privacy notice": cv["Read and understood privacy notice"],
            "SFIA Level": cv["SFIA Level"],
            "CPD Level": cv["CPD Level"],
            "CPD Band": cv["CPD Band"],
            "CPD Label": cv["CPD Label"],
        })
    return rows

def gen_usage_report_rows():
    rows = []
    for cv in user_cvs:
        base, u = base_from_cv(cv)
        counts = {
            "Project Experiences": random.randint(0, MAX_ITEMS_PER_SECTION),
            "Unique roles": random.randint(0, 4),
            "Highlighted roles": random.randint(0, 3),
            "Skill categories": random.randint(1, 5),
            "Educations": random.randint(0, 3),
            "Work experiences": random.randint(0, 6),
            "Certifications": random.randint(0, 4),
            "Courses": random.randint(0, 6),
            "Presentations": random.randint(0, 3),
            "Recommendations": random.randint(0, 2),
            "Positions": random.randint(0, 4),
            "Mentoring": random.randint(0, 2),
            "Publications": random.randint(0, 5),
            "Honors and awards": random.randint(0, 2),
            "Languages": random.randint(1, 4),
        }
        row = {
            **base,
            "Nationality (#{lang})": u["Nationality"],
            "Owner last removed or added a section": ts_in_years_back(1),
            "Owner last updated CV": ts_in_years_back(1),
            "Last updated CV": ts_in_years_back(1),
            "Summary Of Qualifications": cv.get("Summary Of Qualifications",""),
            "Owner last updated Qualifications": ts_in_years_back(2),
            "Years of education": cv["Years of education"],
            "Years since first work experience": cv["Years since first work experience"],
        }
        for label, cnt in counts.items():
            row[label] = cnt
            row[f"Owner last updated {label}"] = ts_in_years_back(2)
        rows.append(row)
    return rows

def gen_project_rows():
    rows = []
    for cv in user_cvs:
        n = random.randint(0, MAX_ITEMS_PER_SECTION)
        for _ in range(n):
            base, u = base_from_cv(cv)
            m1, y1, m2, y2 = month_year_pair()
            rows.append({
                **base,
                "Nationality": get_lang_value(u["Nationality"], "int"),
                "CV Partner section ID": make_ids(),
                "External unique ID": make_ids(),
                "Updated": ts_in_years_back(2),
                "Updated by owner": ts_in_years_back(2),
                "Month from": m1, "Year from": y1, "Month to": m2, "Year to": y2,
                "Customer (#{lang})": multilang_text(random.choice(["Acme","Contoso","Globex"])),
                "Customer (int)": random.choice(["Acme","Contoso","Globex"]),
                "Customer Anonymized (#{lang})": multilang_text("Confidential Client"),
                "Customer Anonymized (int)": "Confidential Client",
                "Description (#{lang})": multilang_text("Delivered analytics platform."),
                "Description (int)": "Delivered analytics platform.",
                "Long description (#{lang})": multilang_text("Data lake, pipelines, BI."),
                "Long description (int)": "Data lake, pipelines, BI.",
                "Industry (#{lang})": multilang_text(random.choice(["Finance","Energy","Health"])),
                "Industry (int)": random.choice(["Finance","Energy","Health"]),
                "Project type (#{lang})": multilang_text(random.choice(["Implementation","Advisory"])),
                "Project type (int)": random.choice(["Implementation","Advisory"]),
                "Percent allocated": random.randint(10,100),
                "Project extent (individual hours)": random.randint(10,200),
                "Project extent (hours)": random.randint(100, 1000),
                "Project extent total (hours)": random.randint(100, 2000),
                "Project extent": random.choice(["Budget","Hours"]),
                "Project extent (currency)": random.choice(["NOK","SEK","GBP","EUR"]),
                "Project extent total": random.randint(10000, 250000),
                "Project extent total (currency)": random.choice(["NOK","SEK","GBP","EUR"]),
                "Project area": random.randint(1, 10)*100,
                "Project area (unit)": "sqm",
                "Highlighted": rand_bool(),
            })
    return rows

def gen_cert_rows():
    rows = []
    for cv in user_cvs:
        for _ in range(random.randint(0, MAX_ITEMS_PER_SECTION//2+1)):
            base, u = base_from_cv(cv)
            month = random.randint(1,12)
            year = random.randint(2016, 2025)
            rows.append({
                **base,
                "Nationality": get_lang_value(u["Nationality"], "int"),
                "CV Partner section ID": make_ids(),
                "External unique ID": make_ids(),
                "Updated": ts_in_years_back(2),
                "Updated by owner": ts_in_years_back(2),
                "Month": month, "Year": year,
                "Month expire": random.randint(1,12), "Year expire": year + random.randint(0,3)
            })
    return rows

def gen_courses_rows():
    rows = []
    for cv in user_cvs:
        for _ in range(random.randint(0, MAX_ITEMS_PER_SECTION)):
            base, u = base_from_cv(cv)
            month = random.randint(1,12); year = random.randint(2018,2025)
            rows.append({
                **base,
                "Nationality": get_lang_value(u["Nationality"], "int"),
                "CV Partner section ID": make_ids(),
                "External unique ID": make_ids(),
                "Updated": ts_in_years_back(2),
                "Updated by owner": ts_in_years_back(2),
                "Month": month, "Year": year,
                "Name": random.choice(["SQL Advanced","Azure Fundamentals","Power BI","AWS Solutions Architect","Databricks Lakehouse"]),
                "Organiser": random.choice(["Microsoft","Udemy","Coursera","Internal","AWS","Databricks"]),
                "Long description": maybe("Intensive 3-day workshop."),
                "Highlighted": rand_bool(),
                "Is official masterdata (in #{lang})": multilang_text(random.choice(["Yes","No"])),
                "Attachments": maybe("certificate.pdf"),
            })
    return rows

def gen_languages_rows():
    rows = []
    for cv in user_cvs:
        for lang in random.sample(["English","Norwegian","Swedish","Danish","Polish"], k=random.randint(1,3)):
            base, u = base_from_cv(cv)
            rows.append({
                **base,
                "Nationality": get_lang_value(u["Nationality"], "int"),
                "CV Partner section ID": make_ids(),
                "External unique ID": make_ids(),
                "Updated": ts_in_years_back(2),
                "Updated by owner": ts_in_years_back(2),
                "Highlighted": rand_bool(),
                "Is official masterdata (in #{lang})": multilang_text(random.choice(["Yes","No"])),
                "Language": lang,
                "Level": random.choice(["Native","Fluent","Professional","Intermediate"]),
            })
    return rows

def gen_tech_rows():
    rows = []
    skills = [
        "Python","C#",".NET","JavaScript","TypeScript",
        "React","Node.js","SQL","Azure","AWS","GCP",
        "Databricks","Spark","Kafka","Airflow","dbt",
        "Terraform","Kubernetes","Docker","Oracle","Snowflake","Power BI"
    ]
    for cv in user_cvs:
        for skill in random.sample(skills, k=random.randint(3,6)):
            base, u = base_from_cv(cv)
            rows.append({
                **base,
                "Nationality": get_lang_value(u["Nationality"], "int"),
                "CV Partner skill ID": make_ids(),
                "CV Partner skill category ID": make_ids(),
                "Skill name": skill,
                "Year experience": random.randint(1,15),
                "Proficiency (0-5)": random.randint(1,5),
                "Is official masterdata (in #{lang})": multilang_text(random.choice(["Yes","No"])),
            })
    return rows

def gen_keyqual_rows():
    rows = []
    for cv in user_cvs:
        for _ in range(random.randint(0,2)):
            base, u = base_from_cv(cv)
            rows.append({
                **base,
                "Nationality": get_lang_value(u["Nationality"], "int"),
                "CV Partner section ID": make_ids(),
                "External unique ID": make_ids(),
                "Updated": ts_in_years_back(2),
                "Updated by owner": ts_in_years_back(2),
                "Label": random.choice(["Profile","Summary","Key Strengths"]),
                "Summary of Qualifications": "Experienced in cloud, data engineering and analytics.",
                "Short description": maybe("Focus on Python, Azure/AWS, Databricks.")
            })
    return rows

def gen_edu_rows():
    rows = []
    degrees = ["BSc Computer Science","MSc Data Science","BEng Software Eng"]
    for cv in user_cvs:
        for _ in range(random.randint(0,3)):
            base, u = base_from_cv(cv)
            m1,y1,m2,y2 = month_year_pair(2008, 2024)
            rows.append({
                **base,
                "Nationality": get_lang_value(u["Nationality"], "int"),
                "CV Partner section ID": make_ids(),
                "External unique ID": make_ids(),
                "Updated": ts_in_years_back(4),
                "Updated by owner": ts_in_years_back(4),
                "Month from": m1, "Year from": y1, "Month to": m2, "Year to": y2,
                "Highlighted": rand_bool(),
                "Attachments": maybe("diploma.pdf"),
                "Place of study": random.choice(["NTNU","KTH","UiO","OU","UCL"]),
                "Degree": random.choice(degrees),
                "Description": maybe("Thesis on scalable data pipelines.")
            })
    return rows

def gen_work_rows():
    rows = []
    employers = ["Acme Bank","Energia","HealthCorp","RetailCo","ConsultCo"]
    for cv in user_cvs:
        for _ in range(random.randint(0, MAX_ITEMS_PER_SECTION)):
            base, u = base_from_cv(cv)
            m1,y1,m2,y2 = month_year_pair(2010, 2025)
            rows.append({
                **base,
                "Nationality": get_lang_value(u["Nationality"], "int"),
                "CV Partner section ID": make_ids(),
                "External unique ID": make_ids(),
                "Updated": ts_in_years_back(3),
                "Updated by owner": ts_in_years_back(3),
                "Month from": m1, "Year from": y1, "Month to": m2, "Year to": y2,
                "Highlighted": rand_bool(),
                "Employer": random.choice(employers),
                "Description": "Worked on data platforms, software delivery and BI.",
                "Long Description": maybe("Led a small team delivering cloud migration.")
            })
    return rows

def gen_positions_rows():
    rows = []
    for cv in user_cvs:
        base, u = base_from_cv(cv)
        title_int = get_lang_value(cv["Title (#{lang})"], "int")
        ladder = ladder_from_title(title_int)
        start = random.randint(2016, 2021)
        for i, t in enumerate(ladder):
            rows.append({
                **base,
                "Nationality": get_lang_value(u["Nationality"], "int"),
                "CV Partner section ID": make_ids(),
                "External unique ID": make_ids(),
                "Updated": ts_in_years_back(2),
                "Updated by owner": ts_in_years_back(2),
                "Year from": start+i, "Year to": start+i+1,
                "Highlighted": rand_bool(),
                "Name": t,
                "Description": maybe("Progression based on delivery impact.")
            })
    return rows

def gen_blogs_rows():
    rows = []
    topics = [
        "Data Mesh in Practice","Intro to dbt","Streaming 101","Kubernetes for Data",
        "Optimising PySpark","Modern .NET APIs","AWS Well-Architected","Azure Fabric Basics",
        "MLOps Playbook","Databricks Lakehouse Patterns"
    ]
    for cv in user_cvs:
        for _ in range(random.randint(0,3)):
            base, u = base_from_cv(cv)
            rows.append({
                **base,
                "Nationality": get_lang_value(u["Nationality"], "int"),
                "CV Partner section ID": make_ids(),
                "External unique ID": make_ids(),
                "Updated": ts_in_years_back(2),
                "Updated by owner": ts_in_years_back(2),
                "Name": random.choice(topics),
                "Description": maybe("Conference talk / blog summary."),
                "Highlighted": rand_bool()
            })
    return rows

def gen_cv_roles_rows():
    rows = []
    for cv in user_cvs:
        for role in random.sample(["Developer","Tech Lead","Architect","Analyst","Manager"], k=random.randint(1,3)):
            base, u = base_from_cv(cv)
            rows.append({
                **base,
                "Nationality": get_lang_value(u["Nationality"], "int"),
                "Updated": ts_in_years_back(2),
                "Updated by owner": ts_in_years_back(2),
                "Name": role,
                "Description": maybe("High-level role on multiple projects."),
                "Highlighted": rand_bool()
            })
    return rows

def gen_sc_clearance_rows():
    # Columns: Email, UPN, External User ID, CV Partner User ID, Clearance, Valid From, Valid To, Verified By, Notes
    rows = []
    CLEARANCES = ["SC", "NPPV2", "None"]
    for u in users:  # reuse the same user rows you already build
        clr = random.choices(CLEARANCES, weights=[0.25, 0.10, 0.65], k=1)[0]
        if clr == "None":
            vf, vt = "", ""
        else:
            vf = ts_in_years_back(3)
            vt = ""  # open-ended
        rows.append({
            "Email": u["Email"],
            "UPN": u["UPN"],
            "External User ID": u["External User ID"],
            "CV Partner User ID": u["CV Partner User ID"],
            "Clearance": clr,
            "Valid From": vf,
            "Valid To": vt,
            "Verified By": random.choice(["HR", "Security", "PMO"]),
            "Notes": maybe("Imported from legacy sheet"),
        })
    return rows

def gen_availability_rows(days_forward=60):
    # Columns: Email, UPN, External User ID, CV Partner User ID, Date, Percent Available, Source
    rows = []
    start = datetime.now().date()
    for u in users:
        # simple realistic pattern: most people 20–80% free; add some fully booked days
        base_free = random.randint(20, 80)
        for d in range(days_forward):
            day = start + timedelta(days=d)
            if day.weekday() >= 5:  # weekends 100% free
                pct = 100
            else:
                pct = max(0, min(100, base_free + random.randint(-20, 20)))
                if random.random() < 0.15:
                    pct = 0  # booked day
            rows.append({
                "Email": u["Email"],
                "UPN": u["UPN"],
                "External User ID": u["External User ID"],
                "CV Partner User ID": u["CV Partner User ID"],
                "Date": day.isoformat(),
                "Percent Available": pct,
                "Source": "Fake generator"
            })
    return rows

# ---------------------------
# write CSVs
# ---------------------------
def write_csv(report_name, rows, out_dir):
    path = Path(out_dir) / f"{report_name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=report_fields[report_name])
        writer.writeheader()
        for r in rows:
            for col in report_fields[report_name]:
                r.setdefault(col, "")
            writer.writerow(r)
    print(f"✔ {path.name}: {len(rows)} rows")

def main():
    folder_name = get_quarter_folder_name()
    output_dir = os.path.join("cv_reports", folder_name)
    os.makedirs(output_dir, exist_ok=True)

    write_csv("user_report", gen_user_report_rows(), output_dir)
    write_csv("usage_report", gen_usage_report_rows(), output_dir)
    write_csv("project_experiences", gen_project_rows(), output_dir)
    write_csv("certifications", gen_cert_rows(), output_dir)
    write_csv("courses", gen_courses_rows(), output_dir)
    write_csv("languages", gen_languages_rows(), output_dir)
    write_csv("technologies", gen_tech_rows(), output_dir)
    write_csv("key_qualifications", gen_keyqual_rows(), output_dir)
    write_csv("educations", gen_edu_rows(), output_dir)
    write_csv("work_experiences", gen_work_rows(), output_dir)
    write_csv("positions", gen_positions_rows(), output_dir)
    write_csv("blogs", gen_blogs_rows(), output_dir)
    write_csv("cv_roles", gen_cv_roles_rows(), output_dir)
    
    write_csv("sc_clearance", gen_sc_clearance_rows(), output_dir)
    write_csv("availability_report", gen_availability_rows(), output_dir)

    print(f"\nAll files written under: {Path(output_dir).resolve()}")

if __name__ == "__main__":
    main()
