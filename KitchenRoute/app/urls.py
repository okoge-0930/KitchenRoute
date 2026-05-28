from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    LoginView,
    HomeView,
    EducatorHomeView,
    TraineeHomeView,
    AdminHomeView,
    TraineeDetailView,
    MarkStepPassedView,
    SkillManagementView,
    StepManagementView,
    RecipeCreateView,
    StepCreateView,
    StepUpdateView,
    StepDeleteView,
    RecipeDeleteView,
    ChangeUserRoleView,
    TraineeTaskDetailView,
    MyProgressView,
    AccountView,
    LogoutRedirectView,
    RecipeUpdateView,
    AdminRegisterView,
    AdminRegisterDoneView,
    GeneralRegisterView,
    GeneralRegisterDoneView,
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutRedirectView.as_view(), name="logout"),
    path("educator-home/", EducatorHomeView.as_view(), name="educator_home"),
    path("trainee-home/", TraineeHomeView.as_view(), name="trainee_home"),
    path("admin-home/", AdminHomeView.as_view(), name="admin_home"),
    path("trainees/<int:user_id>/", TraineeDetailView.as_view(), name="trainee_detail"),
    path(
    "trainees/<int:user_id>/steps/<int:step_id>/pass/",
    MarkStepPassedView.as_view(),
    name="mark_step_passed",
    ),
    path("skill-management/", SkillManagementView.as_view(), name="skill_management"),
    path(
    "skill-management/recipes/<int:recipe_id>/",
    StepManagementView.as_view(),
    name="step_management",
),
    path("skill-management/recipes/create/", RecipeCreateView.as_view(), name="recipe_create"),
    path(
    "skill-management/recipes/<int:recipe_id>/steps/create/",
    StepCreateView.as_view(),
    name="step_create",
),
    path(
    "skill-management/steps/<int:step_id>/edit/",
    StepUpdateView.as_view(),
    name="step_update",
),
    path(
    "skill-management/steps/<int:step_id>/delete/",
    StepDeleteView.as_view(),
    name="step_delete",
),
    path(
    "skill-management/recipes/<int:recipe_id>/edit/",
    RecipeUpdateView.as_view(),
    name="recipe_update",
),
    path(
    "skill-management/recipes/<int:recipe_id>/delete/",
    RecipeDeleteView.as_view(),
    name="recipe_delete",
),
    path(
    "users/<int:user_id>/change-role/<int:role>/",
    ChangeUserRoleView.as_view(),
    name="change_user_role",
),
    path(
    "trainee/tasks/<int:recipe_id>/",
    TraineeTaskDetailView.as_view(),
    name="trainee_task_detail",
),
    path("my-progress/", MyProgressView.as_view(), name="my_progress"),
    path("account/", AccountView.as_view(), name="account"),
    path(
    "register/admin/",
    AdminRegisterView.as_view(),
    name="admin_register",
),
    path(
    "register/admin/done/",
    AdminRegisterDoneView.as_view(),
    name="admin_register_done",
),
    path(
    "register/general/",
    GeneralRegisterView.as_view(),
    name="general_register",
),
    path(
    "register/general/done/",
    GeneralRegisterDoneView.as_view(),
    name="general_register_done",
),
    path(
    "password-reset/",
    auth_views.PasswordResetView.as_view(
        template_name="app/password_reset.html",
        email_template_name="app/password_reset_email.txt",
        success_url="/password-reset/done/",
    ),
    name="password_reset",
),
path(
    "password-reset/done/",
    auth_views.PasswordResetDoneView.as_view(
        template_name="app/password_reset_done.html",
    ),
    name="password_reset_done",
),
path(
    "reset/<uidb64>/<token>/",
    auth_views.PasswordResetConfirmView.as_view(
        template_name="app/password_reset_confirm.html",
        success_url="/reset/done/",
    ),
    name="password_reset_confirm",
),

path(
    "reset/done/",
    auth_views.PasswordResetCompleteView.as_view(
        template_name="app/password_reset_complete.html",
    ),
    name="password_reset_complete",
),
]