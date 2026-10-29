# 🛒 GadgetFlow | Tech Hub E-commerce Platform

GadgetFlow is a fully functional, production-ready full-stack E-commerce platform built using modern web layouts and a robust Python backend architecture. Designed with a sleek user experience, the system enables dynamic product curation, localized currency listings (BDT ৳), interactive shopping workflows, and highly granular category cataloging.

For the current premium storefront, local startup, coupon rules, stock-alert email setup, data-preservation notes and verified behavior, see [PREMIUM_STOREFRONT.md](PREMIUM_STOREFRONT.md).

For the English-only information/support pages, draft publishing, contact messages, private order tracking and missing business setup, see [INFORMATION_SUPPORT.md](INFORMATION_SUPPORT.md). Existing Bangla content is retained in staff-editable database fields for future use.

Static assets are served by WhiteNoise with `DEBUG=False`. Run `manage.py collectstatic --noinput`
with the project interpreter before starting the server and after CSS/JS changes in this mode;
restart the server after collection. Include this command in any future deployment build.
Keep `DJANGO_DEBUG=0` on public hosts. Local development may explicitly use `DJANGO_DEBUG=1`
to serve source assets through Django's development server. Uploads remain separate from static assets.

`manage.py runserver` now selects `djangoProject13.development` by default, which
serves existing uploads from `media/` to loopback clients with debug pages still
disabled. PyCharm's Django facet uses the same local settings. If an environment
explicitly selects another settings module, use
`manage.py runserver 127.0.0.1:8000 --settings=djangoProject13.development` locally.
Production WSGI/ASGI retain `djangoProject13.settings` and do not serve uploads
through Django with debug off. See [LOCAL_MEDIA.md](LOCAL_MEDIA.md) for the verified
failure, routing fix and upload tests.

🔗 **Live Deployment:** [Explore GadgetFlow on Render](https://farhan-gadgetflow.onrender.com/)

---

## 🚀 Key Features

* **Advanced Catalog System:** Dynamically rendered product segments including dedicated zones like the "Mobile Universe", Flash Sales, and Laptops.
* **Granular UI Filtering:** Clean, async-ready categorization for rapid product navigation across Phones, Laptops, Audio, Wearables, and Smart Tech.
* **Django Data Architecture:** Leverages relational integrity mappings for dynamic item generation, image pathways, dynamic price updates, and inventory state persistence.
* **Shopping Cart Ecosystem:** Responsive asynchronous state configurations handling instant "Add to Cart" interactions and real-time navigation badge counters.
* **Premium Glassmorphic UI:** Built with precision components, smooth drop shadows, responsive visual hover cards, and premium responsive breakpoints.

---

## 🛠️ Deep Tech Stack & Architecture

| Layer | Tools & Technologies |
| :--- | :--- |
| **Backend Framework** | Python & Django (Routing, Views, Admin Panels, Template Engine) |
| **Database Model** | SQLite3 (Configured natively for rapid development datasets) |
| **Frontend Layout** | Semantic HTML5, Modular CSS3 (Custom Grid/Flex properties), Embedded JavaScript |
| **Typography & Assets** | Google Inter Fonts Integration, FontAwesome Vector Layout Engines |
| **Hosting & Cloud Deploy** | Render Cloud Platform Hosting Engine |

---

## 📦 Project Directory Architecture

```text
E-commerce/
│
├── djangoProject13/    # Main Core Django Project Configurations 
├── shop/               # Application Logic Module (Models, Views, URLs)
├── media/              # Dynamic User Uploaded Hardware/Product Graphics
├── db.sqlite3          # Persistent SQL Asset Storage Engine
├── manage.py           # Native Django Execution & Management Script
└── requirements.txt    # Frozen Python Dependencies & Package Manifests
