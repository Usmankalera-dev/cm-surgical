# How to open this website

It takes about 2 minutes. No technical knowledge needed.

---

## On a Mac

1. Double-click `CM-SURGICAL-website.zip` to unzip it.
2. Open the folder `CM-SURGICAL-website`.
3. **Right-click** `start.sh` → **Open**.
   *(If that option is missing, right-click `start.sh` → `bash start.sh`.)*
4. A Terminal window opens and text scrolls past. **This is normal.**
5. Your browser opens the site automatically at **http://localhost:8000**

**To close the site:** click the Terminal window and press `Control + C`.

> If macOS says "Python is not installed", click **OK** when it offers to install the
> developer tools. That prompt is normal and takes a minute or two.

---

## On a Windows PC

1. Right-click `CM-SURGICAL-website.zip` → **Extract All** (do not open the zip directly).
2. Open the `CM-SURGICAL-website` folder.
3. **Double-click `start.bat`.**
4. A black window opens and text scrolls past. **This is normal.**
5. Your browser opens the site automatically at **http://localhost:8000**

**To close the site:** click the black window and press `Control + C`.

> First run takes an extra minute while Python downloads a few small packages.
> That only happens once. Every other start is quick.
>
> If Windows shows a blue "Windows protected your PC" message, click
> **More info** → **Run anyway**. It is safe — it is just a file from a USB stick
> that has no publisher signature.

---

## What to look at

| Page | Address |
| --- | --- |
| **Home** | http://localhost:8000 |
| **Shop** | http://localhost:8000/shop |
| **Cart** | http://localhost:8000/cart |
| **Admin panel** | http://localhost:8000/admin — password `admin123` |

**After logging in to the admin panel**, the left menu lets you change products, prices,
orders, coupons, reviews and messages — and change the admin password.

---

## Things to know

- **Leave the Terminal/black window open** while using the site. Closing it stops the site.
- This works with **no internet connection** once the first run has finished.
- Everything is stored in one file, `store.db`. Copy the whole folder to back it up.
- To test it out later, just do step 3 again. Nothing is lost.

**Do not** rename files or folders inside `CM-SURGICAL-website`. The site looks for them
by their exact names.