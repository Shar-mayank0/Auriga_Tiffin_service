from django.db import models


class Plan(models.Model):
    name           = models.CharField(max_length=100)
    monthly_price  = models.DecimalField(max_digits=8, decimal_places=2)
    effective_from = models.DateField()
    is_active      = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (₹{self.monthly_price})"

    class Meta:
        ordering = ['-effective_from']