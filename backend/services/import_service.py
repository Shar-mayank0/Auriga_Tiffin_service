from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple
from django.contrib.auth.models import User
from django.db import transaction
from audit.models import AuditLog
from customers.models import Customer
from plans.models import Plan
from subscriptions.models import Subscription, SubscriptionOwnershipPeriod


DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%b %d %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%B %d, %Y",
    "%d-%b-%y",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y/%m/%d",
]


def normalize_date(raw_value: Any) -> Optional[date]:
    """
    Parses and normalizes varied raw date representations into datetime.date.
    Returns None if unparseable.
    """
    if not raw_value:
        return None
    if isinstance(raw_value, date):
        return raw_value

    val_str = str(raw_value).strip()
    if not val_str:
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            continue

    return None


def validate_row(row: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates an individual import row.
    Returns (is_valid, reasons_list).
    """
    reasons: List[str] = []

    name = str(row.get("name") or "").strip()
    if not name:
        reasons.append("Name is required.")

    phone = str(row.get("phone") or "").strip()
    if not phone:
        reasons.append("Phone is required.")

    start_date = normalize_date(row.get("start_date"))
    if not start_date:
        reasons.append("A valid start_date is required.")

    plan_id = row.get("plan_id")
    if plan_id:
        if not Plan.objects.filter(id=plan_id).exists():
            reasons.append(f"Plan with id {plan_id} does not exist.")
    else:
        if not Plan.objects.filter(is_active=True).exists():
            reasons.append("No active plan available to assign.")

    return len(reasons) == 0, reasons


def deduplicate(
    rows: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Groups rows by phone number, preserving the first instance
    and placing subsequent rows with identical phone into deduped.
    """
    seen_phones = set()
    unique_rows: List[Dict[str, Any]] = []
    deduped_rows: List[Dict[str, Any]] = []

    for row in rows:
        phone = str(row.get("phone") or "").strip()
        if phone in seen_phones:
            deduped_rows.append(row)
        else:
            seen_phones.add(phone)
            unique_rows.append(row)

    return unique_rows, deduped_rows


def run_import(
    raw_data: List[Dict[str, Any]], operator: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Imports customer and subscription data:
    - Normalizes & deduplicates by phone
    - Validates required fields
    - Creates User, Customer, Subscription, and OwnershipPeriod per valid row
    - Runs each row in an isolated transaction so invalid rows do not block valid ones
    - Returns summary dict: {imported: int, deduped: int, rejected: [{row, reasons}]}
    """
    unique_rows, deduped_rows = deduplicate(raw_data)

    imported_count = 0
    rejected_items: List[Dict[str, Any]] = []

    for row in unique_rows:
        is_valid, reasons = validate_row(row)
        if not is_valid:
            rejected_items.append({"row": row, "reasons": reasons})
            continue

        name = str(row["name"]).strip()
        phone = str(row["phone"]).strip()
        address = str(row.get("address") or "").strip()
        start_date = normalize_date(row["start_date"])

        plan_id = row.get("plan_id")
        if plan_id:
            plan = Plan.objects.get(id=plan_id)
        else:
            plan = Plan.objects.filter(is_active=True).first()

        try:
            with transaction.atomic():
                if Customer.objects.filter(phone=phone).exists():
                    rejected_items.append(
                        {
                            "row": row,
                            "reasons": [
                                f"Customer with phone {phone} already exists in database."
                            ],
                        }
                    )
                    continue

                username = f"user_{phone}"
                user, _ = User.objects.get_or_create(
                    username=username, defaults={"first_name": name}
                )

                customer = Customer.objects.create(
                    user=user,
                    name=name,
                    phone=phone,
                    address=address,
                )

                sub = Subscription.objects.create(
                    plan=plan,
                    start_date=start_date,
                    status=Subscription.Status.ACTIVE,
                )

                SubscriptionOwnershipPeriod.objects.create(
                    subscription=sub,
                    customer=customer,
                    from_date=start_date,
                    to_date=None,
                )

                AuditLog.objects.create(
                    event_type=AuditLog.EventType.IMPORTED,
                    entity_type="Customer",
                    entity_id=customer.id,
                    operator=operator,
                    notes=f"Imported customer {name} ({phone}) subscribed to {plan.name}",
                )

                imported_count += 1
        except Exception as e:
            rejected_items.append({"row": row, "reasons": [str(e)]})

    return {
        "imported": imported_count,
        "deduped": len(deduped_rows),
        "rejected": rejected_items,
    }
