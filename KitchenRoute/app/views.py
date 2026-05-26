from django.contrib.auth.views import LoginView as DjangoLoginView
from django.shortcuts import redirect
from django.views.generic import TemplateView


class LoginView(DjangoLoginView):
    template_name = "app/login.html"

    def get_success_url(self):
        user = self.request.user

        if user.role == 0:
            return "/trainee-home/"

        if user.role == 1:
            return "/educator-home/"

        if user.role == 2:
            return "/admin-home/"

        return "/"
    

class EducatorHomeView(TemplateView):
    template_name = "app/educator_home.html"


class TraineeHomeView(TemplateView):
    template_name = "app/trainee_home.html"


class AdminHomeView(TemplateView):
    template_name = "app/admin_home.html"


class HomeView(TemplateView):
    template_name = "app/home.html"