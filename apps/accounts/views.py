from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, View

from .forms import (
    UserRegisterForm,
    UserLoginForm,
    UserUpdateForm,
    ProfileUpdateForm,
)
from .models import CustomUser, Profile


class RegisterView(CreateView):
    """
    Vista de registro de nuevos usuarios con rol de Entrenador o Aficionado.
    """

    model = CustomUser
    form_class = UserRegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        messages.success(
            self.request,
            f"¡Cuenta creada con éxito para {user.username}! Ya puedes iniciar sesión con tus credenciales.",
        )
        return super().form_valid(form)


class LoginView(DjangoLoginView):
    """
    Vista de inicio de sesión con mensajes de retroalimentación.
    """

    form_class = UserLoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        messages.info(
            self.request,
            f"¡Bienvenido de nuevo, {user.get_full_name() or user.username}! ({user.get_role_display()})",
        )
        return super().form_valid(form)


class LogoutView(View):
    """
    Vista de cierre de sesión seguro.
    """

    def post(self, request):
        logout(request)
        messages.info(request, "Has cerrado sesión correctamente. ¡Hasta pronto!")
        return redirect("core:home")

    def get(self, request):
        logout(request)
        messages.info(request, "Has cerrado sesión correctamente. ¡Hasta pronto!")
        return redirect("core:home")


class ProfileView(LoginRequiredMixin, View):
    """
    Vista para visualizar y editar la información de perfil del usuario activo.
    """

    template_name = "accounts/profile.html"

    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)
        return render(
            request,
            self.template_name,
            {
                "user_form": user_form,
                "profile_form": profile_form,
                "profile": profile,
            },
        )

    def post(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST, request.FILES, instance=profile
        )

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(
                request, "Tu perfil ha sido actualizado satisfactoriamente."
            )
            return redirect("accounts:profile")

        messages.error(
            request, "Por favor corrige los errores indicados en el formulario."
        )
        return render(
            request,
            self.template_name,
            {
                "user_form": user_form,
                "profile_form": profile_form,
                "profile": profile,
            },
        )
