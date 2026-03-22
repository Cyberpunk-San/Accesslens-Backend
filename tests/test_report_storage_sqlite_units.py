import pytest
pytestmark = pytest.mark.unit

import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch
from app.core.report_storage import ReportStorage
from app.models.schemas import AuditReport, AuditRequest, AuditSummary, UnifiedIssue, IssueSeverity, ConfidenceLevel, IssueSource

@pytest.fixture
async def sqlite_storage():
    with patch("app.core.config.settings.database_url", "sqlite:///:memory:"):
        storage = ReportStorage()
        await storage.initialize()
        yield storage
        await storage.close()

@pytest.fixture
def mock_report_full():
    report_id = str(uuid4())
    request = AuditRequest(url="https://example.com")
    summary = AuditSummary(
        total_issues=1,
        by_severity={"critical": 1, "serious": 0, "moderate": 0, "minor": 0},
        by_source={"wcag_deterministic": 1},
        by_wcag_level={"AA": 1},
        score=85,
        confidence_avg=0.9,
        error=None
    )
    issue = UnifiedIssue(
        id=str(uuid4()),
        title="Test Issue",
        description="A test issue",
        issue_type="test",
        severity=IssueSeverity.CRITICAL,
        confidence=ConfidenceLevel.HIGH,
        confidence_score=95.0,
        source=IssueSource.WCAG_DETERMINISTIC,
        engine_name="test_engine"
    )
    return AuditReport(
        id=report_id,
        request=request,
        timestamp=datetime.now(timezone.utc),
        summary=summary,
        issues=[issue],
        metadata={"test": "data"},
        accessibility_tree={"node": "root"}
    )

@pytest.mark.asyncio
async def test_sqlite_save_and_get(sqlite_storage, mock_report_full):
    # Save
    saved_id = await sqlite_storage.save_report(mock_report_full)
    assert saved_id == mock_report_full.id
    
    # Get
    retrieved = await sqlite_storage.get_report(mock_report_full.id)
    assert retrieved is not None
    assert retrieved.id == mock_report_full.id
    assert len(retrieved.issues) == 1
    assert retrieved.issues[0].title == "Test Issue"
    assert retrieved.accessibility_tree == {"node": "root"}
    assert retrieved.metadata == {"test": "data"}

@pytest.mark.asyncio
async def test_sqlite_list_reports(sqlite_storage, mock_report_full):
    await sqlite_storage.save_report(mock_report_full)
    
    # Filter by URL
    reports = await sqlite_storage.list_reports(url="https://example.com")
    assert len(reports) == 1
    assert reports[0]["url"] == "https://example.com"
    
    reports = await sqlite_storage.list_reports(url="https://other.com")
    assert len(reports) == 0

    # Filter by score
    reports = await sqlite_storage.list_reports(min_score=80.0)
    assert len(reports) == 1

    reports = await sqlite_storage.list_reports(min_score=90.0)
    assert len(reports) == 0

@pytest.mark.asyncio
async def test_sqlite_stats_and_delete(sqlite_storage, mock_report_full):
    await sqlite_storage.save_report(mock_report_full)
    
    stats = await sqlite_storage.get_report_stats()
    assert stats["total_reports"] == 1
    assert stats["avg_score"] == 85.0
    
    await sqlite_storage.get_url_history("https://example.com")
    
    deleted = await sqlite_storage.delete_report(mock_report_full.id)
    assert deleted is True
    
    stats_after = await sqlite_storage.get_report_stats()
    assert stats_after["total_reports"] == 0

@pytest.mark.asyncio
async def test_sqlite_cleanup_old_reports(sqlite_storage, mock_report_full):
    from datetime import timedelta
    mock_report_full.timestamp = datetime.now(timezone.utc) - timedelta(days=40)
    await sqlite_storage.save_report(mock_report_full)
    
    deleted_count = await sqlite_storage.cleanup_old_reports(days=30)
    assert deleted_count == 1
    
    reports = await sqlite_storage.list_reports()
    assert len(reports) == 0

@pytest.mark.asyncio
async def test_sqlite_init_failure():
    with patch("app.core.config.settings.database_url", "sqlite:///:invalid:/path/db.sqlite"):
        storage = ReportStorage()
        await storage.initialize()
        assert storage._conn is None
