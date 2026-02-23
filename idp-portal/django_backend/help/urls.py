from django.urls import path

from help.views import get_help_topic

urlpatterns = [
    path('help/<str:topic_id>/', get_help_topic, name='help-topic'),
]
