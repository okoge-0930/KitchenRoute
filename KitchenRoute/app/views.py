from django.contrib.auth.views import LoginView as DjangoLoginView
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.views.generic import TemplateView
from .models import Progress, Recipe, Step, User, Organization
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from datetime import timedelta
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
import uuid
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib import messages


class LoginView(TemplateView):
    template_name = "app/login.html"

    def post(self, request, *args, **kwargs):
        organization_code = request.POST.get("organization_code")
        email = request.POST.get("email")
        password = request.POST.get("password")

        organization = Organization.objects.filter(
            organization_code=organization_code
        ).first()

        if organization is None:
            return render(
                request,
                self.template_name,
                {
                    "error":
                    "メールアドレス、パスワード、または組織コードが正しくありません。",
                },
            )

        user = User.objects.filter(
            email=email
        ).first()

        if user is None:
            return render(
                request,
                self.template_name,
                {
                    "error":
                    "メールアドレス、パスワード、または組織コードが正しくありません。",
                },
            )

        if not user.check_password(password):
            return render(
                request,
                self.template_name,
                {
                    "error":
                    "メールアドレス、パスワード、または組織コードが正しくありません。",
                },
            )

        if user.organization is None:
            user.organization = organization
            user.save()

        elif user.organization != organization:
            return render(
                request,
                self.template_name,
                {
                    "error":
                    "メールアドレス、パスワード、または組織コードが正しくありません。",
                },
            )

        login(request, user)

        if user.role == 0:
            return redirect("trainee_home")

        if user.role == 1:
            return redirect("educator_home")

        if user.role == 2:
            return redirect("admin_home")

        return redirect("home")
    

class EducatorHomeView(LoginRequiredMixin, TemplateView):
    template_name = "app/educator_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        search_keyword = self.request.GET.get("keyword", "")

        users = User.objects.filter(
            organization=self.request.user.organization
        )

        if search_keyword:
            users = users.filter(
                username__icontains=search_keyword
            )

        role_order = {
            2: 0,
            1: 1,
            0: 2,
        }

        users = sorted(
            users,
            key=lambda user: (
                role_order.get(user.role, 99),
                user.id,
            )
        )

        user_summaries = []

        total_steps = Step.objects.filter(
            recipe__organization=self.request.user.organization
        ).count()

        for user in users:
            completed_count = Progress.objects.filter(
                trainee=user,
                step__recipe__organization=self.request.user.organization,
            ).count()

            progress_rate = (
                round(completed_count / total_steps * 100)
                if total_steps > 0
                else 0
            )

            user_summaries.append(
                {
                    "user": user,
                    "progress_rate": progress_rate,
                }
            )

        context["user_summaries"] = user_summaries
        context["search_keyword"] = search_keyword

        return context


class TraineeHomeView(LoginRequiredMixin, TemplateView):
    template_name = "app/trainee_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        trainee = self.request.user

        recipes = Recipe.objects.filter(
            organization=trainee.organization
        ).order_by("id")

        task_list = []

        for recipe in recipes:
            steps = recipe.steps.order_by("order")

            next_step = None

            for step in steps:
                completed = Progress.objects.filter(
                    trainee=trainee,
                    step=step,
                ).exists()

                if not completed:
                    next_step = step
                    break

            if next_step:
                completed_count = Progress.objects.filter(
                    trainee=trainee,
                    step__recipe=recipe,
                ).count()

                total_count = steps.count()

                progress_rate = (
                    round(
                        completed_count
                        / total_count
                        * 100
                    )
                    if total_count > 0
                    else 0
                )

                task_list.append(
                    {
                        "recipe": recipe,
                        "step": next_step,
                        "progress_rate": progress_rate,
                    }
                )

        task_list.sort(
            key=lambda item: item["progress_rate"]
        )

        context["task_list"] = task_list[:5]

        return context


class AdminHomeView(LoginRequiredMixin, TemplateView):
    template_name = "app/admin_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        search_keyword = self.request.GET.get("keyword", "")

        users = User.objects.filter(
            organization=self.request.user.organization
        )

        if search_keyword:
            users = users.filter(
                username__icontains=search_keyword
            )

        role_order = {
            2: 0,
            1: 1,
            0: 2,
        }

        users = sorted(
            users,
            key=lambda user: (
                role_order.get(user.role, 99),
                user.id,
            )
        )

        user_summaries = []

        total_steps = Step.objects.filter(
            recipe__organization=self.request.user.organization
        ).count()

        for user in users:
            completed_count = Progress.objects.filter(
                trainee=user,
                step__recipe__organization=self.request.user.organization,
            ).count()

            progress_rate = (
                round(completed_count / total_steps * 100)
                if total_steps > 0
                else 0
            )

            user_summaries.append(
                {
                    "user": user,
                    "progress_rate": progress_rate,
                }
            )

        context["user_summaries"] = user_summaries
        context["search_keyword"] = search_keyword

        return context


class TraineeDetailView(LoginRequiredMixin, TemplateView):
    template_name = "app/trainee_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        trainee = get_object_or_404(
            User,
            id=self.kwargs["user_id"],
            organization=self.request.user.organization,
        )

        recipes = Recipe.objects.filter(
            organization=self.request.user.organization
        ).order_by("id")

        incomplete_recipe_progresses = []
        completed_recipe_progresses = []

        for recipe in recipes:
            steps = Step.objects.filter(
                recipe=recipe
            ).order_by("order")

            step_items = []
            completed_count = 0
            total_count = steps.count()

            for step in steps:
                progress = Progress.objects.filter(
                    trainee=trainee,
                    step=step,
                ).first()

                is_completed = progress is not None

                if is_completed:
                    completed_count += 1

                step_items.append(
                    {
                        "step": step,
                        "is_completed": is_completed,
                        "progress": progress,
                    }
                )

            progress_rate = (
                round(completed_count / total_count * 100)
                if total_count > 0
                else 0
            )

            recipe_progress = {
                "recipe": recipe,
                "steps": step_items,
                "progress_rate": progress_rate,
            }

            if progress_rate == 100:
                completed_recipe_progresses.append(recipe_progress)
            else:
                incomplete_recipe_progresses.append(recipe_progress)

        incomplete_recipe_progresses.sort(
            key=lambda item: item["progress_rate"]
        )

        context["trainee"] = trainee
        context["incomplete_recipe_progresses"] = incomplete_recipe_progresses
        context["completed_recipe_progresses"] = completed_recipe_progresses
        context["completed_recipe_count"] = len(completed_recipe_progresses)

        return context
    

class MarkStepPassedView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        trainee = get_object_or_404(
            User,
            id=kwargs["user_id"],
            organization=request.user.organization,
        )
        step = get_object_or_404(
            Step,
            id=kwargs["step_id"],
            recipe__organization=request.user.organization,
        )

        progress, created = Progress.objects.get_or_create(
            trainee=trainee,
            step=step,
            defaults={
                "recorded_by": request.user,
            },
        )

        total_count = Step.objects.filter(
            recipe=step.recipe
        ).count()
        completed_count = Progress.objects.filter(
            trainee=trainee,
            step__recipe=step.recipe,
        ).count()
        progress_rate = (
            round(completed_count / total_count * 100)
            if total_count > 0
            else 0
        )

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "progress_rate": progress_rate,
                    "recorded_by": (
                        progress.recorded_by.username
                        if progress.recorded_by
                        else ""
                    ),
                }
            )

        return redirect("trainee_detail", user_id=trainee.id)    


class HomeView(View):
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        if request.user.role == 0:
            return redirect("trainee_home")

        if request.user.role == 1:
            return redirect("educator_home")

        return redirect("admin_home")
    
    
class SkillManagementView(LoginRequiredMixin, TemplateView):
    template_name = "app/skill_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        recipes = Recipe.objects.filter(
            organization=self.request.user.organization
        ).order_by("id")

        context["recipes"] = recipes

        return context
    
    
class StepManagementView(LoginRequiredMixin, TemplateView):
    template_name = "app/step_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        recipe = get_object_or_404(
            Recipe,
            id=self.kwargs["recipe_id"],
            organization=self.request.user.organization,
        )

        steps = Step.objects.filter(
            recipe=recipe
        ).order_by("order")

        context["recipe"] = recipe
        context["steps"] = steps

        return context
    

class RecipeCreateView(TemplateView):
    template_name = "app/recipe_create.html"

    def post(self, request, *args, **kwargs):
        recipe_name = request.POST.get("name")

        if recipe_name:
            Recipe.objects.create(
                organization=request.user.organization,
                name=recipe_name,
            )

        return redirect("skill_management")
    
    
class RecipeUpdateView(LoginRequiredMixin, View):
    def get(self, request, recipe_id):
        recipe = get_object_or_404(
            Recipe,
            id=recipe_id,
            organization=request.user.organization,
        )
        redirect_to = request.GET.get("next", "")

        if not url_has_allowed_host_and_scheme(
            redirect_to,
            allowed_hosts={request.get_host()},
        ):
            redirect_to = ""

        return render(
            request,
            "app/recipe_update.html",
            {
                "recipe": recipe,
                "redirect_to": redirect_to,
            },
        )

    def post(self, request, recipe_id):
        recipe = get_object_or_404(
            Recipe,
            id=recipe_id,
            organization=request.user.organization,
        )

        recipe.name = request.POST.get("name")
        recipe.save()

        redirect_to = request.POST.get("next", "")

        if url_has_allowed_host_and_scheme(
            redirect_to,
            allowed_hosts={request.get_host()},
        ):
            return redirect(redirect_to)

        return redirect("skill_management")
        

class StepCreateView(TemplateView):
    template_name = "app/step_create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        recipe = get_object_or_404(
            Recipe,
            id=self.kwargs["recipe_id"],
            organization=self.request.user.organization,
        )

        context["recipe"] = recipe

        return context

    def post(self, request, *args, **kwargs):
        recipe = get_object_or_404(
            Recipe,
            id=self.kwargs["recipe_id"],
            organization=request.user.organization,
        )

        step_name = request.POST.get("name")
        step_order = request.POST.get("order")

        if step_name and step_order:
            Step.objects.create(
                recipe=recipe,
                name=step_name,
                order=step_order,
            )

        return redirect("step_management", recipe_id=recipe.id)
    
    
class StepUpdateView(TemplateView):
    template_name = "app/step_update.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        step = get_object_or_404(
            Step,
            id=self.kwargs["step_id"],
            recipe__organization=self.request.user.organization,
        )

        context["step"] = step

        return context

    def post(self, request, *args, **kwargs):
        step = get_object_or_404(
            Step,
            id=self.kwargs["step_id"],
            recipe__organization=request.user.organization,
        )

        step_order = request.POST.get("order")
        step_name = request.POST.get("name")

        if step_order and step_name:
            step.order = step_order
            step.name = step_name
            step.save()

        return redirect("step_management", recipe_id=step.recipe.id)
    
    
class StepDeleteView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        step = get_object_or_404(
            Step,
            id=self.kwargs["step_id"],
            recipe__organization=request.user.organization,
        )

        return redirect(
            "step_management",
            recipe_id=step.recipe.id,
        )

    def post(self, request, *args, **kwargs):
        step = get_object_or_404(
            Step,
            id=self.kwargs["step_id"],
            recipe__organization=request.user.organization,
        )

        recipe_id = step.recipe.id
        step.delete()

        messages.success(
            request,
            "工程が削除されました。"
        )

        return redirect(
            "step_management",
            recipe_id=recipe_id,
        )
        

class RecipeDeleteView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        get_object_or_404(
            Recipe,
            id=self.kwargs["recipe_id"],
            organization=request.user.organization,
        )

        return redirect("skill_management")

    def post(self, request, *args, **kwargs):
        recipe = get_object_or_404(
            Recipe,
            id=self.kwargs["recipe_id"],
            organization=request.user.organization,
        )

        recipe.delete()

        messages.success(
            request,
            "レシピが削除されました。"
        )

        return redirect("skill_management")
    
    
class ChangeUserRoleView(LoginRequiredMixin, View):

    def post(self, request, user_id, role):
        user = get_object_or_404(
            User,
            id=user_id,
            organization=request.user.organization,
        )

        user.role = role
        user.save()

        return redirect("admin_home")
    
    
class TraineeTaskDetailView(LoginRequiredMixin, TemplateView):
    template_name = "app/trainee_task_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        trainee = self.request.user

        recipe = get_object_or_404(
            Recipe,
            id=self.kwargs["recipe_id"],
            organization=trainee.organization,
        )

        steps = Step.objects.filter(
            recipe=recipe
        ).order_by("order")

        completed_step_ids = Progress.objects.filter(
            trainee=trainee,
            step__recipe=recipe,
        ).values_list("step_id", flat=True)

        total_count = steps.count()
        completed_count = len(completed_step_ids)

        progress_rate = (
            round(completed_count / total_count * 100)
            if total_count > 0
            else 0
        )

        context["recipe"] = recipe
        context["steps"] = steps
        context["completed_step_ids"] = completed_step_ids
        context["progress_rate"] = progress_rate

        return context
    
    
class MyProgressView(LoginRequiredMixin, TemplateView):
    template_name = "app/my_progress.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        trainee = self.request.user

        recipes = Recipe.objects.filter(
            organization=trainee.organization
        ).order_by("id")

        total_steps = Step.objects.filter(
            recipe__organization=trainee.organization
        ).count()

        completed_steps = Progress.objects.filter(
            trainee=trainee,
            step__recipe__organization=trainee.organization,
        )

        completed_count = completed_steps.count()

        overall_progress_rate = (
            round(completed_count / total_steps * 100)
            if total_steps > 0
            else 0
        )

        thirty_days_ago = timezone.now() - timedelta(days=30)

        recent_recipe_progresses = []

        for recipe in recipes:
            recent_progresses = completed_steps.filter(
                step__recipe=recipe,
                passed_at__gte=thirty_days_ago,
            ).order_by("passed_at")

            if recent_progresses.exists():
                oldest_progress = recent_progresses.first()
                latest_progress = recent_progresses.last()

                recent_recipe_progresses.append(
                    {
                        "recipe": recipe,
                        "oldest_progress": oldest_progress,
                        "latest_progress": latest_progress,
                    }
                )

        recipe_progresses = []

        for recipe in recipes:
            steps = Step.objects.filter(
                recipe=recipe
            ).order_by("order")

            recipe_total_count = steps.count()

            recipe_completed_step_ids = completed_steps.filter(
                step__recipe=recipe
            ).values_list("step_id", flat=True)

            recipe_completed_count = len(recipe_completed_step_ids)

            recipe_progress_rate = (
                round(recipe_completed_count / recipe_total_count * 100)
                if recipe_total_count > 0
                else 0
            )

            step_items = []

            for step in steps:
                is_completed = step.id in recipe_completed_step_ids

                step_items.append(
                    {
                        "step": step,
                        "is_completed": is_completed,
                    }
                )

            recipe_progresses.append(
                {
                    "recipe": recipe,
                    "progress_rate": recipe_progress_rate,
                    "steps": step_items,
                }
            )

        recipe_progresses.sort(key=lambda x: x["progress_rate"])

        context["overall_progress_rate"] = overall_progress_rate
        context["recent_recipe_progresses"] = recent_recipe_progresses
        context["recipe_progresses"] = recipe_progresses

        return context
    
    
class AccountView(LoginRequiredMixin, TemplateView):
    template_name = "app/account.html"
    
class AccountUsernameUpdateView(LoginRequiredMixin,TemplateView):
    template_name = (
        "app/account_username_update.html"
    )

    def get_context_data(
        self,
        **kwargs
    ):
        context = super().get_context_data(
            **kwargs
        )

        context["current_username"] = (
            self.request.user.username
        )

        return context

    def post(
        self,
        request,
        *args,
        **kwargs
    ):
        username = request.POST.get(
            "username"
        )

        if User.objects.filter(
            username=username
        ).exclude(
            id=request.user.id
        ).exists():
            return render(
                request,
                self.template_name,
                {
                    "error":
                    "この名前はすでに登録されています。",
                    "current_username":
                    request.user.username,
                },
            )

        request.user.username = username
        request.user.save()

        return redirect("account")


class AccountEmailUpdateView(LoginRequiredMixin,TemplateView):
    template_name = (
        "app/account_email_update.html"
    )

    def get_context_data(
        self,
        **kwargs
    ):
        context = super().get_context_data(
            **kwargs
        )

        context["current_email"] = (
            self.request.user.email
        )

        return context

    def post(
        self,
        request,
        *args,
        **kwargs
    ):
        email = request.POST.get(
            "email"
        )

        if User.objects.filter(
            email=email
        ).exclude(
            id=request.user.id
        ).exists():
            return render(
                request,
                self.template_name,
                {
                    "error":
                    "このメールアドレスはすでに登録されています。",
                    "current_email":
                    request.user.email,
                },
            )

        request.user.email = email
        request.user.save()

        return redirect("account")
    
class LogoutRedirectView(TemplateView):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect("login")
    
    
def is_valid_password(password):
    if password is None:
        return False

    if len(password) < 8:
        return False

    has_alpha = any(char.isalpha() for char in password)
    has_digit = any(char.isdigit() for char in password)

    return has_alpha and has_digit
    
    
class AdminRegisterView(TemplateView):
    template_name = "app/admin_register.html"

    def post(self, request, *args, **kwargs):
        organization_name = request.POST.get(
            "organization_name"
        )

        username = request.POST.get(
            "username"
        )

        email = request.POST.get(
            "email"
        )

        password = request.POST.get(
            "password"
        )

        password_confirm = request.POST.get(
            "password_confirm"
        )

        if password != password_confirm:
            return render(
                request,
                self.template_name,
                {
                    "error":
                    "パスワードが一致しません。"
                },
            )
        try:
            validate_password(password)
        except ValidationError as error:
            return render(
                request,
                self.template_name,
                {
                    "error":
                     error.messages[0],
                },
            )
            
        if Organization.objects.filter(name=organization_name).exists():
            return render(
                request,
                self.template_name,
                {
                    "error": 
                    "この組織名はすでに登録されています。",
                },
            )

        if User.objects.filter(username=username).exists():
            return render(
                request,
                self.template_name,
                {
                    "error": 
                    "この名前はすでに登録されています。",
                },
            )

        if User.objects.filter(email=email).exists():
            return render(
                request,
                self.template_name,
                {
                    "error": 
                    "このメールアドレスはすでに登録されています。",
                },
            )

        organization_code = str(
            uuid.uuid4()
        )[:8]

        organization = Organization.objects.create(
            name=organization_name,
            organization_code=organization_code,
        )

        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=2,
            organization=organization,
        )

        request.session["organization_code"] = (
            organization.organization_code
        )

        request.session["organization_code"] = organization.organization_code

        return redirect(
            "admin_register_done"
        )
        
        
class AdminRegisterDoneView(TemplateView):
    template_name = "app/admin_register_done.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["organization_code"] = self.request.session.get(
            "organization_code"
        )

        return context
    
    
class GeneralRegisterView(TemplateView):
    template_name = "app/general_register.html"

    def post(self, request, *args, **kwargs):
        organization_code = request.POST.get("organization_code")
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")

        organization = Organization.objects.filter(
            organization_code=organization_code
        ).first()

        if organization is None:
            return render(
                request,
                self.template_name,
                {
                    "error": "組織コードが正しくありません。",
                },
            )

        if password != password_confirm:
            return render(
                request,
                self.template_name,
                {
                    "error": "パスワードが一致しません。",
                },
            )

        try:
            validate_password(password)
        except ValidationError as error:
            return render(
                request,
                self.template_name,
                {
                    "error": error.messages[0],
                },
            )

        if User.objects.filter(username=username).exists():
            return render(
                request,
                self.template_name,
                {
                    "error": "この名前はすでに登録されています。",
                },
            )

        if User.objects.filter(email=email).exists():
            return render(
                request,
                self.template_name,
                {
                    "error": "このメールアドレスはすでに登録されています。",
                },
            )

        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=0,
            organization=organization,
        )

        return redirect("general_register_done")
    
    
class GeneralRegisterDoneView(TemplateView):
    template_name = "app/general_register_done.html"
