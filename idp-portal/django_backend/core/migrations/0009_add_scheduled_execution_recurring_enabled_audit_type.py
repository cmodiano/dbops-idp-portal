# Generated manually for story 66-16 review — adds SCHEDULED_EXECUTION_RECURRING_ENABLED to AuditActionType
# Rationale: SCHEDULED_EXECUTION_RECURRING_CREATED is semantically reserved for new pattern INSERT;
# a dedicated ENABLED type is required for toggle re-activation of an existing pattern.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_add_iac_sync_tracking"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action_type",
            field=models.CharField(
                choices=[
                    ("ACTION_CREATED", "Action Created"),
                    ("ACTION_UPDATED", "Action Updated"),
                    ("ACTION_PUBLISHED", "Action Published"),
                    ("ACTION_DISABLED", "Action Disabled"),
                    (
                        "ACTION_DISABLED_INTEGRATION_DELETED",
                        "Action Disabled - Integration Deleted",
                    ),
                    ("ACTION_ENABLED", "Action Enabled"),
                    ("ACTION_DELETED", "Action Deleted"),
                    ("ACTION_DEACTIVATED", "Action Deactivated"),
                    ("ACTION_REACTIVATED", "Action Reactivated"),
                    ("PROFILE_CREATED", "Profile Created"),
                    ("PROFILE_UPDATED", "Profile Updated"),
                    ("PROFILE_DELETED", "Profile Deleted"),
                    ("INTEGRATION_CREATED", "Integration Created"),
                    ("INTEGRATION_UPDATED", "Integration Updated"),
                    ("INTEGRATION_DELETED", "Integration Deleted"),
                    ("EXECUTION_SUBMITTED", "Execution Submitted"),
                    ("EXECUTION_STARTED", "Execution Started"),  # Legacy: in Oracle constraint
                    ("EXECUTION_INTEGRATION_ERROR", "Execution Integration Error"),
                    ("EXECUTION_RUNNING", "Execution Running"),
                    ("EXECUTION_COMPLETED", "Execution Completed"),
                    ("EXECUTION_FAILED", "Execution Failed"),
                    ("EXECUTION_CANCELLED", "Execution Cancelled"),
                    ("EXECUTION_PENDING_APPROVAL", "Execution Pending Approval"),
                    ("EXECUTION_APPROVED", "Execution Approved"),
                    ("EXECUTION_REJECTED", "Execution Rejected"),
                    ("EXECUTION_TARGET_FORBIDDEN", "Execution Target Forbidden"),
                    ("SCHEDULED_EXECUTION_CREATED", "Scheduled Execution Created"),
                    (
                        "SCHEDULED_EXECUTION_RECURRING_CREATED",
                        "Scheduled Execution Recurring Created",
                    ),
                    ("SCHEDULED_EXECUTION_EXECUTED", "Scheduled Execution Executed"),
                    ("SCHEDULED_EXECUTION_CANCELLED", "Scheduled Execution Cancelled"),
                    (
                        "SCHEDULED_EXECUTION_RECURRING_DISABLED",
                        "Scheduled Execution Recurring Disabled",
                    ),
                    # story 66-16 review: ENABLED for toggle re-activation (distinct from CREATED)
                    (
                        "SCHEDULED_EXECUTION_RECURRING_ENABLED",
                        "Scheduled Execution Recurring Enabled",
                    ),
                    (
                        "SCHEDULED_EXECUTION_CELERY_TRIGGERED",
                        "Scheduled Execution Celery Triggered",
                    ),
                    ("USER_CREATED", "User Created"),
                    ("USER_UPDATED", "User Updated"),
                    ("USER_LOGIN", "User Login"),
                    ("USER_LOGOUT", "User Logout"),
                    ("USER_REFRESH", "User Refresh Token"),
                    ("API_KEY_TOKEN_EXCHANGE", "API Key Token Exchange"),
                    ("SERVICE_LOGIN", "Service Account Login"),
                    ("AUTH_DEV_BYPASS_LOGIN", "Dev Bypass Authentication"),
                    ("FAVORITE_ADDED", "Favorite Added"),
                    ("FAVORITE_REMOVED", "Favorite Removed"),
                    ("EXECUTION_STEP_RETRY_ATTEMPT", "Execution Step Retry Attempt"),
                    ("EXECUTION_STEP_RETRY_SUCCESS", "Execution Step Retry Success"),
                    (
                        "EXECUTION_STEP_RETRY_EXHAUSTED",
                        "Execution Step Retry Exhausted",
                    ),
                    ("EXECUTION_STEP_RETRY_ABORTED", "Execution Step Retry Aborted"),
                    ("EXECUTION_STEP_WAITING", "Execution Step Waiting"),
                    ("EXECUTION_STEP_GATE_SATISFIED", "Execution Step Gate Satisfied"),
                    ("EXECUTION_STEP_GATE_TIMEOUT", "Execution Step Gate Timeout"),
                    ("FEATURE_FLAG_UPDATED", "Feature Flag Updated"),
                    ("FEATURE_FLAG_CREATED", "Feature Flag Created"),
                    ("PROFILE_UPDATE_REJECTED", "Profile Update Rejected"),
                    ("INTEGRATION_TYPE_CREATED", "Integration Type Created"),
                    ("INTEGRATION_TYPE_UPDATED", "Integration Type Updated"),
                    ("INTEGRATION_ACTION_CREATED", "Integration Action Created"),
                    ("INTEGRATION_ACTION_UPDATED", "Integration Action Updated"),
                    ("INTEGRATION_STATUS_UPDATED", "Integration Status Updated"),
                    (
                        "INTEGRATION_HEALTH_CHECK_TESTED",
                        "Integration Health Check Tested",
                    ),
                    ("INTEGRATION_MARKED_LEGACY", "Integration Marked Legacy"),
                    (
                        "EXECUTION_BLOCKED_INVALID_INTEGRATION",
                        "Execution Blocked Invalid Integration",
                    ),
                    (
                        "EXECUTION_DEPRECATED_INTEGRATION_WARNING",
                        "Execution Deprecated Integration Warning",
                    ),
                    (
                        "WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION",
                        "Workflow Step Blocked Invalid Integration",
                    ),
                    (
                        "EXECUTION_STEP_POLICY_APPROVAL_REQUIRED",
                        "Execution Step Policy Approval Required",
                    ),
                    (
                        "EXECUTION_STEP_POLICY_AUTO_APPROVED",
                        "Execution Step Policy Auto Approved",
                    ),
                    (
                        "EXECUTION_STEP_POLICY_EVALUATION_FAILED",
                        "Execution Step Policy Evaluation Failed",
                    ),
                    ("WORKFLOW_STEP_SCHEDULE_CREATED", "Workflow Step Schedule Created"),
                    ("POLICY_CREATED", "Policy Created"),
                    ("POLICY_UPDATED", "Policy Updated"),
                    ("POLICY_DELETED", "Policy Deleted"),
                    ("EXECUTION_POLLING_EXHAUSTED", "Execution Polling Exhausted"),
                ],
                db_column="ACTION_TYPE",
                max_length=50,
            ),
        ),
    ]
