# Tiffin Service Billing System Requirements

## 1. Problem Statement (Mandatory)

A home-style tiffin (lunch delivery) service needs a system where:

- Customers subscribe to a monthly plan.
- Lunch is delivered on weekdays.
- Customers can pause and resume service for temporary gaps (travel, festivals, etc.).
- Paused days must not be billed.
- At month-end, each customer receives a pro-rated bill based only on days actually served.
- Customers are searchable by phone number.
- The owner can view each customer’s current status (active or paused).

Core goal: **ensure every customer is billed only for days they were actually served**.

---

## 2. Scope

### 2.1 In Scope

- Customer subscription to monthly tiffin plans.
- Pause/resume service lifecycle.
- Weekday-based service tracking.
- Pro-rated monthly billing using delivered days.
- Customer lookup by phone number.
- Status visibility (active/paused) for operations.

### 2.2 Out of Scope (for initial version)

- Payment gateway integration.
- Driver routing and delivery logistics optimization.
- Multi-meal/day plan complexity beyond lunch weekday model.
- GST/tax filing automation (may be added later).

---

## 3. Actors and Roles

- **Owner/Admin**: manages customers, service states, and billing.
- **Customer**: subscribes and requests pause/resume.
- **System**: enforces business rules and computes billing correctly.

---

## 4. Functional Requirements

## FR-1: Customer Management
- System must create a customer profile with at least:
  - Full name
  - Unique phone number
  - Address (optional for lookup, required for delivery operations)
  - Subscription start date
  - Plan assignment
- Phone number must be unique and used as primary lookup key.
- System must support viewing and updating customer profile details.

## FR-2: Plan Management
- System must support defining monthly plans with:
  - Plan name
  - Monthly base price
  - Effective date/version support (for future plan price changes)
- Customer must be mapped to one active monthly plan at a time.

## FR-3: Subscription Lifecycle
- Owner must be able to subscribe a customer to a plan.
- Subscription status must include at minimum:
  - Active
  - Paused
  - Inactive/Cancelled (optional but recommended)
- Subscription state changes must be timestamped.

## FR-4: Pause Service
- Owner must be able to pause service for:
  - A single date
  - A date range (start and end)
  - Open-ended pause (resume date not yet known)
- Pause requests must prevent charging for all paused weekdays in the selected range.
- Overlapping pause ranges must be merged or rejected to avoid double counting.

## FR-5: Resume Service
- Owner must be able to resume service after a pause.
- Resume action must:
  - End active pause state
  - Restore customer status to active
  - Ensure billing includes only resumed delivery weekdays onward

## FR-6: Delivery-Day Eligibility Rules
- Service days considered for billing must include only weekdays (Monday–Friday).
- Weekend days (Saturday/Sunday) must be excluded from billable day counts by default.
- Paused weekdays must be excluded from billable day counts.
- Any day before subscription start date must never be billable.

## FR-7: Billing Computation (Core)
- Month-end bill must be generated per customer for a selected billing month.
- Pro-rated formula (minimum baseline):
  - `Daily Rate = Monthly Plan Price / Total Billable Weekdays in Billing Month`
  - `Amount Due = Daily Rate × Delivered Weekdays`
- Delivered weekdays = billable weekdays after excluding paused weekdays and non-service days.
- Billing output must include:
  - Billing month
  - Plan price
  - Total weekdays in month
  - Paused weekdays
  - Delivered weekdays
  - Daily rate
  - Final amount due
- Billing must be deterministic and reproducible for the same inputs.

## FR-8: Billing for Mid-Month Subscription Changes
- If a customer starts subscription mid-month:
  - Days before start date must be excluded from delivered weekdays.
  - Pro-rated bill must apply only to eligible service window in that month.
- If a subscription ends/cancels mid-month:
  - Days after end date must be excluded.

## FR-9: Customer Lookup
- Owner must be able to search customers by full or partial phone number.
- Search results must return:
  - Customer identity
  - Current subscription status
  - Active plan
  - Current pause window (if paused)

## FR-10: Active vs Paused Dashboard View
- System must provide list/filter views for:
  - All active customers
  - All paused customers
- Status view should be current and consistent with pause/resume events.

## FR-11: Validation and Error Handling
- Invalid date ranges (pause end before start) must be rejected.
- Pause/resume actions on non-existent customers must fail with clear errors.
- Duplicate phone numbers must be rejected.
- Billing generation must fail gracefully if required customer/plan data is missing.

## FR-12: Auditability
- System must track key events:
  - Subscription created/updated
  - Pause created/edited/cancelled
  - Resume action
  - Bill generated
- Each event should preserve timestamp and operator identity where available.

---

## 5. Non-Functional Requirements

## NFR-1: Correctness
- Billing calculations must be mathematically correct for all supported lifecycle states.
- Date calculations must be timezone-consistent (single canonical timezone for business rules).
- Pause and delivery day rules must be applied consistently across all reports and invoices.

## NFR-2: Performance
- Phone lookup should return results quickly for normal operational usage (target: near-instant for small-to-medium customer sets).
- Month-end billing generation should complete within acceptable business time for all active customers.

## NFR-3: Reliability
- System must avoid data loss for subscriptions, pause periods, and billing records.
- Failed billing runs must be recoverable and re-runnable without corrupting prior records.

## NFR-4: Data Integrity
- Enforce unique constraints for customer phone.
- Prevent inconsistent lifecycle states (e.g., two overlapping active pauses for same customer if unsupported).
- Use transactional updates for pause/resume and billing record writes.

## NFR-5: Security
- Access to customer data and billing operations must be restricted to authorized owner/admin users.
- Sensitive customer data must be protected at rest and in transit where applicable.
- Input validation must guard against malformed or malicious input.

## NFR-6: Usability
- Owner workflows (subscribe, pause/resume, lookup, bill generation) should require minimal steps.
- Error messages should be actionable and human-readable.
- Status indicators (active/paused) should be clear and visible in listing views.

## NFR-7: Maintainability
- Business rules for weekday eligibility and proration must be centralized and testable.
- Requirement-to-implementation traceability should be preserved for future feature expansion.
- Documentation should remain versioned with product changes.

## NFR-8: Scalability
- Design should support growth from small customer counts to larger local service volumes without redesigning core billing logic.
- Data model should support adding future plan variants and service-day rules.

## NFR-9: Observability
- System should log billing runs and lifecycle changes for debugging and support.
- Errors should be captured with enough context to diagnose failed operations.

## NFR-10: Compliance Readiness
- Records should be retainable for business and tax reference periods.
- Generated billing details should be exportable/printable in future integrations.

---

## 6. Key Business Rules Summary

1. Weekends are non-billable by default.
2. Paused weekdays are non-billable.
3. Only served weekdays are billable.
4. Phone number is the operational customer lookup key.
5. Customer status must always resolve to active or paused for owner visibility.
6. Month-end billing must be pro-rated, transparent, and reproducible.

---

## 7. Acceptance Criteria (Initial Milestone)

- Owner can subscribe a customer to a monthly plan.
- Owner can pause and resume service accurately with date control.
- System generates correct monthly pro-rated bill based on delivered weekdays only.
- Owner can search customer by phone.
- Owner can view who is active vs paused at any time.
- No customer is charged for paused days.
