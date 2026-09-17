from customers.models import Customer
from subscriptions.models import SubscriptionOwnershipPeriod


def search_by_phone(partial_phone: str):
    """
    Returns customers matching a partial phone number.
    """
    return Customer.objects.filter(phone__icontains=partial_phone)


def get_customer_status(customer: Customer):
    """
    Returns a customer's active subscription status, active pause (if any), and active plan.
    """
    ownership = (
        SubscriptionOwnershipPeriod.objects.filter(customer=customer, to_date__isnull=True)
        .select_related("subscription", "subscription__plan")
        .first()
    )

    if not ownership:
        return {"status": "INACTIVE", "active_pause": None, "plan": None}

    sub = ownership.subscription
    active_pause = sub.pause_periods.filter(resumed_at__isnull=True).first()

    return {
        "status": sub.status,
        "active_pause": active_pause,
        "plan": sub.plan,
    }
