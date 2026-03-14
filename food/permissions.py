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
    