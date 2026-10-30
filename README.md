<div align="center">

  <h1>🛒 GadgetFlow</h1>
  <p><b>Next-Gen E-Commerce Platform for Tech & Electronics</b></p>

  [![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
  [![Django](https://img.shields.io/badge/Django-4.2+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
  [![License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
  [![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen?style=for-the-badge)]()
  [![Deployment](https://img.shields.io/badge/Render-Deployed-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://farhan-gadgetflow.onrender.com/)

  <br />

  <a href="https://farhan-gadgetflow.onrender.com/"><b>🌐 Explore Live Storefront</b></a> •
  <a href="#-key-features"><b>Features</b></a> •
  <a href="#-tech-stack"><b>Tech Stack</b></a> •
  <a href="#-getting-started"><b>Local Setup</b></a>

</div>

---

## 📖 Overview

**GadgetFlow** is a production-ready, full-stack E-commerce platform built on Django's robust backend architecture and designed with a modern glassmorphic interface. It delivers a seamless online shopping experience with localized BDT (৳) pricing, dynamic catalog management, automated cart workflows, and interactive checkout systems.

---

## ✨ Key Features

- **📱 Mobile Universe & Specialized Zones:** Dynamic storefront segments for flagship smartphones, laptops, flash sales, and trending tech gadgetry.
- **⚡ Async Cart & Dynamic Badge Updates:** Instant product additions, live subtotal updates, and badge counters powered by lightweight asynchronous JavaScript.
- **🔍 Granular UI Filtering & Search:** Rapid categorization and real-time filtering across Audio, Wearables, Smartphones, Laptops, and Smart Accessories.
- **🎨 Glassmorphic Aesthetic:** Premium UI layout built with smooth custom drop-shadows, responsive grid components, and modern typography.
- **💳 Localized Checkout & Payment Manual Integration:** Native support for BDT (৳) transactions with manual Bkash settlement workflows and instructions.
- **⚙️ Multi-Environment Static & Media Handling:** Powered by WhiteNoise for production assets with zero-downtime static collection and isolated local media streaming.

---

## 🛠️ Tech Stack & Architecture

| Layer | Tools & Technologies |
| :--- | :--- |
| **Backend Core** | Python, Django Framework (MVC / MTV) |
| **Database Storage** | SQLite3 (Configured natively for rapid development & relational integrity) |
| **Frontend UI** | HTML5, CSS3 Grid/Flexbox, Vanilla JavaScript (ES6+) |
| **Static & Media Asset Delivery** | WhiteNoise Middleware, Native Django Media Local Stream |
| **Design & Typography** | Glassmorphism, Google Inter Fonts, FontAwesome 6 Icons |
| **Production Deployment** | Render Cloud Platform Hosting Engine |

---

## 📁 Repository Directory Structure

```text
E-commerce/
├── 📁 djangoProject13/       # Main Django Project Configuration Modules
│   ├── settings.py           # Core Application Settings
│   ├── development.py        # Local Media/Development Settings Overrides
│   └── urls.py               # Root URL Routing Engine
├── 📁 shop/                  # Primary Application Domain
│   ├── 📁 models/            # Relational Data Schema Models (Products, Orders, Categories)
│   ├── 📁 views/             # Core Business Logic & API Handlers
│   ├── 📁 templates/         # Dynamic Django HTML Layout Templates
│   └── urls.py               # App-level Route Mappings
├── 📁 media/                 # Dynamic User & Staff Uploaded Graphics
├── 📁 static/                # Static CSS, JavaScript, and UI Assets
├── db.sqlite3                # Local Relational Asset Database
├── manage.py                 # Django Execution CLI Executable
├── PREMIUM_STOREFRONT.md     # Storefront, Coupon, and Email Alert Guidelines
├── INFORMATION_SUPPORT.md    # Documentation for Support Pages & Legal Policies
└── requirements.txt          # Frozen Production Dependency Manifest
