from rest_framework.permissions import BasePermission

class IsStaffOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method == "GET":
            return request.user.is_authenticated
        return request.user.is_staff

class IsOrderOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user

class IsStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff
    
class IsVendor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, "vendor")
        )

class IsApprovedVendor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, "vendor") and
            request.user.vendor.is_approved and
            request.user.vendor.is_active
        )

class IsVendorOrderOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if not hasattr(request.user, "vendor"):
            return False
        return obj.vendor == request.user.vendor

class IsStaffOrVendorOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if not hasattr(request.user, "vendor"):
            return False
        return obj.vendor == request.user.vendor