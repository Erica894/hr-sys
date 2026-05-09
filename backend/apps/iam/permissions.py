from rest_framework.permissions import BasePermission


class IsHRAdmin(BasePermission):
    message = "HR_ADMIN role required."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.roles.filter(role__code="HR_ADMIN").exists()
