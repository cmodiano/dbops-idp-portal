"""
AuditService for audit log business logic.
Handles creation of immutable audit entries with context enrichment.
"""

import csv
import logging
from datetime import datetime
from io import StringIO
from django.db.models import Q
from core.models import AuditLog, AuditActionType, AuditEntityType

logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for audit log business logic.
    Handles creation of immutable audit entries with context enrichment.
    """
    
    @staticmethod
    def create_entry(user_id: str, action_type: str, entity_type: str, 
                     entity_id: int, details: dict | None = None, 
                     ip_address: str | None = None, correlation_id: str | None = None):
        """
        Create a new audit log entry (immutable).
        
        Args:
            user_id: ID of the user performing the action
            action_type: Type of action (ACTION_CREATED, etc.)
            entity_type: Type of entity (action, execution, etc.)
            entity_id: ID of the entity
            details: Optional JSON details about the action
            ip_address: Optional IP address of the user
            correlation_id: Optional correlation ID
        
        Returns:
            AuditLog instance
        """
        return AuditLog.objects.create_entry(
            user_id=user_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
            correlation_id=correlation_id,
        )
    
    @staticmethod
    def list_all(user_id: str | None = None, action_type: str | None = None,
                entity_type: str | None = None, entity_id: int | None = None,
                date_from: datetime | None = None, date_to: datetime | None = None,
                page: int = 1, page_size: int = 25):
        """
        List all audit entries with pagination and filters.
        
        Args:
            user_id: Filter by user ID
            action_type: Filter by action type
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            date_from: Filter by timestamp >= date_from
            date_to: Filter by timestamp <= date_to
            page: Page number (1-based)
            page_size: Number of items per page
        
        Returns:
            Tuple of (list of audit entries, total count)
        """
        queryset = AuditLog.objects.all()
        
        # Apply filters
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        if entity_id:
            queryset = queryset.filter(entity_id=entity_id)
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        # Order by timestamp DESC
        queryset = queryset.order_by('-timestamp')
        
        # Pagination
        total_count = queryset.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        results = list(queryset[start_index:end_index])
        
        return results, total_count
    
    @staticmethod
    def get_by_entity(entity_type: str, entity_id: int):
        """
        Get audit entries for a specific entity (history trace).
        
        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
        
        Returns:
            QuerySet of audit entries for the entity, ordered by timestamp DESC
        """
        return AuditLog.objects.list_by_entity(entity_type, entity_id)
    
    @staticmethod
    def export_to_csv(user_id: str | None = None, action_type: str | None = None,
                     entity_type: str | None = None, date_from: datetime | None = None,
                     date_to: datetime | None = None):
        """
        Export audit entries to CSV format.
        
        Args:
            user_id: Optional filter by user ID
            action_type: Optional filter by action type
            entity_type: Optional filter by entity type
            date_from: Optional filter by date_from
            date_to: Optional filter by date_to
        
        Returns:
            StringIO buffer with CSV content
        """
        queryset = AuditLog.objects.all()
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        queryset = queryset.order_by('-timestamp')
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Timestamp', 'User ID', 'Action Type', 'Entity Type', 'Entity ID', 'IP Address', 'Details'])
        
        # Write rows
        for entry in queryset:
            writer.writerow([
                entry.timestamp.isoformat(),
                entry.user_id,
                entry.action_type,
                entry.entity_type,
                entry.entity_id,
                entry.ip_address or '',
                entry.details or '',
            ])
        
        output.seek(0)
        return output
    
    @staticmethod
    def export_to_pdf(user_id: str | None = None, action_type: str | None = None,
                      entity_type: str | None = None, date_from: datetime | None = None,
                      date_to: datetime | None = None):
        """
        Export audit entries to PDF format.
        Note: This is a placeholder - full PDF generation would require a library like reportlab.
        
        Args:
            user_id: Optional filter by user ID
            action_type: Optional filter by action type
            entity_type: Optional filter by entity type
            date_from: Optional filter by date_from
            date_to: Optional filter by date_to
        
        Returns:
            BytesIO buffer with PDF content (placeholder implementation)
        
        Raises:
            NotImplementedError: PDF export requires reportlab library
        """
        # Placeholder - would require reportlab or similar library
        raise NotImplementedError("PDF export requires reportlab library. Use export_to_csv() for now.")
