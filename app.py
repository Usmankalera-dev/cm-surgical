import hashlib
import json
import os
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from db import LIKE_OP, get_conn, init_db, sql_interval_ago, sql_now, ts_param

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
ADMIN_LOGIN_EMAIL = os.environ.get("ADMIN_LOGIN_EMAIL", "admin@cmsurgical.pk")
LOGIN_CODE_TTL_MINUTES = int(os.environ.get("LOGIN_CODE_TTL_MINUTES", "10"))
LOGIN_CODE_MAX_PER_HOUR = int(os.environ.get("LOGIN_CODE_MAX_PER_HOUR", "5"))

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img", "products")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["LOGIN_CODE_TTL_MINUTES"] = LOGIN_CODE_TTL_MINUTES


def row_to_product(row):
    return {
        "id": row["id"],
        "sku": row["sku"],
        "name": row["name"],
        "category": row["cat_name"],
        "category_slug": row["cat_slug"],
        "description": row["description"],
        "price_min": row["price_min"],
        "price_max": row["price_max"],
        "price_min_str": f"{row['price_min']:,}",
        "price_max_str": f"{row['price_max']:,}",
        "image": row["image"],
        "featured": bool(row["featured"]),
        "top_sell": bool(row["top_sell"]),
        "stock": row["stock"],
        "in_stock": bool(row["stock"] > 0),
    }


def rating_map(product_ids):
    """product_id -> {"rating": float|None, "count": int} using a single query."""
    ids = list({int(i) for i in product_ids})
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    conn = get_conn()
    rows = conn.execute(
        f"""SELECT product_id, COUNT(*) AS n, AVG(rating) AS avg_rating
            FROM reviews WHERE product_id IN ({placeholders}) GROUP BY product_id""",
        ids,
    ).fetchall()
    conn.close()
    out = {}
    for r in rows:
        out[r["product_id"]] = {
            # AVG() returns Decimal on Postgres and float on SQLite;
            # normalise to float so jsonify can serialise it.
            "rating": float(round(r["avg_rating"], 1)) if r["avg_rating"] else None,
            "count": r["n"],
        }
    return out


def attach_ratings(products):
    ratings = rating_map([p["id"] for p in products])
    for p in products:
        r = ratings.get(p["id"], {"rating": None, "count": 0})
        p["rating"] = r["rating"]
        p["review_count"] = r["count"]
    return products


def get_product_row(product_id):
    conn = get_conn()
    row = conn.execute(
        """SELECT p.*, c.name AS cat_name, c.slug AS cat_slug
           FROM products p JOIN categories c ON c.id = p.category_id
           WHERE p.id = ?""",
        (product_id,),
    ).fetchone()
    conn.close()
    return row


def get_categories():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.context_processor
def inject_categories():
    # Only nag inside the admin panel, and only while the default password is still in use.
    warning = False
    try:
        path = request.path or ""
        if path.startswith("/admin") and not session.get("admin_logged_in"):
            pass
        elif path.startswith("/admin") and using_default_password():
            warning = True
    except Exception:
        warning = False
    return {"categories": get_categories(), "default_password_warning": warning}


def get_ads(position=None):
    conn = get_conn()
    if position:
        rows = conn.execute(
            "SELECT * FROM ads WHERE active = 1 AND position = ? ORDER BY id", (position,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM ads WHERE active = 1 ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------- Coupons ----------------


def _as_utc(value):
    """Stored timestamps are text in SQLite and datetime in Postgres;
    normalise both to an aware UTC datetime for comparison."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def evaluate_coupon(code, subtotal):
    """Return (coupon_row | None, discount, error_message)."""
    code = (code or "").strip().upper()
    if not code:
        return None, 0, ""
    conn = get_conn()
    row = conn.execute("SELECT * FROM coupons WHERE UPPER(code) = ?", (code,)).fetchone()
    conn.close()
    if row is None or not row["active"]:
        return None, 0, "This discount code is not valid."
    now = datetime.now(timezone.utc)
    if row["expires_at"] and _as_utc(row["expires_at"]) < now:
        return None, 0, "This discount code has expired."
    if row["starts_at"] and _as_utc(row["starts_at"]) > now:
        return None, 0, "This discount code is not active yet."
    if row["usage_limit"] and row["used_count"] >= row["usage_limit"]:
        return None, 0, "This discount code has reached its usage limit."
    if subtotal < row["min_order"]:
        return None, 0, (
            f"Minimum order of ₨ {row['min_order']:,} required for this code. "
            f"Add ₨ {row['min_order'] - subtotal:,} more."
        )
    if row["kind"] == "percent":
        discount = (subtotal * row["value"]) // 100
    else:
        discount = row["value"]
    if row["max_discount"]:
        discount = min(discount, row["max_discount"])
    discount = min(discount, subtotal)
    return row, discount, ""


# ---------------- Admin one-time login codes ----------------


def hash_login_code(code):
    return hashlib.sha256(f"{app.secret_key}:{code}".encode()).hexdigest()


def get_setting(key):
    conn = get_conn()
    row = conn.execute("SELECT value FROM admin_settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        f"INSERT INTO admin_settings (key, value, updated_at) VALUES (?, ?, {sql_now()}) "
        f"ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = {sql_now()}",
        (key, value),
    )
    conn.commit()
    conn.close()


def verify_admin_password(password):
    """Accept the password set in the admin panel, or the ADMIN_PASSWORD env var."""
    stored = get_setting("password_hash")
    if stored:
        return check_password_hash(stored, password)
    return bool(password) and secrets.compare_digest(password, ADMIN_PASSWORD)


def using_default_password():
    return get_setting("password_hash") is None and ADMIN_PASSWORD == "admin123"


def issue_login_code():
    """Create a one-time code. Returns (code, expires_at) or (None, error)."""
    conn = get_conn()
    recent = conn.execute(
        f"SELECT COUNT(*) FROM login_codes WHERE created_at > {sql_interval_ago(hours=1)}"
    ).fetchone()[0]
    if recent >= LOGIN_CODE_MAX_PER_HOUR:
        conn.close()
        return None, "Too many codes requested. Please try again later."
    conn.execute(f"DELETE FROM login_codes WHERE used = 1 OR expires_at < {sql_now()}")
    code = "".join(secrets.choice(string.digits) for _ in range(6))
    # Stored as UTC on both backends (TIMESTAMPTZ in Postgres, UTC text in
    # SQLite), which is what the expiry check below compares against.
    expires = datetime.now(timezone.utc) + timedelta(minutes=LOGIN_CODE_TTL_MINUTES)
    conn.execute(
        "INSERT INTO login_codes (code_hash, expires_at) VALUES (?, ?)",
        (hash_login_code(code), ts_param(expires)),
    )
    conn.commit()
    conn.close()
    return code, expires.strftime("%Y-%m-%d %H:%M:%S")


def deliver_login_code(code, expires):
    """Hand the code to the admin.

    Security note: showing the code on screen is ONLY safe while the site is running
    on the developer's own machine. As soon as the site is reachable on the internet,
    anyone can request a code, read it off the screen and sign in — so it is opt-in
    via LOGIN_CODE_DEMO=1 and off by default.
    """
    print(f"[admin login] code {code} for {ADMIN_LOGIN_EMAIL} (expires {expires})")
    if os.environ.get("LOGIN_CODE_DEMO") == "1":
        return code
    return None


def consume_login_code(code):
    code = (code or "").strip()
    if not code:
        return False
    conn = get_conn()
    row = conn.execute(
        f"SELECT * FROM login_codes WHERE code_hash = ? AND used = 0 AND expires_at > {sql_now()}",
        (hash_login_code(code),),
    ).fetchone()
    if row is None:
        conn.close()
        return False
    conn.execute("UPDATE login_codes SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return True


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)

    return wrapper


@app.route("/")
def index():
    conn = get_conn()
    featured = conn.execute(
        """SELECT p.*, c.name AS cat_name, c.slug AS cat_slug
           FROM products p JOIN categories c ON c.id = p.category_id
           WHERE p.featured = 1 ORDER BY p.name LIMIT 8"""
    ).fetchall()
    top_sell = conn.execute(
        """SELECT p.*, c.name AS cat_name, c.slug AS cat_slug
           FROM products p JOIN categories c ON c.id = p.category_id
           WHERE p.top_sell = 1 ORDER BY p.name LIMIT 8"""
    ).fetchall()
    conn.close()
    return render_template(
        "index.html",
        featured=attach_ratings([row_to_product(r) for r in featured]),
        top_sell=attach_ratings([row_to_product(r) for r in top_sell]),
        categories=get_categories(),
        top_banner_ads=get_ads("top_banner"),
        mid_banner_ads=get_ads("mid_banner"),
    )


@app.route("/shop")
def shop():
    return render_template("shop.html", categories=get_categories())


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    row = get_product_row(product_id)
    if row is None:
        abort(404)
    product = attach_ratings([row_to_product(row)])[0]
    conn = get_conn()
    reviews = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM reviews WHERE product_id = ? ORDER BY verified DESC, created_at DESC LIMIT 20",
            (product_id,),
        ).fetchall()
    ]
    breakdown = {r["rating"]: r["n"] for r in conn.execute(
        "SELECT rating, COUNT(*) AS n FROM reviews WHERE product_id = ? GROUP BY rating",
        (product_id,),
    ).fetchall()}
    related = conn.execute(
        """SELECT p.*, c.name AS cat_name, c.slug AS cat_slug
           FROM products p JOIN categories c ON c.id = p.category_id
           WHERE p.category_id = ? AND p.id != ? ORDER BY p.name LIMIT 4""",
        (row["category_id"], product_id),
    ).fetchall()
    conn.close()
    return render_template(
        "product.html",
        product=product,
        reviews=reviews,
        breakdown=breakdown,
        related=attach_ratings([row_to_product(r) for r in related]),
    )


@app.route("/cart")
def cart():
    return render_template("cart.html")


@app.route("/wishlist")
def wishlist():
    return render_template("wishlist.html")


@app.route("/checkout")
def checkout():
    return render_template("checkout.html")


@app.route("/track", methods=["GET", "POST"])
def track_order():
    order = None
    error = None
    if request.method == "POST" or (request.args.get("order_id") and request.args.get("phone")):
        order_id = (request.values.get("order_id") or "").strip()
        phone = (request.values.get("phone") or "").strip()
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM orders WHERE id = ? AND phone = ?", (order_id, phone)
        ).fetchone()
        conn.close()
        if row is None:
            error = "No order found with that ID and phone number."
        else:
            order = dict(row)
            order["products"] = json.loads(order["items"])
    return render_template("track.html", order=order, error=error, phone=phone if request.method == "POST" else "")


@app.route("/order-confirmed/<int:order_id>")
def order_confirmed(order_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    if row is None:
        abort(404)
    order = dict(row)
    order["products"] = json.loads(order["items"])
    return render_template("order_confirmation.html", order=order)


@app.route("/orders", methods=["GET", "POST"])
def order_history():
    orders = []
    error = None
    phone = (request.values.get("phone") or "").strip()
    if request.method == "POST" and not phone:
        error = "Please enter the phone number used on your order."
    if phone:
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM orders WHERE phone = ? ORDER BY id DESC LIMIT 50", (phone,)
        ).fetchall()
        conn.close()
        for r in rows:
            o = dict(r)
            o["products"] = json.loads(o["items"])
            orders.append(o)
        if not orders and not error:
            error = "No orders found for that phone number."
    return render_template("orders.html", orders=orders, error=error, phone=phone)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/quality")
def quality():
    return render_template("quality.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/blog")
def blog():
    return render_template("blog.html")


# ---------------- Admin ----------------


def save_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        return None
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    dest = os.path.join(UPLOAD_FOLDER, filename)
    file_storage.save(dest)
    return f"/static/img/products/{filename}"


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    issued_code = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "request_code":
            if os.environ.get("LOGIN_CODE_DEMO") != "1":
                # No mail server, and on-screen codes are switched off because the
                # site may be reachable from the internet. Do not create a code that
                # nobody can receive, and never reveal one on screen.
                flash(
                    "Email delivery is not set up on this site, so no code was sent. "
                    "Please sign in with your password.",
                    "error",
                )
            else:
                code, expires = issue_login_code()
                if code is None:
                    flash(expires, "error")
                else:
                    session["login_code_email"] = request.form.get("email", "").strip() or ADMIN_LOGIN_EMAIL
                    issued_code = deliver_login_code(code, expires)
                    flash("Your 6-digit code is below. Enter it to sign in.", "ok")
        elif action == "verify_code":
            if consume_login_code(request.form.get("code")):
                session["admin_logged_in"] = True
                session.pop("login_code_email", None)
                return redirect(url_for("admin_dashboard"))
            flash("That code is invalid or has expired. Request a new one.", "error")
        elif request.form.get("password") and verify_admin_password(request.form["password"]):
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        elif request.form.get("password"):
            flash("Incorrect password.", "error")
    return render_template("admin/login.html", issued_code=issued_code)


@app.route("/admin/password", methods=["GET", "POST"])
def admin_password():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not verify_admin_password(current):
            flash("Your current password is not correct.", "error")
        elif len(new) < 8:
            flash("The new password must be at least 8 characters long.", "error")
        elif new != confirm:
            flash("The two new passwords do not match.", "error")
        elif verify_admin_password(new):
            flash("The new password must be different from the current one.", "error")
        else:
            set_setting("password_hash", generate_password_hash(new))
            session.clear()
            session["admin_logged_in"] = True
            flash("Password changed. Please use your new password next time.", "ok")
            return redirect(url_for("admin_dashboard"))
    return render_template("admin/password.html", env_password_in_use=using_default_password())


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("login_code_email", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    conn = get_conn()
    stats = {
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "messages": conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
        "ads": conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0],
        "reviews": conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0],
        "coupons": conn.execute("SELECT COUNT(*) FROM coupons WHERE active = 1").fetchone()[0],
    }
    latest_orders = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 5").fetchall()
    latest_messages = conn.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        latest_orders=[dict(r) for r in latest_orders],
        latest_messages=[dict(r) for r in latest_messages],
    )


@app.route("/admin/products")
@login_required
def admin_products():
    conn = get_conn()
    rows = conn.execute(
        """SELECT p.*, c.name AS cat_name FROM products p
           JOIN categories c ON c.id = p.category_id ORDER BY p.id DESC"""
    ).fetchall()
    conn.close()
    return render_template("admin/products.html", products=[dict(r) for r in rows])


def product_form_data():
    sku = (request.form.get("sku") or "").strip()
    name = (request.form.get("name") or "").strip()
    category_id = request.form.get("category_id")
    description = (request.form.get("description") or "").strip()
    price_min = int(request.form.get("price_min") or 0)
    price_max = int(request.form.get("price_max") or price_min)
    stock = int(request.form.get("stock") or 0)
    featured = 1 if request.form.get("featured") else 0
    top_sell = 1 if request.form.get("top_sell") else 0
    image = save_upload(request.files.get("image"))
    return sku, name, category_id, description, price_min, price_max, stock, featured, top_sell, image


@app.route("/admin/products/new", methods=["GET", "POST"])
@login_required
def admin_product_new():
    if request.method == "POST":
        (sku, name, category_id, description, price_min, price_max, stock, featured, top_sell, image) = product_form_data()
        if not (name and category_id and price_min):
            flash("Name, category and a price are required.", "error")
        else:
            if image is None and request.files.get("image"):
                flash("Image type not allowed (png, jpg, jpeg, gif, webp, svg).", "error")
            else:
                if image is None:
                    conn = get_conn()
                    row = conn.execute("SELECT name FROM categories WHERE id = ?", (category_id,)).fetchone()
                    cat_name = row["name"] if row else "General"
                    conn.close()
                    from db import generate_svg
                    image = generate_svg((sku or name[:8].upper(), name), cat_name)
                conn = get_conn()
                conn.execute(
                    """INSERT INTO products (sku, name, category_id, description, price_min, price_max, image, featured, top_sell, stock)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (sku or name[:8].upper(), name, category_id, description, price_min, price_max, image, featured, top_sell, stock),
                )
                conn.commit()
                conn.close()
                flash("Product added.", "ok")
                return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", product=None, categories=get_categories())


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def admin_product_edit(product_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if row is None:
        abort(404)
    if request.method == "POST":
        (sku, name, category_id, description, price_min, price_max, stock, featured, top_sell, image) = product_form_data()
        if not name:
            flash("Name is required.", "error")
        else:
            if image is None:
                image = row["image"]
            conn.execute(
                """UPDATE products SET sku=?, name=?, category_id=?, description=?, price_min=?, price_max=?, image=?, featured=?, top_sell=?, stock=? WHERE id=?""",
                (sku, name, category_id, description, price_min, price_max, image, featured, top_sell, stock, product_id),
            )
            conn.commit()
            conn.close()
            flash("Product updated.", "ok")
            return redirect(url_for("admin_products"))
    conn.close()
    return render_template("admin/product_form.html", product=dict(row), categories=get_categories())


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@login_required
def admin_product_delete(product_id):
    conn = get_conn()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    flash("Product deleted.", "ok")
    return redirect(url_for("admin_products"))


@app.route("/admin/products/import", methods=["GET", "POST"])
@login_required
def admin_product_import():
    import re as _re

    def slugify(name):
        s = _re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
        return s or "general"

    def make_category(name):
        conn = get_conn()
        row = conn.execute(
            "SELECT id FROM categories WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if row:
            cid = row["id"]
        else:
            slug = slugify(name)
            cur = conn.execute("INSERT INTO categories (name, slug) VALUES (?, ?)", (name, slug))
            cid = cur.lastrowid
            conn.commit()
        conn.close()
        return cid

    result = None
    if request.method == "POST":
        text = request.form.get("rows", "")
        conn = get_conn()
        added = 0
        errors = []
        line_number = 0
        for raw in text.splitlines():
            line_number += 1
            line = raw.strip().rstrip(",").strip()
            if not line:
                continue
            fields = [f.strip() for f in line.split("|")]
            if len(fields) < 2 or not fields[0]:
                errors.append(f"Line {line_number}: needs at least a name and a price.")
                continue
            name = fields[0]
            cat_name = fields[1] if len(fields) > 1 and fields[1] else "General"
            try:
                price_min = int(float(fields[2].replace(",", "").replace("₨", "")))
            except (IndexError, ValueError):
                errors.append(f"Line {line_number}: bad price for '{name}'.")
                continue
            price_max = price_min if len(fields) < 4 else int(float(fields[3].replace(",", "").replace("₨", "")) or price_min)
            stock = 0 if len(fields) < 5 else int(float(fields[4].replace(",", "")) or 0)
            desc = fields[5].strip() if len(fields) > 5 else ""
            cat_id = make_category(cat_name)
            sku = _re.sub(r"[^A-Z0-9]+", "", name.upper())[:8] or "ITEM"
            image = None
            try:
                from db import generate_svg
                image = generate_svg((sku, name), cat_name)
            except Exception:
                image = cat_name
            conn.execute(
                """INSERT INTO products (sku, name, category_id, description, price_min, price_max, image, featured, top_sell, stock)
                   VALUES (?,?,?,?,?,?,?,0,0,?)""",
                (sku, name, cat_id, desc, price_min, price_max, image, stock),
            )
            added += 1
        conn.commit()
        conn.close()
        result = {"added": added, "errors": errors}
        flash(f"Imported {added} product(s).", "ok" if not errors else "error")
    return render_template("admin/products_import.html", result=result)


@app.route("/admin/orders")
@login_required
def admin_orders():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    conn.close()
    orders = []
    for r in rows:
        o = dict(r)
        o["products"] = json.loads(o["items"])
        orders.append(o)
    return render_template("admin/orders.html", orders=orders)


ORDER_STATUSES = ["new", "confirmed", "shipped", "delivered", "cancelled"]

app.jinja_env.globals["order_rank"] = lambda s: {
    "new": 0, "confirmed": 1, "shipped": 2, "delivered": 3
}.get(s, -1)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@login_required
def admin_order_status(order_id):
    status = request.form.get("status")
    if status not in ORDER_STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("admin_orders"))
    conn = get_conn()
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()
    flash(f"Order #{order_id} marked as {status}.", "ok")
    return redirect(url_for("admin_orders"))


@app.route("/admin/messages")
@login_required
def admin_messages():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM messages ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin/messages.html", messages=[dict(r) for r in rows])


@app.route("/admin/reviews")
@login_required
def admin_reviews():
    conn = get_conn()
    rows = conn.execute(
        """SELECT r.*, p.name AS product_name, p.sku, p.image
           FROM reviews r JOIN products p ON p.id = r.product_id
           ORDER BY r.id DESC"""
    ).fetchall()
    conn.close()
    return render_template("admin/reviews.html", reviews=[dict(r) for r in rows])


@app.route("/admin/reviews/<int:review_id>/delete", methods=["POST"])
@login_required
def admin_review_delete(review_id):
    conn = get_conn()
    conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    conn.commit()
    conn.close()
    flash("Review deleted.", "ok")
    return redirect(url_for("admin_reviews"))


@app.route("/admin/reviews/<int:review_id>/verify", methods=["POST"])
@login_required
def admin_review_verify(review_id):
    conn = get_conn()
    row = conn.execute("SELECT verified FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if row is not None:
        conn.execute("UPDATE reviews SET verified = ? WHERE id = ?", (0 if row["verified"] else 1, review_id))
        conn.commit()
    conn.close()
    flash("Review updated.", "ok")
    return redirect(url_for("admin_reviews"))


def coupon_form_data():
    code = (request.form.get("code") or "").strip().upper()
    kind = request.form.get("kind") if request.form.get("kind") in ("percent", "flat") else "percent"
    value = max(0, int(request.form.get("value") or 0))
    min_order = max(0, int(request.form.get("min_order") or 0))
    max_discount = max(0, int(request.form.get("max_discount") or 0))
    usage_limit = max(0, int(request.form.get("usage_limit") or 0))
    expires_at = (request.form.get("expires_at") or "").strip() or None
    if expires_at and len(expires_at) == 10:
        expires_at = expires_at + " 23:59:59"
    active = 1 if request.form.get("active") else 0
    return code, kind, value, min_order, max_discount, usage_limit, expires_at, active


@app.route("/admin/coupons")
@login_required
def admin_coupons():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM coupons ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin/coupons.html", coupons=[dict(r) for r in rows])


@app.route("/admin/coupons/new", methods=["GET", "POST"])
@login_required
def admin_coupon_new():
    if request.method == "POST":
        code, kind, value, min_order, max_discount, usage_limit, expires_at, active = coupon_form_data()
        if not code or value <= 0:
            flash("Code and a discount value are required.", "error")
        else:
            conn = get_conn()
            existing = conn.execute("SELECT id FROM coupons WHERE UPPER(code) = ?", (code,)).fetchone()
            if existing is not None:
                conn.close()
                flash(f"Coupon '{code}' already exists.", "error")
            else:
                conn.execute(
                    """INSERT INTO coupons (code, kind, value, min_order, max_discount, usage_limit, expires_at, active)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (code, kind, value, min_order, max_discount, usage_limit, expires_at, active),
                )
                conn.commit()
                conn.close()
                flash(f"Coupon {code} created.", "ok")
                return redirect(url_for("admin_coupons"))
    return render_template("admin/coupon_form.html", coupon=None)


@app.route("/admin/coupons/<int:coupon_id>/edit", methods=["GET", "POST"])
@login_required
def admin_coupon_edit(coupon_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM coupons WHERE id = ?", (coupon_id,)).fetchone()
    if row is None:
        conn.close()
        abort(404)
    if request.method == "POST":
        code, kind, value, min_order, max_discount, usage_limit, expires_at, active = coupon_form_data()
        if not code or value <= 0:
            flash("Code and a discount value are required.", "error")
        else:
            clash = conn.execute(
                "SELECT id FROM coupons WHERE UPPER(code) = ? AND id != ?", (code, coupon_id)
            ).fetchone()
            if clash is not None:
                flash(f"Coupon '{code}' already exists.", "error")
            else:
                conn.execute(
                    """UPDATE coupons SET code=?, kind=?, value=?, min_order=?, max_discount=?,
                       usage_limit=?, expires_at=?, active=? WHERE id=?""",
                    (code, kind, value, min_order, max_discount, usage_limit, expires_at, active, coupon_id),
                )
                conn.commit()
                conn.close()
                flash("Coupon updated.", "ok")
                return redirect(url_for("admin_coupons"))
    conn.close()
    return render_template("admin/coupon_form.html", coupon=dict(row))


@app.route("/admin/coupons/<int:coupon_id>/delete", methods=["POST"])
@login_required
def admin_coupon_delete(coupon_id):
    conn = get_conn()
    conn.execute("DELETE FROM coupons WHERE id = ?", (coupon_id,))
    conn.commit()
    conn.close()
    flash("Coupon deleted.", "ok")
    return redirect(url_for("admin_coupons"))


@app.route("/admin/ads")
@login_required
def admin_ads():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM ads ORDER BY id").fetchall()
    conn.close()
    return render_template("admin/ads.html", ads=[dict(r) for r in rows])


@app.route("/admin/ads/new", methods=["GET", "POST"])
@login_required
def admin_ad_new():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        link = (request.form.get("link") or "").strip()
        position = request.form.get("position") or "top_banner"
        active = 1 if request.form.get("active") else 0
        image = save_upload(request.files.get("image"))
        if not title:
            flash("Title is required.", "error")
        else:
            conn = get_conn()
            conn.execute(
                "INSERT INTO ads (title, image, link, position, active) VALUES (?,?,?,?,?)",
                (title, image, link, position, active),
            )
            conn.commit()
            conn.close()
            flash("Ad added.", "ok")
            return redirect(url_for("admin_ads"))
    return render_template("admin/ad_form.html", ad=None)


@app.route("/admin/ads/<int:ad_id>/edit", methods=["GET", "POST"])
@login_required
def admin_ad_edit(ad_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM ads WHERE id = ?", (ad_id,)).fetchone()
    if row is None:
        abort(404)
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        link = (request.form.get("link") or "").strip()
        position = request.form.get("position") or "top_banner"
        active = 1 if request.form.get("active") else 0
        image = save_upload(request.files.get("image"))
        if not title:
            flash("Title is required.", "error")
        else:
            if image is None:
                image = row["image"]
            conn.execute(
                "UPDATE ads SET title=?, image=?, link=?, position=?, active=? WHERE id=?",
                (title, image, link, position, active, ad_id),
            )
            conn.commit()
            conn.close()
            flash("Ad updated.", "ok")
            return redirect(url_for("admin_ads"))
    conn.close()
    return render_template("admin/ad_form.html", ad=dict(row))


@app.route("/admin/ads/<int:ad_id>/delete", methods=["POST"])
@login_required
def admin_ad_delete(ad_id):
    conn = get_conn()
    conn.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
    conn.commit()
    conn.close()
    flash("Ad deleted.", "ok")
    return redirect(url_for("admin_ads"))


# ---------------- API ----------------


@app.route("/api/categories")
def api_categories():
    return jsonify(get_categories())


@app.route("/api/products")
def api_products():
    category = request.args.get("category")
    search = request.args.get("search", "").strip()
    featured = request.args.get("featured")
    top_sell = request.args.get("top_sell")
    in_stock = request.args.get("in_stock")
    min_price = request.args.get("min_price", type=int)
    max_price = request.args.get("max_price", type=int)
    sort = request.args.get("sort", "name")
    conn = get_conn()
    query = """SELECT p.*, c.name AS cat_name, c.slug AS cat_slug
               FROM products p JOIN categories c ON c.id = p.category_id WHERE 1=1"""
    params = []
    if category:
        query += " AND c.slug = ?"
        params.append(category)
    if featured:
        query += " AND p.featured = 1"
    if top_sell:
        query += " AND p.top_sell = 1"
    if in_stock in ("1", "true", "yes"):
        query += " AND p.stock > 0"
    if min_price is not None:
        query += " AND p.price_max >= ?"
        params.append(min_price)
    if max_price is not None:
        query += " AND p.price_min <= ?"
        params.append(max_price)
    if search:
        query += f" AND (p.name {LIKE_OP} ? OR p.description {LIKE_OP} ? OR p.sku {LIKE_OP} ?)"
        like = f"%{search}%"
        params.extend([like, like, like])

    if sort == "price_asc":
        query += " ORDER BY p.price_min, p.name"
    elif sort == "price_desc":
        query += " ORDER BY p.price_max DESC, p.name"
    elif sort == "rating":
        query += " ORDER BY (SELECT AVG(rating) FROM reviews WHERE product_id = p.id) IS NULL, (SELECT AVG(rating) FROM reviews WHERE product_id = p.id) DESC, p.name"
    elif sort == "popular":
        query += " ORDER BY p.top_sell DESC, p.featured DESC, p.name"
    else:
        query += " ORDER BY p.name"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify(attach_ratings([row_to_product(r) for r in rows]))


@app.route("/api/products/<int:product_id>")
def api_product(product_id):
    row = get_product_row(product_id)
    if row is None:
        abort(404)
    return jsonify(attach_ratings([row_to_product(row)])[0])


@app.route("/api/search/suggest")
def api_search_suggest():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    like = f"%{q}%"
    conn = get_conn()
    rows = conn.execute(
        f"""SELECT p.id, p.sku, p.name, p.image, p.price_min, p.price_max, p.stock, c.name AS cat_name
           FROM products p JOIN categories c ON c.id = p.category_id
           WHERE p.name {LIKE_OP} ? OR p.sku {LIKE_OP} ?
           ORDER BY (p.name {LIKE_OP} ?) DESC, p.name LIMIT 8""",
        (like, like, f"{q}%"),
    ).fetchall()
    conn.close()
    return jsonify(
        [
            {
                "id": r["id"],
                "sku": r["sku"],
                "name": r["name"],
                "image": r["image"],
                "category": r["cat_name"],
                "price": r["price_max"] or r["price_min"],
                "in_stock": bool(r["stock"] > 0),
            }
            for r in rows
        ]
    )


@app.route("/api/products/<int:product_id>/reviews", methods=["GET", "POST"])
def api_product_reviews(product_id):
    if get_product_row(product_id) is None:
        abort(404)

    if request.method == "GET":
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM reviews WHERE product_id = ? ORDER BY verified DESC, created_at DESC",
            (product_id,),
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    data = request.get_json(silent=True) or {}
    author = (data.get("author") or "").strip()
    body = (data.get("body") or "").strip()
    title = (data.get("title") or "").strip()
    phone = (data.get("phone") or "").strip()
    try:
        rating = int(data.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0

    if not (author and body):
        return jsonify({"error": "Please add your name and a review."}), 400
    if rating < 1 or rating > 5:
        return jsonify({"error": "Please choose a rating between 1 and 5 stars."}), 400
    if len(body) > 2000:
        return jsonify({"error": "Review is too long (2000 characters max)."}), 400

    verified = 0
    if phone:
        conn = get_conn()
        match = conn.execute(
            "SELECT items FROM orders WHERE phone = ?", (phone,)
        ).fetchall()
        conn.close()
        for row in match:
            try:
                if any(str(i.get("id")) == str(product_id) for i in json.loads(row["items"])):
                    verified = 1
                    break
            except (TypeError, ValueError):
                continue

    conn = get_conn()
    recent = conn.execute(
        f"""SELECT id FROM reviews WHERE product_id = ? AND LOWER(author) = LOWER(?)
           AND created_at > {sql_interval_ago(days=1)}""",
        (product_id, author),
    ).fetchone()
    if recent is not None:
        conn.close()
        return jsonify({"error": "You already reviewed this product recently."}), 429
    conn.execute(
        "INSERT INTO reviews (product_id, author, rating, title, body, verified) VALUES (?,?,?,?,?,?)",
        (product_id, author, rating, title or None, body, verified),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "verified": bool(verified)}), 201


@app.route("/api/coupons/validate", methods=["POST"])
def api_validate_coupon():
    data = request.get_json(silent=True) or {}
    code = data.get("code") or request.form.get("code") or ""
    try:
        subtotal = int(data.get("subtotal") or 0)
    except (TypeError, ValueError):
        subtotal = 0
    coupon, discount, error = evaluate_coupon(code, subtotal)
    if error:
        return jsonify({"valid": False, "error": error}), 400
    if coupon is None:
        return jsonify({"valid": True, "discount": 0, "code": "", "message": "No discount code entered."})
    return jsonify(
        {
            "valid": True,
            "code": coupon["code"],
            "discount": discount,
            "discount_str": f"₨ {discount:,}",
            "kind": coupon["kind"],
            "message": (
                f"{coupon['value']}% off applied."
                if coupon["kind"] == "percent"
                else f"₨ {coupon['value']:,} off applied."
            ),
        }
    )


@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()
    address = (data.get("address") or "").strip()
    city = (data.get("city") or "").strip()
    items = data.get("items") or []
    note = (data.get("note") or "").strip()
    coupon_code = (data.get("coupon_code") or "").strip().upper()

    if not (name and phone and address and city and items):
        return jsonify({"error": "Please fill all required fields and add items to your cart."}), 400

    subtotal = 0
    normalized = []
    for item in items:
        pid = item.get("id")
        qty = int(item.get("quantity") or 0)
        if qty <= 0:
            continue
        row = get_product_row(pid)
        if row is None:
            return jsonify({"error": "A product in your cart is no longer available."}), 400
        if qty > row["stock"]:
            return (
                jsonify(
                    {
                        "error": f"Only {row['stock']} unit(s) of \"{row['name']}\" are in stock. Please reduce the quantity."
                    }
                ),
                400,
            )
        price = row["price_max"] or row["price_min"]
        subtotal += price * qty
        normalized.append(
            {
                "id": pid,
                "sku": row["sku"],
                "name": row["name"],
                "price": price,
                "quantity": qty,
                "image": row["image"],
            }
        )

    if subtotal <= 0:
        return jsonify({"error": "Your cart is empty."}), 400

    coupon, discount, coupon_error = evaluate_coupon(coupon_code, subtotal)
    if coupon_error:
        return jsonify({"error": coupon_error}), 400
    total = subtotal - discount

    conn = get_conn()
    try:
        conn.execute("BEGIN")
        cur = conn.execute(
            """INSERT INTO orders (name, phone, email, address, city, total, items, note, status, discount, coupon_code)
               VALUES (?,?,?,?,?,?,?,?,'new',?,?)""",
            (name, phone, email, address, city, total, json.dumps(normalized), note, discount, coupon["code"] if coupon else None),
        )
        for item in normalized:
            conn.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?", (item["quantity"], item["id"])
            )
        if coupon is not None:
            conn.execute("UPDATE coupons SET used_count = used_count + 1 WHERE id = ?", (coupon["id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        app.logger.exception("Order placement failed")
        return jsonify({"error": "Could not place the order. Please try again."}), 500
    order_id = cur.lastrowid
    conn.close()
    return jsonify(
        {
            "order_id": order_id,
            "subtotal": subtotal,
            "discount": discount,
            "total": total,
            "total_str": f"₨ {total:,}",
        }
    ), 201


@app.route("/api/orders/reorder", methods=["POST"])
def reorder_order():
    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id")
    phone = (data.get("phone") or "").strip()
    if not (order_id and phone):
        return jsonify({"error": "Order ID and phone number are required."}), 400
    conn = get_conn()
    row = conn.execute("SELECT items FROM orders WHERE id = ? AND phone = ?", (order_id, phone)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "No order found with that ID and phone number."}), 404
    try:
        stored = json.loads(row["items"])
    except (TypeError, ValueError):
        stored = []
    items = []
    for item in stored:
        fresh = get_product_row(item.get("id"))
        if fresh is None:
            continue
        items.append(
            {
                "id": fresh["id"],
                "sku": fresh["sku"],
                "name": fresh["name"],
                "image": fresh["image"],
                "category": fresh["cat_name"],
                "price": fresh["price_max"] or fresh["price_min"],
                "stock": fresh["stock"],
                "quantity": min(item.get("quantity", 1), max(fresh["stock"], 0)),
                "available": fresh["stock"] > 0,
            }
        )
    return jsonify({"items": items, "added": [i for i in items if i["quantity"] > 0]})


@app.route("/api/contact", methods=["POST"])
def submit_message():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()
    if not (name and email and subject and message):
        return jsonify({"error": "Please fill in all fields."}), 400
    conn = get_conn()
    conn.execute(
        "INSERT INTO messages (name, email, subject, message) VALUES (?,?,?,?)",
        (name, email, subject, message),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    init_db()
    _debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    _prod = os.environ.get("APP_ENV", "dev") == "production"

    if _prod:
        missing = [
            name
            for name, val in (("SECRET_KEY", app.secret_key), ("ADMIN_PASSWORD", ADMIN_PASSWORD))
            if val in ("change-me-in-production", "admin123")
        ]
        if missing:
            raise SystemExit(
                "Refusing to start in production with default values for: "
                + ", ".join(missing)
                + "\nSet them as environment variables first. See HANDOVER.md."
            )

    if not _debug:
        print("  ! Debug mode is OFF. Set FLASK_DEBUG=1 to enable it while developing.")
    if app.secret_key == "change-me-in-production":
        print("  ! WARNING: SECRET_KEY is the default. Set a real one before going live.")
    if ADMIN_PASSWORD == "admin123":
        print("  ! WARNING: ADMIN_PASSWORD is 'admin123'. Change it before going live.")

    app.run(debug=_debug, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
