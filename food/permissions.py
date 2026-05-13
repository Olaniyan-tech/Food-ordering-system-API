from rest_framework.permissions import BasePermission


class IsStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff

class IsOrderOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user
    
class IsApprovedVendor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, "vendor") and
            request.user.vendor.is_approved and
            request.user.vendor.is_active
        )

class IsVendorOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if not hasattr(request.user, "vendor"):
            return False
        return obj.vendor == request.user.vendor

class IsAnalyticsAllowed(BasePermission):
    # Only vendors whose plan includes analytics

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        try:
            vendor = request.user.vendor
            return (
                vendor.subscription.is_valid() and
                vendor.subscription.plan.analytics_access
            )
        except:
            return False