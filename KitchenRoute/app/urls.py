from django.urls import path
from .views import (
    LoginView,
    HomeView,
    EducatorHomeView,
    TraineeHomeView,
    AdminHomeView,
    TraineeDetailView,
    MarkStepPassedView,
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
]