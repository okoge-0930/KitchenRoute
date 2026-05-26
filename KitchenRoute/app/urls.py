from django.urls import path
from .views import (
    LoginView,
    HomeView,
    EducatorHomeView,
    TraineeHomeView,
    AdminHomeView,
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("login/", LoginView.as_view(), name="login"),
    path("educator-home/", EducatorHomeView.as_view(), name="educator_home"),
    path("trainee-home/", TraineeHomeView.as_view(), name="trainee_home"),
    path("admin-home/", AdminHomeView.as_view(), name="admin_home"),
]