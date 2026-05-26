from django.contrib.auth.views import LoginView as DjangoLoginView
from django.shortcuts import redirect
from django.views.generic import TemplateView
from .models import Progress, Step


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        completed_step_ids = Progress.objects.filter(
            trainee=user
        ).values_list("step_id", flat=True)

        next_step = Step.objects.exclude(
            id__in=completed_step_ids
        ).order_by("order").first()

        context["next_step"] = next_step

        return context


class AdminHomeView(TemplateView):
    template_name = "app/admin_home.html"


class HomeView(TemplateView):
    template_name = "app/home.html"