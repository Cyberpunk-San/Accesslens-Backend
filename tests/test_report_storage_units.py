# tests/test_report_storage_units.py

import pytest
pytestmark = pytest.mark.unit

from datetime import datetime
from uuid import uuid4
from app.core.report_storage import ReportStorage
from app.models.schemas import AuditReport, AuditRequest, AuditSummary

class TestReportStorageUnits:
    @pytest.fixture
    def storage(self):
        # By default, ReportStorage uses in-memory if no DB url
        return ReportStorage()

    @pytest.fixture
    def mock_report(self):
        report_id = str(uuid4())
        request = AuditRequest(url="https://example.com")
        summary = AuditSummary(
            total_issues=1,
            by_severity={"critical": 1, "serious": 0, "moderate": 0, "minor": 0},
            by_source={"wcag_deterministic": 1},
            by_wcag_level={"AA": 1},
            score=85,
            confidence_avg=0.9
        )
        return AuditReport(
            id=report_id,
            request=request,
            timestamp=datetime.now(),
            summary=summary,
            issues=[],
            metadata={}
        )

    @pytest.mark.asyncio
    async def test_in_memory_save_and_get(self, storage, mock_report):
        await storage.save_report(mock_report)
        retrieved = await storage.get_report(mock_report.id)
        assert retrieved == mock_report
        assert retrieved.id == mock_report.id

    @pytest.mark.asyncio
    async def test_in_memory_list_and_delete(self, storage, mock_report):
        await storage.save_report(mock_report)
        reports = await storage.list_reports(limit=10)
        assert len(reports) == 1
        assert reports[0]["id"] == mock_report.id
        
        await storage.delete_report(mock_report.id)
        reports_after = await storage.list_reports()
        assert len(reports_after) == 0

    @pytest.mark.asyncio
    async def test_in_memory_stats(self, storage, mock_report):
        await storage.save_report(mock_report)
        stats = await storage.get_report_stats()
        assert stats["total_reports"] == 1
        assert stats["avg_score"] == 85
        assert stats["total_issues"] == 1
        assert stats["unique_urls"] == 1

    @pytest.mark.asyncio
    async def test_in_memory_cleanup(self, storage, mock_report):
        # Set timestamp to 40 days ago
        import time
        from datetime import timedelta
        storage._in_memory_store[mock_report.id] = mock_report
        mock_report.timestamp = datetime.now() - timedelta(days=40)
        
        deleted_count = await storage.cleanup_old_reports(days=30)
        assert deleted_count == 1
        assert mock_report.id not in storage._in_memory_store

    @pytest.mark.asyncio
    async def test_close_no_pool(self, storage):
        # Should not raise error
        await storage.close()
