from django.contrib.auth.views import LoginView as DjangoLoginView
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView
from .models import Progress, Step, User


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        trainees = User.objects.filter(
            organization=self.request.user.organization,
            role=0,
        )

        trainee_summaries = []
        total_steps = Step.objects.count()

        for trainee in trainees:
            completed_count = Progress.objects.filter(
                trainee=trainee
            ).count()

            if total_steps == 0:
                progress_rate = 0
            else:
                progress_rate = round(completed_count / total_steps * 100)

            trainee_summaries.append(
                {
                    "trainee": trainee,
                    "progress_rate": progress_rate,
                }
            )

        context["trainee_summaries"] = trainee_summaries

        return context


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


class TraineeDetailView(TemplateView):
    template_name = "app/trainee_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        trainee = User.objects.get(id=self.kwargs["user_id"])

        completed_step_ids = Progress.objects.filter(
            trainee=trainee
        ).values_list("step_id", flat=True)

        steps = Step.objects.all().order_by("order")

        context["trainee"] = trainee
        context["steps"] = steps
        context["completed_step_ids"] = completed_step_ids

        return context
    

class MarkStepPassedView(TemplateView):
    def post(self, request, *args, **kwargs):
        trainee = get_object_or_404(User, id=kwargs["user_id"])
        step = get_object_or_404(Step, id=kwargs["step_id"])

        Progress.objects.get_or_create(
            trainee=trainee,
            step=step,
            defaults={
                "recorded_by": request.user,
            },
        )

        return redirect("trainee_detail", user_id=trainee.id)    


class HomeView(TemplateView):
    template_name = "app/home.html"