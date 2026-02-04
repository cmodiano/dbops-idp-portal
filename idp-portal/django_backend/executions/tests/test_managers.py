"""
Tests for executions managers (ExecutionManager, ScheduledExecutionManager).
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from idp_auth.models import User
from catalog.models import Action
from executions.models import Execution, ExecutionStatus, ScheduledExecution, ScheduledExecutionStatus


@pytest.mark.django_db
class TestExecutionManager(TestCase):
    """Tests for ExecutionManager."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='testuser', profile='DBA')
        self.action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status='published'
        )
    
    def test_list_by_user(self):
        """Test list_by_user() returns executions for specific user."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )
        
        results = Execution.objects.list_by_user(self.user.id)
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].id, execution.id)
    
    def test_list_by_status(self):
        """Test list_by_status() filters by status."""
        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )
        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.COMPLETED
        )
        
        submitted = Execution.objects.list_by_status(ExecutionStatus.SUBMITTED)
        self.assertEqual(submitted.count(), 1)
        
        completed = Execution.objects.list_by_status(ExecutionStatus.COMPLETED)
        self.assertEqual(completed.count(), 1)
    
    def test_get_recent(self):
        """Test get_recent() returns recent executions."""
        for i in range(5):
            Execution.objects.create(
                action=self.action,
                user=self.user,
                environment='dev',
                status=ExecutionStatus.COMPLETED
            )
        
        recent = Execution.objects.get_recent(limit=3)
        self.assertEqual(len(list(recent)), 3)
