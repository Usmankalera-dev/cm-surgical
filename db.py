import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store.db")
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img", "products")

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    description TEXT NOT NULL,
    price_min INTEGER NOT NULL,
    price_max INTEGER NOT NULL,
    image TEXT NOT NULL,
    featured INTEGER DEFAULT 0,
    top_sell INTEGER DEFAULT 0,
    stock INTEGER NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    total INTEGER NOT NULL,
    items TEXT NOT NULL,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    discount INTEGER NOT NULL DEFAULT 0,
    coupon_code TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    image TEXT,
    link TEXT DEFAULT '',
    position TEXT NOT NULL DEFAULT 'top_banner',
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    author TEXT NOT NULL,
    rating INTEGER NOT NULL,
    title TEXT,
    body TEXT NOT NULL,
    verified INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);

CREATE TABLE IF NOT EXISTS coupons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL DEFAULT 'percent',
    value INTEGER NOT NULL DEFAULT 0,
    min_order INTEGER NOT NULL DEFAULT 0,
    max_discount INTEGER NOT NULL DEFAULT 0,
    usage_limit INTEGER NOT NULL DEFAULT 0,
    used_count INTEGER NOT NULL DEFAULT 0,
    starts_at TEXT,
    expires_at TEXT,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS login_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    used INTEGER DEFAULT 0
);

-- Admin credentials set from inside the panel. The password is stored only as a
-- salted hash. When no row exists, the app falls back to the ADMIN_PASSWORD
-- environment variable, so a fresh install still works.
CREATE TABLE IF NOT EXISTS admin_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

CATEGORIES = [
    ("Ear, Nose & Throat", "ear-nose-throat"),
    ("Forceps", "forceps"),
    ("Scissors", "scissors"),
    ("Scalpels & Knives", "scalpels-knives"),
    ("Diagnostics", "diagnostics"),
    ("Gynecology & Obstetrics", "gynecology-obstetrics"),
    ("Sterilization Containers", "sterilization-containers"),
    ("Suction Tubes", "suction-tubes"),
    ("Suture", "suture"),
    ("Hollowware", "hollowware"),
    ("Retractors", "retractors"),
]

PRODUCTS = [
    ("FS-101", "Dressing Forceps", "forceps", "Stainless steel dressing forceps with serrated tips for safe and secure tissue handling. Available in multiple sizes.", 330, 615, 1, 0),
    ("CCJ-102", "Cotton & Catgut Jars", "suture", "Heavy-duty glass and stainless jars for storing cotton and catgut. Multiple capacities available.", 1295, 3060, 0, 0),
    ("NS-3813", "RANEY Scalp Clip", "ear-nose-throat", "Premium stainless steel Raney scalp clip for scalp hemostasis during surgical procedures.", 750, 750, 1, 0),
    ("SC-340", "Bio Barrier Sterilization Containers – Half Size", "sterilization-containers", "Autoclavable perforated sterilization containers with filter, half size. Multiple models available.", 98415, 139725, 0, 0),
    ("SS-901", "IRIS Scissors", "scissors", "Fine precision iris scissors with sharp pointed blades, ideal for delicate ophthalmic work.", 990, 1035, 1, 0),
    ("FS-205", "ADSON Dissecting Forceps, TC Tip", "forceps", "Adson dissecting forceps with tungsten-carbide tips for a firm, precise grip.", 1090, 1090, 0, 0),
    ("SS-277", "GOLDMAN-FOX Operating Scissors – TC Edge", "scissors", "Operating scissors with tungsten-carbide edge for clean cutting of heavy tissue.", 5115, 5400, 0, 1),
    ("SS-285", "LITTAUER Stitch Scissors", "scissors", "Littauer stitch scissors with notched blades for quick suture removal.", 1275, 1275, 0, 0),
    ("GY-103", "HEGAR Uterine Dilator", "gynecology-obstetrics", "Set of double-ended Hegar uterine dilators in graduated sizes, German stainless steel.", 1065, 14085, 0, 1),
    ("DG-248", "PINARD Stethoscope Aluminium", "diagnostics", "Classic Pinard fetal stethoscope in lightweight aluminium with an ergonomic shape.", 930, 930, 0, 1),
    ("ENT-104", "HARTMANN Ear Specula", "ear-nose-throat", "Set of Hartmann ear specula in polished stainless steel, multiple tip sizes.", 530, 530, 0, 1),
    ("ENT-175", "THUDICHUM (MARK HOVELL) Nasal Specula", "ear-nose-throat", "Mark Hovell pattern nasal specula for nasal examination and procedures.", 480, 480, 0, 1),
    ("DG-242", "Mini Ophthalmoscope Set", "diagnostics", "Compact mini ophthalmoscope set packed in a protective pouch, complete with spare bulbs.", 8250, 8250, 1, 1),
    ("SU-673", "FRAZIER Suction Tubes", "suction-tubes", "Frazier suction tubes with finger valve, available in flexible and rigid patterns.", 1260, 1260, 0, 0),
    ("FS-356", "Tissue Forceps", "forceps", "Versatile tissue forceps with 1x2 teeth for gentle and secure tissue grasp.", 465, 1050, 1, 0),
    ("ENT-109", "BUCK Ear Curette", "ear-nose-throat", "Buck ear curette with fine sharp edge for removal of ear wax and small debris.", 750, 750, 0, 0),
    ("GY-228", "CUSCO Vaginal Specula", "gynecology-obstetrics", "Cusco bivalve vaginal specula in multiple sizes with a smooth polished finish.", 1635, 2595, 0, 0),
    ("ENT-179", "TOYNBEE Ear Specula", "ear-nose-throat", "Toynbee ear specula, stainless steel with a matte finish to reduce glare.", 415, 415, 0, 0),
    ("SK-3183", "Scalpel Handles", "scalpels-knives", "Classic no. 3 and no. 4 scalpel handles in stainless steel with a secure blade lock.", 345, 615, 0, 0),
    ("HW-199", "Kidney Tray", "hollowware", "Hospital-grade stainless steel kidney tray with rolled edges for easy handling.", 1250, 1595, 1, 0),
    ("ENT-124", "HARTMANN Ear Catheter", "ear-nose-throat", "Hartmann ear catheters with olive-shaped tips for gentle insufflation.", 915, 915, 0, 0),
    ("GY-949", "IUD Obstetric Hook", "gynecology-obstetrics", "IUD insertion/removal obstetric hook in surgical stainless steel.", 615, 615, 0, 0),
    ("RT-501", "GILLIES Skin Hooks", "retractors", "Gillies skin hooks for fine tissue retraction during minor surgery.", 520, 780, 0, 0),
    ("DG-816", "Mercury Sphygmomanometer", "diagnostics", "Classic aneroid/mercury-free sphygmomanometer with cuff and carrying case.", 1850, 2450, 0, 1),
]

SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 600 600">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0e7490"/>
      <stop offset="1" stop-color="#164e63"/>
    </linearGradient>
  </defs>
  <rect width="600" height="600" fill="url(#g)"/>
  <g fill="none" stroke="#e0f2fe" stroke-width="10" stroke-linecap="round" opacity="0.9" transform="translate(170,120)">
    <!-- generic instrument silhouette -->
    <path d="M0 140 C 90 40, 170 40, 260 140" />
    <path d="M20 60 C 60 30, 100 30, 140 60" />
    <path d="M120 145 C 150 205, 160 250, 150 300" opacity="0.6"/>
  </g>
  <text x="300" y="470" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="34" font-weight="600" fill="#f0fdfa">{name}</text>
  <text x="300" y="515" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="20" fill="#cffafe" opacity="0.8">{category}</text>
</svg>"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def slugify(name):
    return name.strip().lower().replace(" ", "-").replace(",", "").replace("/", "-")


def generate_svg(product, category_name):
    os.makedirs(IMG_DIR, exist_ok=True)
    filename = f"{product[0].lower()}.svg"
    path = os.path.join(IMG_DIR, filename)
    svg = SVG_TEMPLATE.format(name=product[1], category=category_name)
    with open(path, "w") as f:
        f.write(svg)
    return f"/static/img/products/{filename}"


AD_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="160" viewBox="0 0 1200 160">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{c1}"/>
      <stop offset="1" stop-color="{c2}"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="160" fill="url(#g)"/>
  <text x="60" y="80" font-family="Segoe UI, Arial, sans-serif" font-size="42" font-weight="800" fill="#ffffff">{title}</text>
  <text x="60" y="120" font-family="Segoe UI, Arial, sans-serif" font-size="22" fill="#e0f2fe">{subtitle}</text>
  <rect x="1010" y="55" width="140" height="54" rx="27" fill="#ffffff" opacity="0.95"/>
  <text x="1080" y="90" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="22" font-weight="700" fill="{c2}">Call Us</text>
</svg>"""

SAMPLE_ADS = [
    ("Bulk Orders Welcome", "Hospitals & distributors — get export-grade prices on bulk surgical instruments. Call 0333-6095208", "top_banner", "#0e7490", "#164e63", "/contact"),
    ("New: ENT Instrument Range", "Ear, nose & throat instruments now in stock. Shop the collection today.", "mid_banner", "#155e75", "#0f172a", "/shop?category=ear-nose-throat"),
]


def generate_ad_svg(index, title, subtitle, c1, c2):
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img", "ads"), exist_ok=True)
    filename = f"ad-{index}.svg"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img", "ads", filename)
    with open(path, "w") as f:
        f.write(AD_TEMPLATE.format(title=title, subtitle=subtitle, c1=c1, c2=c2))
    return f"/static/img/ads/{filename}"


STOCK_RANGES = {
    "FS-101": (20, 100), "CCJ-102": (8, 40), "NS-3813": (0, 0), "SC-340": (3, 15),
    "SS-901": (5, 50), "FS-205": (12, 60), "SS-277": (6, 30), "SS-285": (0, 0),
    "GY-103": (4, 20), "DG-248": (25, 120), "ENT-104": (30, 150), "ENT-175": (28, 140),
    "DG-242": (18, 90), "SU-673": (14, 70), "FS-356": (33, 160), "ENT-109": (10, 50),
    "GY-228": (16, 80), "ENT-179": (0, 0), "SK-3183": (40, 200), "HW-199": (22, 110),
    "ENT-124": (11, 55), "GY-949": (9, 45), "RT-501": (19, 95), "DG-816": (7, 35),
}

# products whose default stock should be low/high in the demo
STOCK_OVERRIDES = {"NS-3813": 0, "SS-285": 0, "ENT-179": 0}

# (sku, author, rating, title, body, verified)
REVIEWS = [
    ("FS-101", "Dr. Ayesha Khan", 5, "Excellent grip", "The serrated tips hold tissue firmly without slipping. We use these in every minor procedure in our OPD.", 1),
    ("FS-101", "Bilal Ahmed", 4, "Good value", "Solid stainless steel for the price. Delivery took two days to Multan.", 1),
    ("FS-101", "Sana Iqbal", 5, "Worth every rupee", "Replaced three cheaper pairs with this. Much better finishing.", 0),
    ("SS-277", "Dr. Fahad Mehmood", 5, "Sharp and precise", "The TC edge cuts cleanly. Very happy with the finish quality.", 1),
    ("SS-277", "Usman Tariq", 4, "Nice weight", "Balanced and sturdy. The only thing is the packaging could be stronger.", 0),
    ("ENT-104", "Dr. Hina Sheikh", 5, "Complete set", "All tip sizes included and well labelled. Polished finish is excellent.", 1),
    ("ENT-104", "Malik Zeeshan", 4, "Good specula", "Fits well and sterilises without any corrosion so far.", 0),
    ("DG-816", "Dr. Kamran Butt", 4, "Accurate readings", "Matches our hospital aneroid unit closely. Cuff is decent quality.", 1),
    ("DG-816", "Rabia Noor", 3, "Okay for the price", "Works fine but the case hinge is a bit loose out of the box.", 0),
    ("GY-103", "Dr. Sadia Rehman", 5, "Smooth dilators", "Graduation is accurate and the set is properly sterilised before dispatch.", 1),
    ("HW-199", "Hospital Procurement", 5, "Bulk order, no complaints", "Ordered 40 trays for our ward. Consistent finish on every piece.", 1),
    ("HW-199", "Ayesha Siddiqui", 4, "Sturdy", "Rolled edges are smooth and easy to clean.", 0),
    ("SU-673", "Dr. Imran Qureshi", 4, "Good suction", "Finger valve works smoothly. Bought the rigid pattern as well.", 1),
    ("SK-3183", "Naveed Anwar", 5, "Secure blade lock", "The no. 3 handle grips the blade firmly with no wobble.", 1),
    ("CCJ-102", "Dr. Saira Javed", 4, "Good storage jars", "Glass is thick and the lids seal well. Catgut has stayed dry.", 1),
    ("SS-901", "Ophthalmology Dept.", 5, "Precision tips", "Sharp points and fine control. Suitable for delicate eye work.", 1),
]

# (code, kind, value, min_order, max_discount, usage_limit, expires_at)
COUPONS = [
    ("WELCOME10", "percent", 10, 2000, 3000, 0, None),
    ("BULK5000", "flat", 5000, 25000, 0, 50, None),
    ("FREESHIP", "percent", 5, 0, 0, 0, None),
]


def seed_reviews(cur, sku_to_id):
    for sku, author, rating, title, body, verified in REVIEWS:
        pid = sku_to_id.get(sku)
        if not pid:
            continue
        cur.execute(
            "INSERT INTO reviews (product_id, author, rating, title, body, verified) VALUES (?,?,?,?,?,?)",
            (pid, author, rating, title, body, verified),
        )


def seed_coupons(cur):
    for code, kind, value, min_order, max_discount, limit, expires in COUPONS:
        cur.execute(
            """INSERT OR IGNORE INTO coupons (code, kind, value, min_order, max_discount, usage_limit, expires_at, active)
               VALUES (?,?,?,?,?,?,?,1)""",
            (code, kind, value, min_order, max_discount, limit, expires, ),
        )


def seed():
    os.makedirs(IMG_DIR, exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        "DROP TABLE IF EXISTS reviews; DROP TABLE IF EXISTS coupons; DROP TABLE IF EXISTS login_codes; "
        "DROP TABLE IF EXISTS orders; DROP TABLE IF EXISTS messages; DROP TABLE IF EXISTS products; "
        "DROP TABLE IF EXISTS categories; DROP TABLE IF EXISTS ads;"
    )
    cur.executescript(SCHEMA)

    cat_ids = {}
    cat_names = {}
    for name, slug in CATEGORIES:
        cur.execute("INSERT INTO categories (name, slug) VALUES (?, ?)", (name, slug))
        cat_ids[slug] = cur.lastrowid
        cat_names[slug] = name

    sku_to_id = {}
    for sku, name, cat_slug, desc, pmin, pmax, featured, top in PRODUCTS:
        image = generate_svg((sku, name), cat_names[cat_slug])
        lo, hi = STOCK_RANGES.get(sku, (50, 200))
        import random

        stock = STOCK_OVERRIDES.get(sku, random.randint(lo, hi))
        cur.execute(
            "INSERT INTO products (sku, name, category_id, description, price_min, price_max, image, featured, top_sell, stock) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (sku, name, cat_ids[cat_slug], desc, pmin, pmax, image, featured, top, stock),
        )
        sku_to_id[sku] = cur.lastrowid

    seed_reviews(cur, sku_to_id)
    seed_coupons(cur)

    for i, (title, subtitle, position, c1, c2, link) in enumerate(SAMPLE_ADS):
        img = generate_ad_svg(i + 1, title, subtitle, c1, c2)
        cur.execute(
            "INSERT INTO ads (title, image, link, position, active) VALUES (?,?,?,?,1)",
            (title, img, link, position),
        )

    conn.commit()
    conn.close()


def column_exists(conn, table, column):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def migrate():
    if not os.path.exists(DB_PATH):
        return
    conn = get_conn()
    conn.executescript(SCHEMA)
    if not column_exists(conn, "products", "stock"):
        conn.execute("ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 100")
    if not column_exists(conn, "orders", "status"):
        conn.execute("ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'new'")
    if not column_exists(conn, "orders", "discount"):
        conn.execute("ALTER TABLE orders ADD COLUMN discount INTEGER NOT NULL DEFAULT 0")
    if not column_exists(conn, "orders", "coupon_code"):
        conn.execute("ALTER TABLE orders ADD COLUMN coupon_code TEXT")
    conn.commit()
    conn.close()


def init_db():
    if not os.path.exists(DB_PATH):
        seed()
        return
    migrate()
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    ad_count = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    review_count = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    coupon_count = conn.execute("SELECT COUNT(*) FROM coupons").fetchone()[0]
    conn.close()
    if count == 0:
        seed()
    else:
        if ad_count == 0:
            conn = get_conn()
            for i, (title, subtitle, position, c1, c2, link) in enumerate(SAMPLE_ADS):
                img = generate_ad_svg(i + 1, title, subtitle, c1, c2)
                conn.execute(
                    "INSERT INTO ads (title, image, link, position, active) VALUES (?,?,?,?,1)",
                    (title, img, link, position),
                )
            conn.commit()
            conn.close()
        if review_count == 0:
            conn = get_conn()
            cur = conn.cursor()
            sku_to_id = {
                r["sku"]: r["id"] for r in conn.execute("SELECT id, sku FROM products").fetchall()
            }
            seed_reviews(cur, sku_to_id)
            conn.commit()
            conn.close()
        if coupon_count == 0:
            conn = get_conn()
            seed_coupons(conn.cursor())
            conn.commit()
            conn.close()


if __name__ == "__main__":
    seed()
    print("Database seeded with", len(PRODUCTS), "products")