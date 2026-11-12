# 日本代購・集運網站（daigou）

Japan buying-agent and package-forwarding site for Taiwanese customers, modeled on the features of doso.net. Flask + SQLite, no front-end build step.

## Run it

```bash
cd daigou
pip install -r requirements.txt
python app.py            # http://127.0.0.1:5001
python -m pytest -q tests
```

The first run creates `data/site.db` and an admin account. Set these for production:

| Variable | Purpose | Default |
| --- | --- | --- |
| `SECRET_KEY` | session signing | `dev-change-me` (**must change**) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | first admin | `admin@example.com` / `admin1234` |
| `SITE_NAME` / `SITE_TAGLINE` | brand | `日貨通 JPGO` |
| `SUPPORT_EMAIL` | footer contact | `service@example.com` |
| `DATABASE` | SQLite path | `data/site.db` |

Production: `gunicorn -w 2 -b 0.0.0.0:8000 app:app`

## Feature breakdown (reference analysis → this build)

| Area | doso.net | This build |
| --- | --- | --- |
| Home | hero, app download, announcements, 9 feature cards, fee calculator, 4-column footer | hero + 4-step flow, announcements, 6 feature cards, calculator, FAQ, footer |
| Help center | VitePress docs, left category sidebar, prev/next | `/help/<slug>`, categories in sidebar, prev/next, FAQ, editable in admin |
| Fee calculator | `POST calculateShippingCosts?weight=` | `GET /api/shipping-fee?weight=` + rate table at `/calculator` |
| Purchasing | paste link / in-store buying / pre-orders, no fee | purchase requests (online / in store), statuses 待採購 → 已採購 → 已入庫 |
| Forwarding | dedicated warehouse address, inbound notice | member code + warehouse address, parcel pre-registration, admin check-in by weight |
| Consolidated shipping | select parcels → address → ship | select in-stock parcels → admin weighs → shipping bill → pay → tracking number |
| Payments | TWD/JPY top-up, product bills 72 h, shipping bills 48 h, credit limit | same rules: wallet, top-up review, pay bills from balance, credit limit |
| Admin | (closed system) | purchases, parcels, shipments, top-ups, members, content, rates / exchange rate / bank accounts |

Measured shipping prices from the reference (TWD, air, duty included): 1 kg 290, 2 kg 570, 3 kg 830, 4 kg 1070, 5 kg 1290, 10 kg 2300, 30 kg 5850, 100 kg 18000; partial kilograms round up. The default table in `pricing.py` approximates this. **Change it to your own contracted rates** under Admin > System settings.

## Before launch

- The terms, privacy policy, company details, warehouse address and bank accounts are **placeholders** (in `seed.py` and Admin > Settings). Have a lawyer review the terms.
- Not built yet: online card payment (ECPay / NewebPay), email notifications, EZ WAY real-name verification, sea freight, product catalog / pre-order catalog, mobile app.
