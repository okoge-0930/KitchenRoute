from django.urls import path
from .views import LoginView, HomeView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("", HomeView.as_view(), name="home"),
]