# CM SURGICAL — Going Live With a Domain

For whoever sets up the hosting. Follow in order. **Step 3 is the one that must not be
skipped.**

---

## 0. What the client needs to obtain first

Two separate things, bought from different places:

| What | Where | Rough cost |
| --- | --- | --- |
| **A domain name** | Namecheap, GoDaddy, Hostinger, or a Pakistani registrar | $8–15/year (`.com`), PKR 1,500–3,000 (`.pk`) |
| **A server to run it on** | See the options below | $5–20/month, or PKR 1,500–4,000/month |

The domain is just the name. It does **not** host anything — the server does. Both are
needed.

**Recommended for this site: a small VPS.** The store keeps its data in a single file
(`store.db`) and stores uploaded product photos on disk. That works reliably on a normal
Linux server. It is the least fragile option and the cheapest.

*Why not the free tiers of Render / Railway / Fly.io?* Those platforms delete the
filesystem on every redeploy. Every order and every uploaded photo would vanish. They can
be used, but only with a paid persistent disk attached, which costs more than a small VPS
and needs extra configuration. **Not recommended for a site taking real orders.**

---

## 1. Set up the server

Buy a VPS running **Ubuntu 22.04 or 24.04**. DigitalOcean, Hetzner, Contabo and Vultr all
work. After it is created you get an IP address and root access.

Log in by SSH, then:

```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip nginx rsync curl

# A place for the site to live
mkdir -p /srv/cm-surgical
chown -R www-data:www-data /srv/cm-surgical
```

## 2. Put the site on the server

From your own computer, in the project folder:

```bash
./deploy/deploy.sh root@YOUR.SERVER.IP
```

This shows you exactly what will change, asks for confirmation, uploads the code, and
installs the service. It **never** overwrites `.env`, `store.db` or `backups/` on the
server, so you can run it again any time you update the site.

If you prefer to upload by hand instead:

```bash
rsync -av --exclude='.env' --exclude='store.db' --exclude='__pycache__' \
  ./ root@YOUR.SERVER.IP:/srv/cm-surgical/
```

Then on the server:

```bash
cd /srv/cm-surgical
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install gunicorn
```

## 3. Set the passwords — do not skip this

```bash
cd /srv/cm-surgical
cp .env.example .env
nano .env
```

Set at least these three:

```
SECRET_KEY=<a long random string>
ADMIN_PASSWORD=<a strong password>
APP_ENV=production
PORT=8000
```

Generate a secret key:

```bash
./venv/bin/python -c "import secrets; print(secrets.token_hex(32))"
```

Then load the demo database and set permissions:

```bash
./venv/bin/python -c "import app; app.init_db()"
chown -R www-data:www-data /srv/cm-surgical
chmod 600 /srv/cm-surgical/.env
```

> **The site refuses to start in production mode while `SECRET_KEY` or `ADMIN_PASSWORD`
> are still at their defaults.** That is intentional — it is a safety net against a
> publicly known password.

## 4. Make it a service that starts automatically

```bash
cp deploy/cm-surgical.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable cm-surgical
systemctl start cm-surgical
systemctl status cm-surgical
```

It is now running as an unprivileged user, restarts itself if it crashes, and comes back
after a reboot.

**Check it works:**

```bash
curl -I http://127.0.0.1:8000/
```

Should return `HTTP/1.1 200 OK`.

## 5. Put nginx in front

```bash
cp deploy/nginx.conf /etc/nginx/sites-available/cm-surgical
ln -s /etc/nginx/sites-available/cm-surgical /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
```

**Open `deploy/nginx.conf` and replace `example.com` with the real domain**, then:

```bash
nginx -t && systemctl reload nginx
```

## 6. Point the domain at the server

In the domain registrar's DNS settings, add:

| Type | Name | Value |
| --- | --- | --- |
| `A` | `@` | the server's IP address |
| `A` | `www` | the same IP address |

DNS can take up to an hour to spread. Check with:

```bash
dig +short example.com
```

It should print your server's IP.

## 7. Turn on HTTPS (the free certificate)

Once DNS is working:

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d example.com -d www.example.com
```

Answer `Y` to "Redirect all traffic to HTTPS". Certbot also arranges automatic renewal, so
the certificate never lapses.

**The site is now live.** Verify by visiting `https://example.com`.

---

## 8. Before taking real orders

Work through this list. Nothing here is optional.

- [ ] **Change the admin password** — log in at `/admin`, click **Password** in the left
      menu. Do not rely on `ADMIN_PASSWORD` in `.env` alone; also change it here.
- [ ] **Delete the demo products** (24 of them) and enter the real catalogue
- [ ] **Delete the demo coupons** `WELCOME10`, `BULK5000`, `FREESHIP`
- [ ] **Delete the 16 demo reviews** — fake reviews on a live site are a bad look
- [ ] **Replace the contact details** in `templates/base.html`: phone `0340-2719595`,
      address `271 Model Town Lahore`, email `cmsurgical512@gmail.com`
- [ ] **Check the business name** — the footer logo artwork still reads "CMD" while the
      site text reads "CM SURGICAL". Get a corrected logo file if that matters.
- [ ] **Set up daily backups** (section 9) and test that a backup restores
- [ ] **Place a real test order** on the live site and check it appears in `/admin/orders`
- [ ] **Delete that test order**

---

## 9. Backups on the server

Every order lives in one file. If the disk dies, the orders are gone unless there is a
copy.

```bash
crontab -e
```

Add:

```cron
# 3am every day, keep 14 days of backups
0 3 * * * /srv/cm-surgical/backup.sh >> /var/log/cm-backup.log 2>&1
```

**Then copy `backups/` off the server.** A backup on the same disk is not a backup. On a
VPS this is usually done with a provider snapshot (Hetzner and Contabo include these),
or an `rsync` to another machine or cloud storage. Do one of these.

**Test a restore before you need it:**

```bash
cp backups/<folder>/store.db /tmp/test.db
sqlite3 /tmp/test.db "select count(*) from orders;"
```

## 10. Day-to-day maintenance

```bash
systemctl status cm-surgical      # is it running?
systemctl restart cm-surgical     # restart after an update
journalctl -u cm-surgical -n 50   # read the error log
```

**To update the site** (new features, price fixes): change the code locally, then run
`./deploy/deploy.sh root@YOUR.SERVER.IP` again, then `systemctl restart cm-surgical`.
Existing orders and photos are untouched.

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `502 Bad Gateway` | The Flask service is down | `systemctl status cm-surgical`, then `journalctl -u cm-surgical -n 40` |
| Site starts then stops immediately | Default passwords in `.env` | Set `SECRET_KEY` and `ADMIN_PASSWORD` (section 3) |
| `Permission denied` writing to the database | Wrong owner | `chown -R www-data:www-data /srv/cm-surgical` |
| Product photos upload then disappear | Same as above | Same command; `store.db` and `static/img` must be writable |
| 404 on every page | nginx not proxying | Check `server_name` in `nginx.conf`, then `nginx -t && systemctl reload nginx` |
| "Refusing to start in production" | `.env` has the defaults | Fill in section 3 |
| Domain does not resolve | DNS not propagated yet | Wait up to an hour; `dig +short example.com` |
| Certificate error | Certbot not run yet, or DNS not propagated | Complete sections 6 and 7 in order |
| All orders disappeared after a redeploy | Hosting with an ephemeral disk | Move to a real VPS. `store.db` must live on a permanent disk |