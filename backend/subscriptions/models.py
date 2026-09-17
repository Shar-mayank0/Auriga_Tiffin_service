from django.db import models
from customers.models import Customer
from plans.models import Plan


class Subscription(models.Model):

    class Status(models.TextChoices):
        ACTIVE    = 'ACTIVE',    'Active'
        PAUSED    = 'PAUSED',    'Paused'
        CANCELLED = 'CANCELLED', 'Cancelled'

    plan       = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    start_date = models.DateField()
    end_date   = models.DateField(null=True, blank=True)
    status     = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Subscription #{self.pk} [{self.status}]"

    class Meta:
        ordering = ['-created_at']


class SubscriptionOwnershipPeriod(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='ownership_periods')
    customer     = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='ownership_periods')
    from_date    = models.DateField()
    to_date      = models.DateField(null=True, blank=True)  # null = currently active owner

    def __str__(self):
        to = self.to_date or 'present'
        return f"{self.customer} owns Sub#{self.subscription_id} ({self.from_date} → {to})"

    class Meta:
        ordering = ['from_date']


class PausePeriod(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='pause_periods')
    start_date   = models.DateField()
    end_date     = models.DateField(null=True, blank=True)  # null = open-ended pause
    created_at   = models.DateTimeField(auto_now_add=True)
    resumed_at   = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        end = self.end_date or 'open'
        return f"Pause for Sub#{self.subscription_id} ({self.start_date} → {end})"

    class Meta:
        ordering = ['-start_date']