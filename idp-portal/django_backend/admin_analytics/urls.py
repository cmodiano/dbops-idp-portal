"""
URL configuration for admin analytics endpoints.
Used by frontend AdminAnalyticsDashboard.
"""

from django.urls import path

from admin_analytics import views

app_name = "admin_analytics"

urlpatterns = [
    path("analytics/", views.AdminAnalyticsView.as_view(), name="admin-analytics"),
]

