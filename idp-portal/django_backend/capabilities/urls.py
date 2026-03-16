# capabilities/urls.py
from django.urls import path
from capabilities.views import get_integrations_capabilities, get_workflow_steps_capabilities

app_name = 'capabilities'

urlpatterns = [
    path(
        'capabilities/integrations/',
        get_integrations_capabilities,
        name='capabilities-integrations',
    ),
    path(
        'capabilities/workflow-steps/',
        get_workflow_steps_capabilities,
        name='capabilities-workflow-steps',
    ),
]
