import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from app.core.report_storage import ReportStorage
from app.models.schemas import AuditReport, AuditRequest, AuditSummary

pytestmark = pytest.mark.unit

@pytest.fixture
def mock_simple_report():
    return AuditReport(
        request=AuditRequest(url="https://test.com"),
        summary=AuditSummary(
            total_issues=0, by_severity={}, by_source={}, by_wcag_level={}, score=100.0, confidence_avg=1.0
        ),
        issues=[]
    )

@pytest.mark.asyncio
async def test_init_no_url():
    with patch("app.core.config.settings.database_url", ""):
        storage = ReportStorage()
        await storage.initialize()
        assert storage._conn is None

@pytest.mark.asyncio
async def test_init_postgres_url():
    with patch("app.core.config.settings.database_url", "postgresql://user:pass@localhost/db"):
        with patch("aiosqlite.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = AsyncMock()
            storage = ReportStorage()
            await storage.initialize()
            assert storage._conn is not None
            mock_connect.assert_called_with("accesslens.db")

@pytest.mark.asyncio
async def test_save_report_no_conn(mock_simple_report):
    storage = ReportStorage()
    storage._conn = None
    saved_id = await storage.save_report(mock_simple_report)
    assert saved_id == mock_simple_report.id
    assert mock_simple_report.id in storage._in_memory_store

@pytest.mark.asyncio
async def test_save_report_exception_fallback(mock_simple_report):
    storage = ReportStorage()
    storage._conn = MagicMock()
    storage._conn.execute.side_effect = Exception("DB Error")
    
    saved_id = await storage.save_report(mock_simple_report)
    assert saved_id == mock_simple_report.id
    assert mock_simple_report.id in storage._in_memory_store

@pytest.mark.asyncio
async def test_get_report_no_conn(mock_simple_report):
    storage = ReportStorage()
    storage._conn = None
    assert await storage.get_report("missing") is None

@pytest.mark.asyncio
async def test_get_report_exception():
    storage = ReportStorage()
    storage._conn = MagicMock()
    storage._conn.execute.side_effect = Exception("DB Error")
    
    assert await storage.get_report("missing") is None
