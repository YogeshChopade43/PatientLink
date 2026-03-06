from django.contrib import messages
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "clinic_name", "is_active", "is_staff", "created_at")
    list_filter = ("is_active", "is_staff", "is_superuser", "created_at")
    search_fields = ("username", "clinic_name")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "date_joined", "last_login")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Clinic", {"fields": ("clinic_name", "created_at")}),
    )

    def _is_last_active_superuser(self, user_obj):
        if not (user_obj.is_superuser and user_obj.is_active):
            return False
        active_superusers = User.objects.filter(is_superuser=True, is_active=True).count()
        return active_superusers <= 1

    def save_model(self, request, obj, form, change):
        if change:
            previous = User.objects.filter(pk=obj.pk).first()
            if previous and previous.username == "admin" and obj.username != "admin":
                self.message_user(
                    request,
                    "The admin superuser username cannot be changed.",
                    level=messages.ERROR,
                )
                return

        if obj.username == "admin":
            obj.is_superuser = True
            obj.is_staff = True
            obj.is_active = True
        else:
            obj.is_superuser = False
            obj.is_staff = False

        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        if obj.username == "admin":
            self.message_user(
                request,
                "The admin superuser account cannot be deleted.",
                level=messages.ERROR,
            )
            return

        if request.user.id == obj.id:
            self.message_user(
                request,
                "You cannot delete your own account.",
                level=messages.ERROR,
            )
            return

        if self._is_last_active_superuser(obj):
            self.message_user(
                request,
                "Cannot delete the last active superuser account.",
                level=messages.ERROR,
            )
            return

        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        protected_ids = {str(request.user.id)}
        protected_admin_ids = {str(u.id) for u in queryset if u.username == "admin"}
        protected_last_superuser_ids = {
            str(u.id)
            for u in queryset
            if self._is_last_active_superuser(u)
        }
        blocked_ids = protected_ids.union(protected_admin_ids).union(protected_last_superuser_ids)

        if blocked_ids:
            self.message_user(
                request,
                "Some selected users were not deleted (self account or last active superuser).",
                level=messages.WARNING,
            )

        deletable = queryset.exclude(id__in=blocked_ids)
        super().delete_queryset(request, deletable)
