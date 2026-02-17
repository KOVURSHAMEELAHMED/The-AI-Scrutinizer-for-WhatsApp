from django.urls import path
from . import views

urlpatterns = [
    path("webhook/", views.webhook, name="webhook"),
    path("health/", views.health_check, name="health"),
    path("stats/", views.stats, name="stats"),
]
