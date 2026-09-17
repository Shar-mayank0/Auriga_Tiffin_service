from django.db import models
from django.contrib.auth.models import User


class AuditLog(models.Model):

    class EventType(models.TextChoices):
        SUBSCRIBED   = 'SUBSCRIBED',   'Subscribed'
        PAUSED       = 'PAUSED',       'Paused'
        RESUMED      = 'RESUMED',      'Resumed'
        BILLED       = 'BILLED',       'Billed'
        CANCELLED    = 'CANCELLED',    'Cancelled'
        TRANSFERRED  = 'TRANSFERRED',  'Transferred'
        IMPORTED     = 'IMPORTED',     'Imported'
        NOTIFIED     = 'NOTIFIED',     'Notified'

    event_type  = models.CharField(max_length=20, choices=EventType.choices)
    entity_type = models.CharField(max_length=50)   # e.g. 'Subscription', 'Customer'
    entity_id   = models.IntegerField()
    notes       = models.TextField(blank=True, default='')
    timestamp   = models.DateTimeField(auto_now_add=True)
    operator    = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs')

    def __str__(self):
        return f"[{self.event_type}] {self.entity_type} #{self.entity_id} at {self.timestamp:%Y-%m-%d %H:%M}"

    class Meta:
        ordering = ['-timestamp']