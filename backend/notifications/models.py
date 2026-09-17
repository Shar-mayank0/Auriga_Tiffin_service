from django.db import models
from customers.models import Customer


class SystemClock(models.Model):
    # Always one row, id=1. Never create a second row.
    current_date = models.DateField()

    def __str__(self):
        return f"System date: {self.current_date}"

    class Meta:
        verbose_name = 'System Clock'


class OutboxEntry(models.Model):
    customer      = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='outbox_entries')
    delivery_date = models.DateField()
    message       = models.TextField()
    created_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Outbox: {self.customer} on {self.delivery_date}"

    class Meta:
        ordering = ['-delivery_date']
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'delivery_date'],
                name='unique_outbox_per_customer_per_day'
            )
        ]
