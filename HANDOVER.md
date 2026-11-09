# CM SURGICAL — Client Handover Guide

**Date:** 30 September 2026
**Prepared by:** [your name]

This document is everything the recipient needs to run, use, and maintain the website.
Keep it with the project files.

---

## 1. What you're receiving

A complete, working e-commerce website for a surgical instruments business. It is a
**Cash on Delivery** store — no online payment gateway is connected, by design.

```
surgical-store/
├── start.sh          ← use this to run the site
├── backup.sh         ← use this to back up the data
├── .env.example      ← copy to .env and set your passwords
├── app.py            website code
├── db.py             database structure + demo data
├── store.db          ALL live data lives here (products, orders, reviews…)
├── templates/        page layouts
├── static/           stylesheet, javascript, images
├── requirements.txt  list of Python packages needed
├── DEPLOY.md         how to put it online with a real domain
├── deploy/           ready-made server config + deploy script
├── README.md         technical reference (API, environment variables)
└── HANDOVER.md       this file
```

**Requirements:** a computer with Python 3.9 or newer, and internet access. Nothing else
— no database server, no monthly hosting fee, no licences.

---

## 2. Before you go live — three things you must do

The site is delivered with safe placeholders. **It will not start in production mode
until all three are done.** This is deliberate: it stops the site accidentally running
with a publicly known password.

### 2.1 Set the admin password

Log in at **http://localhost:8000/admin** with the password **`admin123`**, then
immediately:

1. Click **Password** in the left-hand admin menu (or use the red warning banner)
2. Enter `admin123` as the current password
3. Choose a new password of at least 8 characters, type it twice
4. Click **Change password**

You will be signed out and back in automatically. From then on `admin123` no longer
works — use your new password. **Write it down and store it in a password manager.**

The password is stored only as a scrambled hash, so nobody, including the developer,
can read it back. If it is lost it must be reset from the database.

> While the default password is still in use, a red warning banner appears on every
> admin page. It disappears once you have set your own password.

**Optional — also set `ADMIN_PASSWORD` in a config file** (belt and braces, and required
if the site is ever restarted with a fresh database):

```bash
cp .env.example .env
```

Open `.env` and fill in `SECRET_KEY` (generate one with
`python3 -c "import secrets; print(secrets.token_hex(32))"`) and `ADMIN_PASSWORD`.
`SECRET_KEY` keeps customer sessions secure and must be set before the site goes live.

### 2.2 Change the contact details shown on the site

Currently the site displays placeholder details. Search these files and replace them with
the real ones:

| What to change | File |
| --- | --- |
| Phone number, address (appears twice) | `templates/base.html` |
| Email address | `templates/base.html` |
| Company name in the copyright line | `templates/base.html` |
| Company name in the browser tab title | `templates/base.html` |

The logo is in `static/img/`. `cmd-logo-mark.png` is the header logo,
`cmd-logo.png` is the footer logo, `favicon.png` is the browser tab icon.

### 2.3 Set up admin login codes (optional but recommended)

The admin panel can log in two ways:

- **A one-time 6-digit code** requested by email — this is the secure option
- **A password** — a fallback

**Right now no email server is connected**, so the one-time code is displayed on screen
instead of being emailed. It still works and is still single-use with a 10-minute
expiry, but it is only suitable while whoever logs in is sitting at the computer.

To make codes arrive by real email, the developer needs to fill in one function —
`deliver_login_code()` in `app.py`. Give them your SMTP details (mail server, username,
password) and it is a small change. Until then, use the password login.

---

## 3. Running the site

```bash
cd surgical-store
./start.sh
```

Then open **http://localhost:8000** in a browser.

The site starts with debug mode **off** — this is correct and safe. It prints
`Debug mode is OFF`, which is reassuring, not an error.

**To stop it:** press `Ctrl + C` in the terminal.

**To develop/modify it:** `./start.sh --dev` turns on auto-reload and detailed error
messages. Never use `--dev` on a live site.

The first start takes a few seconds longer while Python packages install.

---

## 4. The admin panel

Go to **http://localhost:8000/admin** and sign in.

| Section | What you can do |
| --- | --- |
| **Dashboard** | Order count, revenue, low-stock alerts, recent orders |
| **Products** | Add, edit, delete. Set price, stock, category, featured/top-seller flags, upload a photo |
| **Bulk Import** | Upload a CSV to add or update many products at once |
| **Orders** | See every order; change status: new → confirmed → shipped → delivered |
| **Coupons** | Create discount codes — percentage or fixed amount, minimum order, expiry date, usage limit |
| **Reviews** | Delete reviews, or remove the "Verified purchase" badge if it's wrong |
| **Messages** | Contact form submissions |
| **Ad Banners** | Upload the two banner images shown on the home page |
| **Password** | Change the admin password — **do this first** |

### 4.1 Fulfilling an order — the daily routine

1. **Orders** → click the order to see what was bought
2. Confirm stock is deducted (it is, automatically, the moment the order is placed)
3. Pack and courier
4. **Orders** → change the status to *shipped*
5. When delivered → change to *delivered*

The customer can follow this themselves at `/track` using their order number and phone.

### 4.2 Adding a product with a real photo

**Products → New product**, fill in the details, then use the image upload field. A plain
photo of the instrument on a plain white background works best — square images look
best. The site resizes and displays it automatically.

### 4.3 Creating a discount code

**Coupons → New coupon.** For example, a 10% off code with a minimum order of ₨ 2,000:

- Code: `WELCOME10`
- Type: Percentage
- Value: 10
- Minimum order: 2000
- Maximum discount: 3000 (optional — stops huge orders getting enormous discounts)
- Expires: optional date
- Usage limit: optional

Customers enter it on the checkout page. **The discount is always recalculated on the
server when the order is placed** — the customer's browser cannot change what they pay.

Demo codes already exist: `WELCOME10`, `BULK5000`, `FREESHIP`. Delete them if you don't
want them, before you go live.

---

## 5. What customers can do

| Feature | Where |
| --- | --- |
| Browse products, filter by category, price, stock, rating | `/shop` |
| Search with suggestions as they type | Header search box |
| Save products to a wishlist for later | ♥ on any product |
| Leave a star rating and review | Product page |
| See reviews from confirmed buyers | Product page ("Verified purchase" badge) |
| Add to cart, change quantities | `/cart` |
| Apply a discount code, place a Cash on Delivery order | `/checkout` |
| See all their past orders, re-order in one click | `/orders` (enter phone number) |
| Track a delivery | `/track` (order number + phone) |
| Contact the business | `/contact` |

Reviews automatically show a **"Verified purchase"** badge when the reviewer's phone
number matches an order that contained that product. This is automatic — nothing to
switch on.

Orders are found by **phone number**. This means a customer who orders from two different
phones will see two separate order lists. Mention this to customers if it becomes an
issue; it can be changed later.

---

## 6. Backing up — please read this

**All of the business's data lives in one file: `store.db`.** If that file is lost, the
orders are gone. Back it up daily.

```bash
cd surgical-store
./backup.sh
```

This writes a dated, self-contained copy to `backups/` — the database, all uploaded
images, and the code — and automatically keeps only the 14 most recent. To restore, copy
the `store.db` from the backup folder over the one in the project root.

**For a small business, the simplest reliable routine:** run `./backup.sh` weekly and copy
the `backups/` folder to a USB stick, Google Drive, or Dropbox. A backup that only exists
on the same computer is not a backup.

---

## 7. Putting it online

The site currently runs on this computer only. To make it reachable by customers, it
needs to be hosted somewhere with a domain name. This is a decision for the client, and
it involves a recurring cost — it is not included in this handover.

**Options, roughly:**

| Option | Rough monthly cost | Notes |
| --- | --- | --- |
| A small VPS (Hetzner, DigitalOcean, Contabo) | $5–15 | Full control, most reliable. Needs a developer to set up. |
| Python hosting (Render, Railway, Fly.io) | $0–25 | Easiest. Needs a credit card for the free tier. |
| A Pakistani host with cPanel | PKR 1,500–4,000 | Local support in Urdu/English, easy to pay. |
| Keep it offline (demo/showroom only) | Free | Fine for showing the client; not for selling. |

**Whichever is chosen, the server must run the app under a proper web server**, not
Flask's built-in one. The starting point is:

```bash
pip3 install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

with a `.env` in place, behind nginx, and HTTPS enabled. This is development work, not a
configuration toggle — budget time for it.

**Recommended:** hire the developer who built this to set up hosting. Trying to do it
without experience usually ends with the site offline.

---

## 8. If something goes wrong

| Symptom | Cause | Fix |
| --- | --- | --- |
| "Refusing to start in production..." | `.env` still has the default password or secret key | Finish section 2.1 |
| `python3: command not found` | Python not installed | Install Python 3.9+ from python.org |
| Site will not start, "No module named flask" | Dependencies not installed | `python3 -m pip install -r requirements.txt` |
| Port already in use | Another copy is running | Find it: `lsof -i :8000` then stop it |
| Products missing after a restore | Wrong `store.db` | Restore from `backups/` |
| Admin login rejected | Password changed from the default | Check the `ADMIN_PASSWORD` line in `.env` |
| A customer cannot find their order | Ordered using a different phone number | Orders are looked up by phone only |

To see the full error, run `./start.sh --dev` — it prints detailed messages that are
hidden in normal mode for security.

---

## 9. Known limitations

Honest list, so nothing is a surprise later:

1. **No email is sent.** Admin login codes appear on screen instead of being emailed.
   Contact form submissions are stored but no email is sent to anyone. *(Section 2.3)*
2. **No payment gateway.** Cash on Delivery only.
3. **No customer accounts.** Customers are identified by phone number. No passwords, no
   login, no saved addresses.
4. **One product image per product.** No image gallery, no zoom.
5. **No shipping calculation.** Delivery is free; no zone-based rates.
6. **No product variations.** One price and one stock figure per product — no
   size/length options.
7. **No tax breakdown at checkout.** Prices are shown GST-exclusive, as agreed.
8. **Search is keyword-based.** It matches names, SKUs, and descriptions. It does not
   correct spelling mistakes — "scalpel" finds scalpels, "scalpol" does not.
9. **No analytics.** No visitor tracking of any kind.

Items 1, 3, 5 and 6 are the ones most likely to be requested first. All are possible
additions; none are defects.

---

## 10. Showing the site to someone before it is hosted

There is no need to pay for hosting just to show the site. A temporary link can be
created from the developer's computer with a tunnel.

```bash
# 1. ngrok needs a free account once:  ngrok config add-authtoken YOUR_TOKEN
ngrok http 8000
```

It prints a public link like `https://a1b2-c3d4.ngrok-free.app` that works for anyone,
until the terminal is closed.

**Before sending such a link, do all of the following — they are not optional:**

1. **Change the admin password** (section 2.1). The default `admin123` is printed in
   this document; anyone who has read the email it was sent in could otherwise sign in.
2. Do not share the link on social media or anywhere public. It is a temporary,
   unpassworded, unprotected copy of the live site.
3. Treat the link as expired once the demonstration is over. Closing the terminal stops it.

> **Note on the one-time login codes.** On-screen codes are switched **off** by default.
> Showing a login code in the browser is safe only while the site runs on the developer's
> own machine — as soon as the site is reachable over the internet, anyone can request a
> code, read it off the screen and sign in. The developer can switch the demo behaviour
> back on with `LOGIN_CODE_DEMO=1` while giving a local demonstration, and must switch it
> off again afterwards. Until real email delivery is configured, the password is the only
> working way in.

---

## 11. Handover checklist

- [ ] Section 2.1 — **admin password changed from `admin123` via Admin → Password**
- [ ] Section 2.2 — phone, address, email, company name replaced with real details
- [ ] Section 2.3 — decision made about admin login codes
- [ ] Demo coupons `WELCOME10`, `BULK5000`, `FREESHIP` deleted or kept deliberately
- [ ] 24 demo products reviewed — delete the ones not being sold
- [ ] A real order placed end-to-end as a test, then deleted
- [ ] `./backup.sh` run once, and the client shown where the backup lives
- [ ] Hosting decision made (section 7)
- [ ] **`DEPLOY.md` and the `deploy/` folder handed over** — needed by whoever does the hosting
- [ ] If a temporary public link was used, the admin password was changed first and the link stopped afterwards
- [ ] Recipient has run `./start.sh` themselves, successfully
- [ ] This guide, `README.md` and `.env.example` handed over together
- [ ] **The `.env` file is NOT shared publicly** — it contains the admin password

---

## Contact

Developer: [name] · [phone] · [email]
