# رأی‌گیری آزمایشی — FastAPI، Docker Compose و Nginx

وب‌اپلیکیشن فارسی و راست‌چین برای نظرسنجی آزمایشی. FastAPI صفحه و API را سرو می‌کند، رأی‌ها در SQLite روی volume پایدار Docker نگه‌داری می‌شوند، Nginx روی خود VPS درخواست‌ها را به کانتینر FastAPI می‌فرستد و Certbot گواهی HTTPS را از Let’s Encrypt می‌گیرد و تمدید می‌کند.

## راه‌اندازی از ورود به VPS

دستورها برای Ubuntu هستند. اگر توزیع دیگری دارید، نام بسته‌های Docker ممکن است فرق کند. ابتدا از کامپیوتر خود با SSH به سرور وصل شوید:

```bash
ssh USER@IP_VPS
```

### ۱. DNS و فایروال

در پنل مدیریت دامنه، رکورد `A` با نام `www` را روی IPv4 سرور تنظیم کنید. اگر رکورد `AAAA` برای `www` دارید، فقط وقتی نگهش دارید که IPv6 سرور واقعاً تنظیم و قابل دسترس باشد؛ در غیر این صورت حذفش کنید.

اگر UFW را فعال می‌کنید، ابتدا دسترسی SSH و سپس وب را مجاز کنید تا اتصال SSH قطع نشود:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

اگر ارائه‌دهندهٔ VPS فایروال جداگانه‌ای دارد، TCP پورت‌های `80` و `443` را آنجا نیز باز کنید.

### ۲. نصب ابزارها

در Ubuntu می‌توانید Nginx، Certbot و ابزارهای لازم را نصب کنید:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx git
```

اگر Docker و Compose هنوز نصب نیستند، در Ubuntu این بسته‌ها را نیز نصب کنید:

```bash
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
```

بررسی نصب:

```bash
sudo docker --version
sudo docker compose version
sudo systemctl status nginx --no-pager
```

### ۳. دریافت پروژه و راه‌اندازی FastAPI

```bash
git clone -b arena/430a1a60-test-site https://github.com/MAfzalirad/test_site.git poll-site
cd poll-site
sudo docker compose up -d --build
sudo docker compose ps
```

FastAPI فقط روی `127.0.0.1:8000` در دسترس میزبان است و مستقیماً روی اینترنت منتشر نمی‌شود. سلامت آن را بررسی کنید:

```bash
curl http://127.0.0.1:8000/healthz
```

باید پاسخی شبیه `{"status":"ok"}` ببینید.

### ۴. اتصال Nginx به FastAPI

فایل تنظیمات آمادهٔ پروژه را در محل Nginx کپی و فعال کنید:

```bash
sudo cp nginx/phanacacoffee.conf /etc/nginx/sites-available/phanacacoffee
sudo ln -s /etc/nginx/sites-available/phanacacoffee /etc/nginx/sites-enabled/phanacacoffee
sudo nginx -t
sudo systemctl reload nginx
```

اگر دستور `ln` گفت فایل از قبل وجود دارد، لینک قبلاً فعال شده است؛ ادامه دهید.

### ۵. دریافت و فعال‌کردن HTTPS

وقتی DNS به IP سرور اشاره می‌کند و پورت 80 از اینترنت قابل دسترس است، اجرا کنید:

```bash
sudo certbot --nginx -d www.phanacacoffee.ir
```

ایمیل را وارد کنید و مراحل را تأیید کنید. Certbot گواهی را می‌گیرد، Nginx را برای HTTPS تنظیم می‌کند و تمدید خودکار را پیکربندی می‌کند. سپس باز کنید:

```text
https://www.phanacacoffee.ir
```

تمدید خودکار را می‌توانید آزمایش کنید:

```bash
sudo certbot renew --dry-run
```

## عیب‌یابی

```bash
sudo nginx -t
sudo systemctl status nginx --no-pager
sudo journalctl -u nginx -n 100 --no-pager
sudo docker compose logs --tail=100 app
sudo certbot certificates
```

اگر Certbot نتوانست گواهی بگیرد، بررسی کنید رکورد `A` به IP همین VPS اشاره کند، رکورد `AAAA` نامعتبر نداشته باشید و پورت 80 در فایروال سیستم و پنل VPS باز باشد. گواهی برای `www.phanacacoffee.ir` صادر می‌شود؛ اگر دامنهٔ بدون `www` هم لازم دارید، باید DNS و تنظیم Nginx/Certbot را برای آن دامنه نیز اضافه کنید.

## به‌روزرسانی و داده‌ها

برای دریافت تغییرات و بازسازی برنامه:

```bash
cd poll-site
git pull
sudo docker compose up -d --build
```

برای دیدن وضعیت و گزارش‌ها:

```bash
sudo docker compose ps
sudo docker compose logs -f app
```

داده‌ها در volume به نام `poll_data` نگه‌داری می‌شوند و با `sudo docker compose down` پاک نمی‌شوند. از `sudo docker compose down -v` استفاده نکنید، مگر اینکه عمداً بخواهید داده‌های رأی‌گیری را حذف کنید.

## اجرای محلی بدون Docker

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
DATABASE_PATH=./poll.sqlite3 uvicorn app.main:app --reload
```

سپس `http://127.0.0.1:8000` را باز کنید.

## نکته دربارهٔ رأی‌ها

رأی‌ها در سرور ذخیره می‌شوند و نتیجه برای همهٔ بازدیدکنندگان مشترک است. جلوگیری از رأی تکراری با کوکی مرورگر انجام می‌شود؛ این احراز هویت نیست و با پاک‌کردن کوکی یا استفاده از دستگاه دیگر قابل دورزدن است. برای نظرسنجی رسمی یا حساس، احراز هویت و محدودسازی درخواست لازم است. این برنامه IP کاربران را ذخیره نمی‌کند.
