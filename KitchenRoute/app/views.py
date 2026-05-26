from django.contrib.auth.views import LoginView as DjangoLoginView
from django.views.generic import TemplateView


class LoginView(DjangoLoginView):
    template_name = "app/login.html"


class HomeView(TemplateView):
    template_name = "app/home.html"