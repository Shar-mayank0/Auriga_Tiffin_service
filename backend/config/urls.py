from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from config.views import (
    # Auth
    RegisterView,
    LogoutView,
    # Plans
    PlanListView,
    # Customers
    CustomerMeView,
    CustomerStatusView,
    CustomerListView,
    # Subscriptions
    MySubscriptionView,
    SubscribeView,
    SubscriptionTransferView,
    # Pauses
    PauseListCreateView,
    PauseResumeView,
    # Billing
    MyBillingView,
    GenerateBillView,
    # Clock & Outbox
    ClockView,
    OutboxListView,
    # Import
    ImportCustomersView,
    # Audit
    AuditLogListView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('api/auth/register/', RegisterView.as_view(), name='auth-register'),
    path('api/auth/login/', TokenObtainPairView.as_view(), name='auth-login'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),
    path('api/auth/logout/', LogoutView.as_view(), name='auth-logout'),

    # Plans
    path('api/plans/', PlanListView.as_view(), name='plan-list'),

    # Customers
    path('api/customers/', CustomerListView.as_view(), name='customer-list'),
    path('api/customers/me/', CustomerMeView.as_view(), name='customer-me'),
    path('api/customers/me/status/', CustomerStatusView.as_view(), name='customer-status'),

    # Subscriptions
    path('api/subscriptions/', SubscribeView.as_view(), name='subscribe'),
    path('api/subscriptions/mine/', MySubscriptionView.as_view(), name='subscription-mine'),
    path('api/subscriptions/<int:pk>/transfer/', SubscriptionTransferView.as_view(), name='subscription-transfer'),

    # Pauses
    path('api/pauses/', PauseListCreateView.as_view(), name='pause-list-create'),
    path('api/pauses/<int:pk>/resume/', PauseResumeView.as_view(), name='pause-resume'),

    # Billing
    path('api/billing/', MyBillingView.as_view(), name='billing-list'),
    path('api/billing/generate/', GenerateBillView.as_view(), name='billing-generate'),

    # Clock & Outbox (T1)
    path('api/clock/', ClockView.as_view(), name='clock'),
    path('api/outbox/', OutboxListView.as_view(), name='outbox-list'),

    # Import (T4)
    path('api/import/customers/', ImportCustomersView.as_view(), name='import-customers'),

    # Audit
    path('api/audit/', AuditLogListView.as_view(), name='audit-log-list'),
]
