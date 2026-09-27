# ☕ Café Accounting & POS

A practical café management and accounting system designed to keep daily café operations simple, clear, and easy to monitor.

The system handles **sales, purchases, inventory, ready-to-sell products, reports, and remote activity monitoring through IRC**.

---

## 🇮🇷 فارسی

یک سیستم مدیریت و حسابداری کافه که برای ساده‌تر کردن کارهای روزمره کافه طراحی شده.

با این برنامه می‌توان **خرید، فروش، انبار، محصولات آماده فروش، قیمت‌ها و گزارش‌ها** را مدیریت کرد و اتفاقات مهم سیستم را از طریق **IRC** به‌صورت ریموت مشاهده کرد.

### امکانات اصلی

* 🛒 **خرید** — ثبت محصولات خریداری‌شده و هزینه آن‌ها
* 💰 **فروش** — ثبت سریع فروش و مدیریت تراکنش‌ها
* 📦 **انبار** — مشاهده موجودی و تغییرات آن
* 🏪 **ویترین / آماده فروش** — مدیریت محصولاتی که آماده فروش هستند
* 🏷️ **محصولات** — کد اختصاصی، دسته‌بندی، واحد، قیمت خرید و قیمت فروش
* 💵 **قیمت تمام‌شده و قیمت فروش** — برای بررسی بهتر سود و عملکرد
* 📊 **گزارش‌ها** — مشاهده اطلاعات فروش، خرید و عملکرد سیستم
* 🔎 **جستجوی سریع** — پیدا کردن محصولات بدون دردسر
* ⚠️ **هشدار موجودی** — اطلاع از محصولاتی که موجودی کمی دارند
* 📝 **تاریخچه فعالیت‌ها** — ثبت و پیگیری اتفاقات مهم سیستم
* 📖 **راهنمای داخلی** — آموزش قدم‌به‌قدم تمام بخش‌های برنامه
* 🌐 **نظارت از راه دور با IRC** — ارسال گزارش‌ها و رویدادهای مهم به کانال مشخص IRC
* 📡 **گزارش فروش از راه دور** — صاحب کافه می‌تواند گزارش فروش را از طریق IRC مشاهده کند
* 📥 **گزارش خرید از راه دور** — خریدهای ثبت‌شده قابل مشاهده از طریق IRC هستند
* 📦 **گزارش تغییرات انبار** — تغییرات مهم موجودی نیز قابل گزارش هستند
* 🔔 **گزارش رویدادهای مهم** — اتفاقات مهم سیستم می‌توانند به کانال IRC ارسال شوند
* 🖥️ **چندسکویی** — طراحی با هدف اجرا روی Windows و Linux

### 📡 Remote Monitoring

یکی از قابلیت‌های مهم پروژه، اتصال سیستم به **IRC** است.

برنامه می‌تواند اطلاعات و گزارش‌های مهم را به یک کانال مشخص IRC ارسال کند تا صاحب کافه بتواند بدون حضور مستقیم در محل، فعالیت‌های سیستم را مشاهده کند.

برای مثال:

```text
[SALE]
Product: Omelette
Quantity: 2
Total: 7,000 AMD

[PURCHASE]
Product: Eggs
Quantity: 30
Cost: 9,000 AMD

[INVENTORY]
Beer stock changed: 20 → 17
```

هدف این بخش، **نظارت و اطلاع‌رسانی از راه دور** است، نه پیچیده‌تر کردن کار کاربر داخل کافه.

---

## 🇬🇧 English

A practical café management and accounting system designed to make daily café operations simple and easy to monitor.

The system handles **sales, purchases, inventory, ready-to-sell products, pricing, reports, and remote activity monitoring through IRC**.

### Main Features

* 🛒 **Purchases** — record purchased products and their costs
* 💰 **Sales** — quickly record sales and transactions
* 📦 **Inventory** — track current stock and stock changes
* 🏪 **Ready-to-Sell / Display** — manage products prepared for sale
* 🏷️ **Products** — unique product codes, categories, units, purchase costs and selling prices
* 💵 **Cost & Selling Price** — keep purchase cost and customer price separate
* 📊 **Reports** — sales, purchases and operational reports
* 🔎 **Fast Search** — quickly find products
* ⚠️ **Low Stock Alerts** — identify products that need restocking
* 📝 **Activity History** — keep track of important system events
* 📖 **Built-in Guide** — step-by-step explanations for users
* 🌐 **Remote Monitoring via IRC** — send important reports and events to a configured IRC channel
* 📡 **Remote Sales Reports** — monitor sales remotely through IRC
* 📥 **Remote Purchase Reports** — monitor recorded purchases through IRC
* 📦 **Inventory Event Reports** — monitor important stock changes
* 🔔 **Event Notifications** — receive important system events through IRC
* 🖥️ **Cross-platform design** — intended to support Windows and Linux

### 📡 Remote Monitoring

A key feature of the project is its **IRC integration**.

The application can send important reports and system events to a configured IRC channel, allowing the café owner to monitor activity remotely without being physically present at the café.

Example:

```text
[SALE]
Product: Omelette
Quantity: 2
Total: 7,000 AMD

[PURCHASE]
Product: Eggs
Quantity: 30
Cost: 9,000 AMD

[INVENTORY]
Beer stock changed: 20 → 17
```

The purpose of IRC integration is to provide **simple remote visibility and notifications** without making the café employee's workflow more complicated.

---

## 🇦🇲 Հայերեն

Սրճարանի կառավարման և հաշվապահական համակարգ, որը նախատեսված է ամենօրյա աշխատանքը հնարավորինս պարզ և վերահսկելի դարձնելու համար։

Համակարգը ներառում է **վաճառքների, գնումների, պահեստի, վաճառքի պատրաստ ապրանքների, գների, հաշվետվությունների և IRC-ի միջոցով հեռավար վերահսկման** հնարավորություններ։

### Հիմնական հնարավորություններ

* 🛒 **Գնումներ** — գնված ապրանքների և դրանց արժեքի գրանցում
* 💰 **Վաճառքներ** — վաճառքների և գործարքների արագ գրանցում
* 📦 **Պահեստ** — առկա ապրանքների և պահեստի փոփոխությունների վերահսկում
* 🏪 **Վաճառքի պատրաստ / ցուցադրվող ապրանքներ**
* 🏷️ **Ապրանքներ** — անհատական կոդ, կատեգորիա, չափման միավոր, գնման և վաճառքի գին
* 💵 **Ինքնարժեք և վաճառքի գին**
* 📊 **Հաշվետվություններ** — վաճառքների, գնումների և աշխատանքի վերաբերյալ
* 🔎 **Արագ որոնում**
* ⚠️ **Պահեստի ցածր մնացորդի ծանուցումներ**
* 📝 **Գործողությունների պատմություն**
* 📖 **Ներկառուցված քայլ առ քայլ ուղեցույց**
* 🌐 **Հեռավար վերահսկում IRC-ի միջոցով**
* 📡 **Վաճառքների հեռավար հաշվետվություններ**
* 📥 **Գնումների հեռավար հաշվետվություններ**
* 📦 **Պահեստի փոփոխությունների հաշվետվություններ**
* 🔔 **Կարևոր իրադարձությունների ծանուցումներ**
* 🖥️ **Բազմահարթակ նախագծում** — Windows և Linux

### 📡 Հեռավար վերահսկում IRC-ի միջոցով

Նախագծի կարևոր հնարավորություններից մեկը **IRC ինտեգրումն** է։

Ծրագիրը կարող է վաճառքների, գնումների, պահեստի փոփոխությունների և այլ կարևոր իրադարձությունների վերաբերյալ տեղեկատվությունը ուղարկել նախապես սահմանված IRC ալիք։

Այս կերպ սրճարանի սեփականատերը կարող է **հեռավար հետևել համակարգում տեղի ունեցող կարևոր գործողություններին**՝ առանց սրճարանում ֆիզիկապես գտնվելու։

---

# 📸 Screenshots
![PATOGH Cafe Accounting System](https://raw.githubusercontent.com/AdolfMacro/patogh-cafe-accounting-system/main/screenshots/paSC1.png)

![PATOGH Screenshot 2](https://raw.githubusercontent.com/AdolfMacro/patogh-cafe-accounting-system/main/screenshots/paSC2.png)

![PATOGH Screenshot 3](https://raw.githubusercontent.com/AdolfMacro/patogh-cafe-accounting-system/main/screenshots/paSC3.png)

![PATOGH Screenshot 4](https://raw.githubusercontent.com/AdolfMacro/patogh-cafe-accounting-system/main/screenshots/paSC4.png)



---

## 🚧 Project Status

This project is currently under active development.
