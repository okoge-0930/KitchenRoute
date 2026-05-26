from django.urls import path
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
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("login/", LoginView.as_view(), name="login"),
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
    "skill-management/recipes/<int:recipe_id>/delete/",
    RecipeDeleteView.as_view(),
    name="recipe_delete",
),
    path(
    "users/<int:user_id>/change-role/<int:role>/",
    ChangeUserRoleView.as_view(),
    name="change_user_role",
),
]