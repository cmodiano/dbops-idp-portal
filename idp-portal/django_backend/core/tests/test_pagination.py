"""Tests unitaires pour core.pagination.paginate_queryset().

Story 26.11 (AC4): 8+ tests couvrant tous les cas limites.
"""
import pytest

from core.pagination import paginate_queryset
from executions.models import Execution
from tests.factories import ExecutionFactory


@pytest.fixture
def sample_executions(db):
    """Create 100 sample executions for pagination tests."""
    return ExecutionFactory.create_batch(100)


class TestPaginateQueryset:
    """Tests for paginate_queryset() utility."""

    def test_first_page(self, sample_executions):
        """offset=0, limit=25 on 100 items → page 1 of 4."""
        qs = Execution.objects.all().order_by("id")
        result = paginate_queryset(qs, offset=0, limit=25)

        assert isinstance(result["items"], list)
        assert len(result["items"]) == 25
        assert result["items"][0].id == sample_executions[0].id

        pagination = result["pagination"]
        assert pagination["page"] == 1
        assert pagination["page_size"] == 25
        assert pagination["total"] == 100
        assert pagination["total_pages"] == 4

    def test_middle_page(self, sample_executions):
        """offset=50, limit=25 on 100 items → page 3 of 4."""
        qs = Execution.objects.all().order_by("id")
        result = paginate_queryset(qs, offset=50, limit=25)

        assert len(result["items"]) == 25
        assert result["pagination"]["page"] == 3
        assert result["pagination"]["total"] == 100
        assert result["pagination"]["total_pages"] == 4

    def test_last_page_partial(self, db):
        """93 items, offset=75, limit=25 → page 4 of 4, 18 items."""
        ExecutionFactory.create_batch(93)
        qs = Execution.objects.all().order_by("id")
        result = paginate_queryset(qs, offset=75, limit=25)

        assert len(result["items"]) == 18
        assert result["pagination"]["page"] == 4
        assert result["pagination"]["total"] == 93
        assert result["pagination"]["total_pages"] == 4

    def test_empty_queryset(self, db):
        """0 items → page 1, total_pages=1, items=[]."""
        qs = Execution.objects.none()
        result = paginate_queryset(qs, offset=0, limit=25)

        assert result["items"] == []
        assert result["pagination"]["page"] == 1
        assert result["pagination"]["total"] == 0
        assert result["pagination"]["total_pages"] == 1

    def test_offset_beyond_total(self, db):
        """50 items, offset=100 → empty items, pagination still calculated."""
        ExecutionFactory.create_batch(50)
        qs = Execution.objects.all().order_by("id")
        result = paginate_queryset(qs, offset=100, limit=25)

        assert result["items"] == []
        assert result["pagination"]["page"] == 5
        assert result["pagination"]["total"] == 50
        assert result["pagination"]["total_pages"] == 2

    def test_limit_larger_than_total(self, db):
        """10 items, offset=0, limit=50 → all items, 1 page."""
        ExecutionFactory.create_batch(10)
        qs = Execution.objects.all().order_by("id")
        result = paginate_queryset(qs, offset=0, limit=50)

        assert len(result["items"]) == 10
        assert result["pagination"]["page"] == 1
        assert result["pagination"]["total"] == 10
        assert result["pagination"]["total_pages"] == 1

    def test_exact_page_boundary(self, sample_executions):
        """100 items, offset=0, limit=50 → page 1 of exactly 2."""
        qs = Execution.objects.all().order_by("id")
        result = paginate_queryset(qs, offset=0, limit=50)

        assert len(result["items"]) == 50
        assert result["pagination"]["page"] == 1
        assert result["pagination"]["total_pages"] == 2

    def test_preserves_queryset_order(self, sample_executions):
        """Items respect queryset order_by()."""
        qs = Execution.objects.all().order_by("-id")
        result = paginate_queryset(qs, offset=0, limit=25)

        ids = [item.id for item in result["items"]]
        assert ids == sorted(ids, reverse=True)

    # Code Review Fix (HIGH-3): Input validation tests
    def test_negative_offset_raises_value_error(self, db):
        """offset < 0 → ValueError."""
        qs = Execution.objects.all()
        with pytest.raises(ValueError, match="offset must be >= 0"):
            paginate_queryset(qs, offset=-10, limit=25)

    def test_zero_limit_raises_value_error(self, db):
        """limit = 0 → ValueError (prevents ZeroDivisionError)."""
        qs = Execution.objects.all()
        with pytest.raises(ValueError, match="limit must be > 0"):
            paginate_queryset(qs, offset=0, limit=0)

    def test_negative_limit_raises_value_error(self, db):
        """limit < 0 → ValueError."""
        qs = Execution.objects.all()
        with pytest.raises(ValueError, match="limit must be > 0"):
            paginate_queryset(qs, offset=0, limit=-5)
