from functools import wraps
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


def role_required(allowed_roles):
    """
    Decorador para restringir vistas según uno o varios roles permitidos.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(
                    request, "Debes iniciar sesión para acceder a esta sección."
                )
                return redirect("accounts:login")

            if (
                request.user.role in allowed_roles
                or request.user.is_superuser
                or request.user.role == "ADMIN"
            ):
                return view_func(request, *args, **kwargs)

            messages.error(
                request, "No tienes los permisos requeridos para acceder a esta sección."
            )
            raise PermissionDenied

        return _wrapped_view

    return decorator


def table_official_required(view_func):
    """
    Decorador para restringir acceso exclusivo a Mesa Arbitral o Administrador.
    """
    return role_required(["ADMIN", "TABLE_OFFICIAL"])(view_func)


def coach_required(view_func):
    """
    Decorador para restringir acceso a Entrenadores o Administrador.
    """
    return role_required(["ADMIN", "COACH"])(view_func)


class RoleRequiredMixin(AccessMixin):
    """
    Mixin de Django Class-Based Views para control de acceso por roles.
    """

    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(
                request, "Debes iniciar sesión para acceder a esta sección."
            )
            return redirect("accounts:login")

        if (
            request.user.role in self.allowed_roles
            or request.user.is_superuser
            or request.user.role == "ADMIN"
        ):
            return super().dispatch(request, *args, **kwargs)

        messages.error(
            request, "No tienes los permisos requeridos para realizar esta acción."
        )
        raise PermissionDenied


class TableOfficialRequiredMixin(RoleRequiredMixin):
    allowed_roles = ["ADMIN", "TABLE_OFFICIAL"]


class CoachRequiredMixin(RoleRequiredMixin):
    allowed_roles = ["ADMIN", "COACH"]
