from rest_framework.permissions import BasePermission, IsAuthenticated


class IsStaffOrReadOnly(BasePermission):
    """Allow GET for any authenticated user; write actions only for staff."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.is_staff


class IsStaff(BasePermission):
    """Only Django staff users can access."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsOwnerCustomer(BasePermission):
    """Customer can only see/edit their own data."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        try:
            return obj.user == request.user or obj.customer.user == request.user
        except AttributeError:
            return False
