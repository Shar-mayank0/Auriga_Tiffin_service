# Auriga Tiffin Service — Project Master Plan

> **Status:** Backend Initialization — In Progress
> **Stack finalized. Structure created. Models next.**
> This document is the single source of truth for all architectural and structural decisions.

---

## 1. Final Stack Decision

| Layer | Technology | Reason |
|---|---|---|
| Backend | Django + Django REST Framework | Python comfort, ORM, Admin panel, REST APIs |
| Owner UI | Django Admin (customized) | Internal tool, no frontend overhead |
| Customer UI | React (Vite) | Comfortable, clean SPA, connects via DRF APIs |
| Landing Page | React (same app, separate route `/`) | Static page, reuses the same React project |
| Database | SQLite | Sufficient for scale, zero config, easy Postgres migration later |
| Auth | Django built-in + djangorestframework-simplejwt | Staff = owner, regular User = customer |
| Package Manager | uv | Fast, modern Python package manager |

---

## 2. System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        Browser Clients                       │
│                                                              │
│   ┌─────────────────────────┐   ┌──────────────────────────┐ │
│   │     React App (Vite)    │   │      Django Admin        │ │
│   │  /               Landing│   │      /admin/             │ │
│   │  /login          Page   │   │   Owner manages:         │ │
│   │  /register              │   │   - customers            │ │
│   │  /dashboard             │   │   - plans                │ │
│   │  /subscribe             │   │   - billing              │ │
│   │  /pause                 │   │   - pause overrides      │ │
│   │  /billing               │   │   - imports              │ │
│   └───────────┬─────────────┘   └──────────────────────────┘ │
└───────────────┼──────────────────────────────────────────────┘
                │ REST API (JSON)
                │
┌───────────────▼──────────────────────────────────────────────┐
│                  Django REST Framework (API Layer)           │
│                                                              │
│   /api/auth/            → register, login, logout, token     │
│   /api/customers/       → profile, status                    │
│   /api/plans/           → list available plans               │
│   /api/subscriptions/   → subscribe, transfer, view          │
│   /api/pauses/          → create pause, resume, view         │
│   /api/billing/         → view own bills                     │
│   /api/clock/           → [T1] advance simulation date       │
│   /api/outbox/          → [T1] read notification outbox      │
│   /api/import/          → [T4] bulk customer import          │
└───────────────┬──────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────┐
│                    Service / Business Layer                   │
│                                                              │
│  WeekdayCalculator  BillingEngine    PauseService            │
│  CustomerService    NotificationService  (T1)                │
│  TransferService (T6)                ImportService (T4)      │
└───────────────┬──────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────┐
│                    Django ORM  +  SQLite                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Actor Responsibilities (Clear Boundary)

| Action | Customer (React App) | Owner (Django Admin) |
|---|---|---|
| Register | ✅ Self-serve via React form | ✅ Can create manually |
| Login | ✅ JWT token via API | ✅ Staff login via /admin/ |
| Choose a plan | ✅ From plans listed by API | ✅ Can assign/override |
| Pause own service | ✅ With date picker | ✅ Can pause any customer |
| Resume own service | ✅ One button | ✅ Can resume any customer |
| View own bills | ✅ Read-only | ✅ Full billing access |
| Generate month-end bills | ❌ | ✅ Owner only |
| Manage plans & prices | ❌ | ✅ Owner only |
| View all customers | ❌ | ✅ Owner only |
| Override any pause | ❌ | ✅ Owner only |
| Transfer subscription [T6] | ❌ | ✅ Owner only |
| Bulk import customers [T4] | ❌ | ✅ Owner only |
| Advance clock / view outbox [T1] | ❌ | ✅ Owner / grader only |

---

## 4. Challenge Twists

Three additional requirements layered on top of the core problem.
Each one is documented here with its architectural impact.

---

### T1 — Notification Outbox (Integrate)

> "Each morning, notify customers due a delivery today (active, a weekday, not paused)
>  via the Notification Service. Graded via GET /outbox after POST /clock."

**What this means:**
- The grader controls time. `POST /clock` advances the simulation date — your system must
  NOT use `datetime.today()` anywhere in eligibility logic.
- On each clock advance, the system checks who gets a delivery that day and writes to an
  outbox table. The grader then reads `GET /outbox` to verify.
- `POST /clock` must be **idempotent** — calling it twice for the same date must not
  duplicate outbox entries.

**New models:**
```
SystemClock
├── id            (single row, always id=1)
└── current_date  DateField   ← the system's "today"

OutboxEntry
├── customer       ForeignKey → Customer
├── delivery_date  DateField
├── message        TextField
└── created_at     DateTimeField
```

**New service:** `NotificationService`
```
get_eligible_customers(date)    → QuerySet[Customer]
  - active subscription on that date
  - date is a weekday
  - date is not within any PausePeriod for that subscription

dispatch(date)                  → List[OutboxEntry]
  - calls get_eligible_customers
  - writes OutboxEntry per customer (idempotent: skip if already exists)
```

**New endpoints:**
```
POST  /api/clock/     → { date: "YYYY-MM-DD" }  advances SystemClock, triggers dispatch()
GET   /api/outbox/    → list of OutboxEntry records (grader reads this)
```

---

### T6 — Mid-Cycle Subscription Transfer (Lifecycle)

> "Transfer a subscription to a new customer mid-cycle; the plan and cycle carry over,
>  billing splits by who was served."

**What this means:**
- A subscription can change hands mid-month. Customer A owns it for the first N days,
  Customer B owns it for the rest.
- **Critical:** `Subscription.customer` as a direct FK is now wrong. Ownership must be
  tracked as a history of periods.
- `BillingEngine` must split billing by ownership period — A's bill covers A's served
  days, B's bill covers B's served days.

**Model change — remove `Subscription.customer` FK, replace with:**
```
SubscriptionOwnershipPeriod
├── subscription  ForeignKey → Subscription
├── customer      ForeignKey → Customer
├── from_date     DateField
└── to_date       DateField (nullable = current active owner)
```

**Updated `Subscription` model (no customer FK):**
```
Subscription
├── plan          ForeignKey → Plan
├── start_date    DateField
├── end_date      DateField (nullable)
├── status        CharField  [ACTIVE | PAUSED | CANCELLED]
└── created_at    DateTimeField
```

**New service:** `TransferService`
```
transfer(subscription, new_customer, transfer_date)
  - validates new_customer exists and has no conflicting active subscription
  - closes current SubscriptionOwnershipPeriod (sets to_date = transfer_date - 1)
  - opens new SubscriptionOwnershipPeriod for new_customer from transfer_date
  - runs atomically (transaction)

get_owner_on_date(subscription, date) → Customer
  - returns the customer who owned the subscription on a given date
```

**Updated `BillingEngine`:**
- Must iterate ownership periods within the billing month
- Generate one `BillingRecord` per customer per ownership segment
- Each record only counts delivered weekdays within that customer's ownership window

**New endpoint:**
```
POST  /api/subscriptions/{id}/transfer/
  body: { new_customer_id, transfer_date }
```

---

### T4 — Messy Data Import (Messy Data)

> "Import a messy customer list (dup phones, mixed date formats, blanks)
>  into clean subscriptions with an { imported, deduped, rejected } report."

**What this means:**
- An endpoint accepts a raw list (JSON or CSV) and processes it row by row
- Deduplication key is `phone` (consistent with FR-1 — already the primary lookup key)
- Each row is independently validated; failures are collected, not fatal
- Response shape is fixed: `{ imported: N, deduped: N, rejected: [...] }`

**New service:** `ImportService`
```
normalize_date(raw_value)       → date | None
  - handles: "2024-01-15", "15/01/2024", "Jan 15 2024", "15-Jan-24", etc.

validate_row(row)               → { valid: bool, errors: List[str] }
  - checks: name not blank, phone not blank, parseable start_date
  - checks: plan_id exists if provided

deduplicate(rows)               → { unique: List, dupes: List }
  - groups by phone, keeps first occurrence, marks rest as deduped

run_import(raw_data)            → { imported: int, deduped: int, rejected: List[dict] }
  - parse → deduplicate → validate → create Customer + Subscription
  - rejected entries include: { row, reasons: [...] }
  - runs in a transaction per row (one bad row does not block others)
```

**New endpoint:**
```
POST  /api/import/customers/
  body: JSON array of raw customer rows
  response: { imported: N, deduped: N, rejected: [...] }
```

---

## 5. Data Model (Final — includes all twist changes)

### 5.1 Entity Map

```
User (Django built-in)
│
├── is_staff = True  → Owner  → accesses /admin/
└── is_staff = False → Customer → accesses React app

Customer
├── user          OneToOneField → User
├── name          CharField
├── phone         CharField (unique)  ← primary lookup key
├── address       TextField (optional at registration)
└── created_at    DateTimeField

Plan
├── id
├── name          CharField
├── monthly_price DecimalField
├── effective_from DateField    ← supports future price versioning
└── is_active     BooleanField

Subscription                    ← NO customer FK (ownership via period table)
├── plan          ForeignKey → Plan
├── start_date    DateField
├── end_date      DateField (nullable)
├── status        CharField  [ACTIVE | PAUSED | CANCELLED]
└── created_at    DateTimeField

SubscriptionOwnershipPeriod     ← NEW (T6)
├── subscription  ForeignKey → Subscription
├── customer      ForeignKey → Customer
├── from_date     DateField
└── to_date       DateField (nullable = current active owner)

PausePeriod
├── subscription  ForeignKey → Subscription
├── start_date    DateField
├── end_date      DateField (nullable)  ← open-ended pause if null
├── created_at    DateTimeField
└── resumed_at    DateTimeField (nullable)

BillingRecord
├── subscription  ForeignKey → Subscription
├── customer      ForeignKey → Customer  ← per ownership segment
├── billing_month DateField  (always first of month)
├── ownership_from DateField ← segment start within billing month
├── ownership_to   DateField ← segment end within billing month
├── total_weekdays_in_segment IntegerField
├── paused_weekdays           IntegerField
├── delivered_weekdays        IntegerField
├── daily_rate                DecimalField
├── amount_due                DecimalField
└── generated_at              DateTimeField

SystemClock                     ← NEW (T1)
├── id            (always 1 — single row)
└── current_date  DateField

OutboxEntry                     ← NEW (T1)
├── customer       ForeignKey → Customer
├── delivery_date  DateField
├── message        TextField
└── created_at     DateTimeField

AuditLog
├── event_type    CharField
│    [SUBSCRIBED | PAUSED | RESUMED | BILLED | CANCELLED | TRANSFERRED | IMPORTED | NOTIFIED]
├── entity_type   CharField
├── entity_id     IntegerField
├── notes         TextField
├── timestamp     DateTimeField
└── operator      ForeignKey → User (nullable)
```

### 5.2 Key Constraints

- `Customer.phone` → `unique=True` at DB level
- `SubscriptionOwnershipPeriod`: only one row per subscription may have `to_date = null`
- No two overlapping active `PausePeriod` rows for the same subscription
- `BillingRecord` unique on `(subscription, customer, billing_month)` — re-runnable
- `OutboxEntry` unique on `(customer, delivery_date)` — idempotent clock advances
- `SystemClock` always has exactly one row (id=1), created via data migration
- `PausePeriod.end_date` nullable = open-ended pause
- `Subscription.end_date` nullable = still active

---

## 6. Service Layer (Final)

> All live in `services/` — pure Python, zero Django view dependency. Fully unit-testable.

```
services/
│
├── weekday_calculator.py
│   get_weekdays_in_month(year, month)                    → List[date]
│   get_weekdays_in_range(start_date, end_date)           → List[date]
│   get_paused_weekdays(pause_periods, start, end)        → List[date]
│   get_delivered_weekdays(subscription, start, end)      → int
│
├── billing_engine.py
│   generate_bill(subscription, year, month)              → List[BillingRecord]
│     - fetches ownership periods for the month
│     - calls weekday_calculator per segment
│     - applies daily_rate = plan_price / total_weekdays_in_month
│     - applies amount_due = daily_rate × delivered_weekdays
│     - writes BillingRecord per segment (idempotent)
│
├── pause_service.py
│   create_pause(subscription, start_date, end_date)      → PausePeriod
│     - validates end_date >= start_date
│     - validates no overlap with existing active pauses
│     - updates subscription.status = PAUSED
│   resume_pause(subscription, resume_date)               → PausePeriod
│     - sets pause.end_date = resume_date
│     - sets pause.resumed_at = now()
│     - updates subscription.status = ACTIVE
│
├── customer_service.py
│   search_by_phone(partial_phone)                        → QuerySet[Customer]
│   get_customer_status(customer)                         → {status, active_pause, plan}
│
├── notification_service.py                               ← NEW (T1)
│   get_eligible_customers(date)                          → QuerySet[Customer]
│   dispatch(date)                                        → List[OutboxEntry]
│
├── transfer_service.py                                   ← NEW (T6)
│   transfer(subscription, new_customer, transfer_date)   → SubscriptionOwnershipPeriod
│   get_owner_on_date(subscription, date)                 → Customer
│
└── import_service.py                                     ← NEW (T4)
    normalize_date(raw_value)                             → date | None
    validate_row(row)                                     → {valid, errors}
    deduplicate(rows)                                     → {unique, dupes}
    run_import(raw_data)                                  → {imported, deduped, rejected}
```

---

## 7. API Endpoints (Final)

> All under `/api/`. Auth via JWT. Owner-only endpoints require `is_staff = True`.

```
AUTH
  POST   /api/auth/register/                  → create User + Customer
  POST   /api/auth/login/                     → return JWT access + refresh tokens
  POST   /api/auth/logout/                    → blacklist refresh token
  POST   /api/auth/token/refresh/             → get new access token

PLANS
  GET    /api/plans/                          → list active plans (public)

CUSTOMERS
  GET    /api/customers/me/                   → own profile + current status
  PATCH  /api/customers/me/                   → update address

SUBSCRIPTIONS
  POST   /api/subscriptions/                  → subscribe to a plan
  GET    /api/subscriptions/me/               → own subscription + ownership history
  POST   /api/subscriptions/{id}/transfer/   → [T6] transfer to new customer (owner only)

PAUSES
  POST   /api/pauses/                         → create a pause (own subscription)
  PATCH  /api/pauses/{id}/resume/             → resume a pause
  GET    /api/pauses/                         → own pause history

BILLING
  GET    /api/billing/                        → own billing records

CLOCK + OUTBOX (T1)
  POST   /api/clock/                          → advance simulation date, trigger notifications
  GET    /api/outbox/                         → list outbox entries (grader reads this)

IMPORT (T4)
  POST   /api/import/customers/               → bulk import, returns {imported, deduped, rejected}
```

---

## 8. Project File Structure

> **Platform note:** Windows users — use `New-Item` (PowerShell) or `echo.` (CMD) instead of `touch`.
> See Section 11 for Windows commands.

```
auriga-tiffin/                          ← monorepo root
│
├── pyproject.toml                      ← uv project config + dependencies
├── pytest.ini                          ← pytest + Django settings pointer
├── .gitignore
├── README.md
├── manage.py                           ← Django entry point
├── db.sqlite3                          ← created after first migration
│
├── config/                             ← Django project settings
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── customers/                          ← Customer profiles + auth extension
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                       (Customer — OneToOne → User)
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── plans/                              ← Tiffin plan definitions
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                       (Plan)
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── subscriptions/                      ← Subscription lifecycle + ownership + pauses
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                       (Subscription, SubscriptionOwnershipPeriod, PausePeriod)
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── billing/                            ← BillingRecord + generation
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                       (BillingRecord)
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── notifications/                      ← [T1] SystemClock + OutboxEntry
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                       (SystemClock, OutboxEntry)
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── importer/                           ← [T4] Bulk import endpoint
│   ├── migrations/
│   ├── __init__.py
│   ├── apps.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── audit/                              ← AuditLog + signals
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                       (AuditLog)
│   └── signals.py
│
├── services/                           ← Pure Python business logic (no Django views)
│   ├── __init__.py
│   ├── weekday_calculator.py
│   ├── billing_engine.py
│   ├── pause_service.py
│   ├── customer_service.py
│   ├── notification_service.py         ← NEW (T1)
│   ├── transfer_service.py             ← NEW (T6)
│   └── import_service.py              ← NEW (T4)
│
└── tests/
    ├── __init__.py
    ├── test_weekday_calculator.py
    ├── test_billing_engine.py
    ├── test_pause_service.py
    ├── test_notification_service.py    ← NEW (T1)
    ├── test_transfer_service.py        ← NEW (T6)
    ├── test_import_service.py         ← NEW (T4)
    └── test_api_endpoints.py
```

---

## 9. React App Structure (unchanged)

```
frontend/
├── package.json
├── vite.config.js
├── index.html
│
├── public/
│   └── favicon.ico
│
└── src/
    ├── main.jsx                        ← React entry point
    ├── App.jsx                         ← Router setup
    │
    ├── api/                            ← All API calls (Axios)
    │   ├── auth.js
    │   ├── plans.js
    │   ├── subscriptions.js
    │   ├── pauses.js
    │   └── billing.js
    │
    ├── context/
    │   └── AuthContext.jsx             ← JWT token, current user
    │
    ├── pages/
    │   ├── LandingPage.jsx
    │   ├── LoginPage.jsx
    │   ├── RegisterPage.jsx
    │   ├── DashboardPage.jsx
    │   ├── SubscribePage.jsx
    │   ├── PausePage.jsx
    │   └── BillingPage.jsx
    │
    ├── components/
    │   ├── Navbar.jsx
    │   ├── ProtectedRoute.jsx
    │   ├── StatusBadge.jsx
    │   ├── PlanCard.jsx
    │   ├── BillCard.jsx
    │   └── PauseForm.jsx
    │
    └── utils/
        └── dateHelpers.js
```

---

## 10. Development Order (Revised)

```
Phase 1 — Data Foundation
  [x] Set up Django project structure (done)
  [x] Create services/ folder (done)
  [ ] Write all models
        customers, plans, subscriptions (+ OwnershipPeriod), billing,
        notifications (SystemClock + OutboxEntry), audit
  [ ] Run initial migrations
  [ ] Register all models in Django Admin
  [ ] Seed: create SystemClock row (id=1), create 1-2 test Plans

Phase 2 — Business Logic (test-first where possible)
  [ ] WeekdayCalculator       — write → unit test
  [ ] BillingEngine           — write → unit test (ownership-period-aware from day 1)
  [ ] PauseService            — write → unit test
  [ ] NotificationService     — write → unit test  [T1]
  [ ] TransferService         — write → unit test  [T6]
  [ ] ImportService           — write → unit test  [T4]

Phase 3 — APIs
  [ ] Auth endpoints (register, login, logout, token refresh)
  [ ] Customer profile endpoints
  [ ] Plans list endpoint
  [ ] Subscription endpoints
  [ ] Pause / Resume endpoints
  [ ] Billing read endpoints
  [ ] POST /clock + GET /outbox   [T1]
  [ ] POST /subscriptions/{id}/transfer/  [T6]
  [ ] POST /import/customers/     [T4]

Phase 4 — Django Admin Customization
  [ ] Customer list: phone search + status filter
  [ ] Inline PausePeriod in Subscription admin
  [ ] Inline SubscriptionOwnershipPeriod in Subscription admin
  [ ] Custom action: Generate Bill for Month
  [ ] AuditLog read-only view
  [ ] Outbox / Clock admin view

Phase 5 — React App
  [ ] Vite setup + routing
  [ ] AuthContext + ProtectedRoute
  [ ] Landing Page
  [ ] Register + Login pages
  [ ] Dashboard page
  [ ] Subscribe flow
  [ ] Pause / Resume flow
  [ ] Billing history page
```

---

## 11. Windows Commands (PowerShell)

> `touch` does not work on Windows. Use these equivalents in PowerShell.

**Create an empty file:**
```powershell
New-Item filename.py -ItemType File
```

**Create multiple files at once:**
```powershell
"serializers.py","urls.py" | ForEach-Object { New-Item "customers\$_" -ItemType File }
```

**Create a folder:**
```powershell
New-Item foldername -ItemType Directory
```

**Create all missing files in one shot** (run from project root):
```powershell
# App-level files startapp doesn't create
New-Item customers\serializers.py, customers\urls.py -ItemType File
New-Item plans\serializers.py, plans\urls.py -ItemType File
New-Item subscriptions\serializers.py, subscriptions\urls.py -ItemType File
New-Item billing\serializers.py, billing\urls.py -ItemType File
New-Item notifications\serializers.py, notifications\urls.py -ItemType File
New-Item importer\serializers.py, importer\urls.py, importer\views.py, importer\apps.py -ItemType File
New-Item audit\signals.py -ItemType File

# Services folder (already created)
New-Item services\weekday_calculator.py,
         services\billing_engine.py,
         services\pause_service.py,
         services\customer_service.py,
         services\notification_service.py,
         services\transfer_service.py,
         services\import_service.py -ItemType File

# Tests
New-Item tests\test_weekday_calculator.py,
         tests\test_billing_engine.py,
         tests\test_pause_service.py,
         tests\test_notification_service.py,
         tests\test_transfer_service.py,
         tests\test_import_service.py,
         tests\test_api_endpoints.py -ItemType File
```

---

## 12. Key Python Packages

```toml
# pyproject.toml — managed by uv
[project]
dependencies = [
    "django",
    "djangorestframework",
    "djangorestframework-simplejwt",
    "django-cors-headers",
]

[dependency-groups]
dev = [
    "pytest",
    "pytest-django",
]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
```

---

## 13. Key npm Packages (frontend)

```
react-router-dom    ← page routing
axios               ← API calls
react-hook-form     ← form handling
date-fns            ← date formatting
```

---

## 14. Resolved Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Registration flow | Two-step: register first, then subscribe separately |
| 2 | Pause approval | Self-serve and immediate — no owner approval in v1 |
| 3 | Auth token type | JWT via djangorestframework-simplejwt |
| 4 | Landing page location | Same React app at `/` |
| 5 | CORS in dev | django-cors-headers (explicit, production-consistent) |
| 6 | Clock behavior | Idempotent — duplicate POST /clock for same date is a no-op |
| 7 | Subscription ownership | SubscriptionOwnershipPeriod table — no direct customer FK on Subscription |
| 8 | BillingRecord per transfer | One record per customer per ownership segment per month |

---

*Last updated: Backend initialization phase — structure created, models next*
*Current status: services/ folder created, Django apps created, missing files to be created with New-Item*
