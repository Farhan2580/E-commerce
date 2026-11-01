<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=32&pause=1000&color=6366F1&center=true&vCenter=true&width=600&lines=🛒+GadgetFlow;Next-Gen+E-Commerce;Built+with+Django+%26+Love" alt="Typing SVG" />

<br/>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Django-4.2+-092E20?style=for-the-badge&logo=django&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/Render-Deployed-46E3B7?style=for-the-badge&logo=render&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" />
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/Farhan2580/E-commerce?style=social" />
  <img src="https://img.shields.io/github/forks/Farhan2580/E-commerce?style=social" />
  <img src="https://img.shields.io/github/watchers/Farhan2580/E-commerce?style=social" />
</p>

<br/>

> **🌐 Production-ready full-stack E-Commerce platform for tech & electronics — built with Django, glassmorphic UI, and BDT (৳) localized payments.**

<br/>

<a href="https://farhan-gadgetflow.onrender.com/">
  <img src="https://img.shields.io/badge/🌐 Live Demo-Visit GadgetFlow-6366F1?style=for-the-badge&labelColor=1e1e2e" />
</a>

</div>

---

## 📸 Preview

<div align="center">

```
╔══════════════════════════════════════════════════════╗
║          🛒  G A D G E T F L O W                    ║
║    ─────────────────────────────────────────         ║
║    📱 Smartphones  💻 Laptops  🎧 Audio  ⌚ Wearables ║
║    ─────────────────────────────────────────         ║
║      Search · Filter · Cart · Checkout · Pay         ║
╚══════════════════════════════════════════════════════╝
```

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🛍️ Shopping Experience
- 📱 **Mobile Universe** — Flagship smartphones zone
- 💻 **Laptop Lounge** — Premium laptop section
- ⚡ **Flash Sales** — Real-time deal countdowns
- 🔥 **Trending Zone** — Hot & popular gadgets

</td>
<td width="50%">

### ⚙️ Technical Features
- 🛒 **Async Cart** — Live badge & subtotal updates
- 🔍 **Smart Filtering** — Category-based real-time search
- 💳 **BDT Payment** — Bkash & local checkout support
- 🎨 **Glassmorphic UI** — Modern premium aesthetic

</td>
</tr>
</table>

---

## 🛠️ Tech Stack

<div align="center">

| Layer | Technology |
|-------|-----------|
| 🔙 **Backend** | Python · Django (MTV Architecture) |
| 🗄️ **Database** | SQLite3 |
| 🎨 **Frontend** | HTML5 · CSS3 Grid/Flexbox · Vanilla JS ES6+ |
| 📦 **Static Files** | WhiteNoise Middleware |
| 🖋️ **Design** | Glassmorphism · Google Inter · FontAwesome 6 |
| ☁️ **Deployment** | Render Cloud Platform |

</div>

---

## 📁 Project Structure

```
🗂️ E-commerce/
├── 📁 djangoProject13/       # Django core config
│   ├── settings.py           # App settings
│   ├── development.py        # Dev overrides
│   └── urls.py               # Root URL routing
│
├── 📁 shop/                  # Main app
│   ├── 📁 models/            # Product, Order, Category schemas
│   ├── 📁 views/             # Business logic & API handlers
│   ├── 📁 templates/         # Django HTML templates
│   └── urls.py               # App-level routes
│
├── 📁 media/                 # Uploaded images
├── 📁 static/                # CSS, JS, assets
├── manage.py                 # Django CLI
└── requirements.txt          # Python dependencies
```

---

## 🚀 Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/Farhan2580/E-commerce.git
cd E-commerce

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup environment variables
cp .env.example .env
# Edit .env with your config

# 5. Run migrations
python manage.py migrate

# 6. Start the server
python manage.py runserver
```

> 🌐 Open **http://127.0.0.1:8000** in your browser

---

## 🌍 Deployment

This project is deployed on **[Render](https://render.com/)** using:

- `render-build.sh` — Build script for production
- `render-start.sh` — Server start script
- **WhiteNoise** — Static file serving in production

[![Deploy on Render](https://render.com/images/deploy-to-render-button.svg)](https://farhan-gadgetflow.onrender.com/)

---

## 📦 Category Zones

```
🛍️ GadgetFlow Storefront
│
├── 📱 Smartphones      → Flagship & Budget phones
├── 💻 Laptops          → Gaming, Ultrabooks, Business
├── 🎧 Audio            → Earbuds, Headphones, Speakers
├── ⌚ Wearables        → Smartwatches, Fitness Bands
└── 🔌 Accessories      → Cables, Cases, Chargers
```

---

## 💳 Payment

GadgetFlow supports **BDT (৳) localized payments** with:

- 📲 **Bkash** manual settlement workflow
- 💰 Full BDT pricing across all products
- 🧾 Order summary & checkout confirmation

---

## 🤝 Contributing

Contributions are welcome! Feel free to:

1. 🍴 Fork the repository
2. 🌿 Create a feature branch (`git checkout -b feature/amazing-feature`)
3. 💾 Commit your changes (`git commit -m 'Add amazing feature'`)
4. 📤 Push to branch (`git push origin feature/amazing-feature`)
5. 🔁 Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

---

<div align="center">

**Made with ❤️ by [Farhan](https://github.com/Farhan2580)**

<br/>

<a href="https://farhan-gadgetflow.onrender.com/">
  <img src="https://img.shields.io/badge/🚀 Visit Live Site-GadgetFlow-6366F1?style=for-the-badge" />
</a>

<br/><br/>

⭐ **Star this repo if you found it helpful!** ⭐

</div>
