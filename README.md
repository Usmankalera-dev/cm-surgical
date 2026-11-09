# CM SURGICAL — E-Commerce Store

A full-stack surgical instruments e-commerce website (frontend + backend) for a Pakistani
client, modeled on [swantia.pk](https://swantia.pk).

## Stack

- **Backend:** Python + Flask + SQLite (no external DB required)
- **Frontend:** Server-rendered Jinja templates + vanilla JS (cart, checkout, filters)
- **Currency:** PKR (₨), prices exclusive of GST

## Features

### Storefront

- Home page with featured + top-selling products and ad banner slots
- **Header search suggestions** — type-ahead dropdown matching product name / SKU
- **Shop page filters** — category, text search, min/max price, in-stock-only, top-sellers,
  and sorting by name / price / rating / popularity. All filters sync to the URL so any
  filtered view is shareable, and active filters show as removable chips
- Product pages with quantity selector, live stock indicator and **related products**
- **Reviews & ratings** — 1–5 star reviews with a rating breakdown. Reviews are marked
  *Verified purchase* automatically when the reviewer supplies a phone number that appears
  on an order containing that product. One review per author per product per day
- **Wishlist** — ♥ button on every product card, saved to `localStorage`, with a dedicated
  `/wishlist` page and a live count in the header
- Shopping cart (persisted in localStorage, stock-aware)
- **Discount coupons** at checkout — percentage or flat amount, optional minimum order and
  maximum-discount cap, usage limits and expiry dates. The discount is always recalculated
  server-side when the order is placed; the browser value is only a preview
- **Cash on Delivery checkout** — order saved, contact confirmed by phone
- **Stock management** — out-of-stock items are flagged, checkout enforces limits
- **Order history** at `/orders` — look up all orders by phone number, with a status
  timeline and a **Buy Again** button that refills the cart at current prices/stock
- **Order tracking** — status (new → confirmed → shipped → delivered) shown via `/track`
- Contact form that saves messages
- About, Quality, Blog, Wishlist, My Orders and 404 pages

### Admin panel

- Manage products (name, prices, stock, image upload, featured/top-sell) and bulk import
- Manage ad slots (top + mid home-page banners)
- View orders, update status, read messages
- **Moderate reviews** — delete or toggle the *Verified purchase* badge
- **Manage coupons** — full CRUD with usage counts, limits and expiry
- **One-time login codes** — request a 6-digit code by email, valid for 10 minutes and
  single-use, with a rate limit of 5 requests per hour. Password login is kept as a
  fallback. See [Admin login](#admin-login) below.

## Setup & Run

```bash
cd surgical-store
pip3 install -r requirements.txt
python3 app.py
```

Open http://localhost:8000

- The database (`store.db`) and sample product images are created automatically on first run.
- Seeded with 24 sample surgical instruments across 11 categories, 16 sample reviews and
  3 sample coupons.
- Existing databases are migrated in place — new tables and columns are added automatically
  on startup without losing orders.

## API

| Method | Endpoint                       | Description                                                     |
| ------ | ------------------------------ | --------------------------------------------------------------- |
| GET    | `/api/products`                | List products (see filters below)                                |
| GET    | `/api/products/<id>`           | Single product (includes `rating` and `review_count`)            |
| GET    | `/api/categories`              | All categories                                                    |
| GET    | `/api/search/suggest?q=`       | Type-ahead suggestions (min. 2 characters, max. 8 results)       |
| GET    | `/api/products/<id>/reviews`   | List reviews for a product                                       |
| POST   | `/api/products/<id>/reviews`   | Add a review (auto-detects verified purchases)                   |
| POST   | `/api/coupons/validate`        | Validate a code against a subtotal → discount amount             |
| POST   | `/api/orders`                  | Create order (COD) + deduct stock + apply coupon                 |
| POST   | `/api/orders/reorder`          | Rebuild a previous order's items at current prices/stock         |
| POST   | `/api/contact`                 | Submit contact message                                           |

`/api/products` accepts `category`, `search`, `featured`, `top_sell`, `in_stock`,
`min_price`, `max_price` and `sort` (`name`, `price_asc`, `price_desc`, `rating`,
`popular`).

## Admin login

- URL: `/admin`
- **One-time code (recommended):** enter your email and click *Email me a login code*. A
  6-digit code is generated, single-use, and expires after `LOGIN_CODE_TTL_MINUTES`
  (default 10). Max `LOGIN_CODE_MAX_PER_HOUR` (default 5) requests per hour.
  Codes are stored as salted SHA-256 hashes, never in plain text.
- **Password fallback:** `ADMIN_PASSWORD` (default `admin123`).

No mail server is wired up, so the generated code is printed to the server console *and*
displayed on screen as a clearly-labelled demo box. To send it by email instead, replace
the body of `deliver_login_code()` in `app.py` with your SMTP call and delete the
`issued_code` block in `templates/admin/login.html`.

## Configuration

| Env var                    | Default                  | Purpose                                  |
| -------------------------- | ------------------------ | ---------------------------------------- |
| `SECRET_KEY`               | `change-me-in-production` | Session signing key — **set this**      |
| `ADMIN_PASSWORD`           | `admin123`               | Admin password fallback                   |
| `ADMIN_LOGIN_EMAIL`        | `admin@cmsurgical.pk`    | Default address for login codes           |
| `LOGIN_CODE_TTL_MINUTES`   | `10`                     | Login code lifetime                       |
| `LOGIN_CODE_MAX_PER_HOUR`  | `5`                      | Login code request rate limit             |

## Sending the site live

For production use Gunicorn instead of the dev server:

```bash
pip3 install gunicorn
SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))") \
ADMIN_PASSWORD=your-password \
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## Data

- Orders, messages, reviews, coupons and login codes are stored in `store.db`.
- Reset the demo data (products, categories, reviews, coupons) with: `python3 db.py`
  — note this **drops all orders and messages**.
