from django.db import models
from subscriptions.models import Subscription
from customers.models import Customer


class BillingRecord(models.Model):
    subscription              = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='billing_records')
    customer                  = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='billing_records')
    billing_month             = models.DateField()
    ownership_from            = models.DateField()
    ownership_to              = models.DateField()
    total_weekdays_in_segment = models.IntegerField()
    paused_weekdays           = models.IntegerField()
    delivered_weekdays        = models.IntegerField()
    daily_rate                = models.DecimalField(max_digits=8, decimal_places=2)
    amount_due                = models.DecimalField(max_digits=8, decimal_places=2)
    generated_at              = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bill for {self.customer} ({self.billing_month:%Y-%m}) - ₹{self.amount_due}"

    class Meta:
        ordering = ['-billing_month', '-generated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['subscription', 'customer', 'billing_month'],
                name='unique_billing_per_customer_per_sub_per_month'
            )
        ]
