
from typing import Optional, List, Dict, Any, Union
import aiosqlite
import json
import logging
import os
from datetime import datetime, timezone
from uuid import UUID
from ..models.schemas import AuditReport, UnifiedIssue, AuditRequest, AuditSummary
from ..core.config import settings

class ReportStorage:


    def __init__(self):
        self._conn: Optional[aiosqlite.Connection] = None
        self._logger = logging.getLogger(__name__)
        self._in_memory_store: Dict[str, AuditReport] = {}

    async def initialize(self):

        if not settings.database_url:
            self._logger.warning("No database URL configured, using in-memory storage")
            return

        db_path = settings.database_url
        if db_path.startswith("sqlite:///"):
            db_path = db_path.replace("sqlite:///", "")
        elif db_path.startswith("postgresql://"):
            self._logger.warning("PostgreSQL URL detected but switching to SQLite as requested. Using accesslens.db")
            db_path = "accesslens.db"

        try:
            self._conn = await aiosqlite.connect(db_path)
            self._conn.row_factory = aiosqlite.Row
            
            # Enable Foreign Keys
            await self._conn.execute("PRAGMA foreign_keys = ON")


            await self._create_tables()
            self._logger.info(f"SQLite database initialized at {db_path}")

        except Exception as e:
            self._logger.warning(f"Failed to initialize SQLite database (falling back to in-memory): {e}")
            self._conn = None

    async def _create_tables(self):

        if not self._conn:
            return

        # reports table
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                score FLOAT NOT NULL,
                summary TEXT NOT NULL,
                metadata TEXT NOT NULL,
                request TEXT NOT NULL
            )
        """)

        # issues table
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id TEXT PRIMARY KEY,
                report_id TEXT REFERENCES reports(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                issue_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence TEXT NOT NULL,
                confidence_score FLOAT NOT NULL,
                source TEXT NOT NULL,
                wcag_criteria TEXT,
                location TEXT,
                remediation TEXT,
                evidence TEXT,
                engine_name TEXT NOT NULL,
                tags TEXT
            )
        """)

        # accessibility_trees table
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS accessibility_trees (
                report_id TEXT PRIMARY KEY REFERENCES reports(id) ON DELETE CASCADE,
                tree_data TEXT NOT NULL
            )
        """)

        # Indices
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_url ON reports(url)")
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_timestamp ON reports(timestamp)")
        await self._conn.execute("CREATE INDEX IF NOT EXISTS idx_issues_report_id ON issues(report_id)")
        
        await self._conn.commit()
        self._logger.info("Database tables verified")

    async def save_report(self, report: AuditReport) -> str:

        if not self._conn:
            self._in_memory_store[report.id] = report
            self._logger.debug(f"Saved report {report.id} to in-memory storage")
            return report.id

        try:
            async with self._conn.execute("""
                INSERT INTO reports (id, url, timestamp, score, summary, metadata, request)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                str(report.id),
                report.request.url,
                report.timestamp.isoformat(),
                report.summary.score,
                json.dumps(report.summary.model_dump()),
                json.dumps(report.metadata),
                json.dumps(report.request.model_dump())
            )):
                pass


            for issue in report.issues:
                await self._conn.execute("""
                    INSERT INTO issues (
                        id, report_id, title, description, issue_type,
                        severity, confidence, confidence_score, source,
                        wcag_criteria, location, remediation, evidence,
                        engine_name, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(issue.id),
                    str(report.id),
                    issue.title,
                    issue.description,
                    issue.issue_type,
                    issue.severity.value,
                    issue.confidence.value,
                    issue.confidence_score,
                    issue.source.value,
                    json.dumps([c.model_dump() for c in issue.wcag_criteria]),
                    json.dumps(issue.location.model_dump() if issue.location else None),
                    json.dumps(issue.remediation.model_dump() if issue.remediation else None),
                    json.dumps(issue.evidence.model_dump() if issue.evidence else None),
                    issue.engine_name,
                    json.dumps(issue.tags)
                ))


            if report.accessibility_tree:
                await self._conn.execute("""
                    INSERT INTO accessibility_trees (report_id, tree_data)
                    VALUES (?, ?)
                """, (
                    str(report.id),
                    json.dumps(report.accessibility_tree)
                ))

            await self._conn.commit()
            self._logger.info(f"Saved report {report.id} to SQLite with {len(report.issues)} issues")
            return report.id

        except Exception as e:
            self._logger.error(f"Failed to save report to SQLite: {e}")
            self._in_memory_store[report.id] = report
            return report.id

    async def get_report(self, report_id: str) -> Optional[AuditReport]:

        if report_id in self._in_memory_store:
            return self._in_memory_store[report_id]

        if not self._conn:
            return None

        try:
            async with self._conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)) as cursor:
                report_row = await cursor.fetchone()

            if not report_row:
                return None

            async with self._conn.execute("SELECT * FROM issues WHERE report_id = ? ORDER BY severity, confidence_score", (report_id,)) as cursor:
                issue_rows = await cursor.fetchall()

            async with self._conn.execute("SELECT tree_data FROM accessibility_trees WHERE report_id = ?", (report_id,)) as cursor:
                tree_row = await cursor.fetchone()

            return await self._reconstruct_report(report_row, issue_rows, tree_row)

        except Exception as e:
            self._logger.error(f"Failed to retrieve report {report_id}: {e}")
            return None

    async def _reconstruct_report(self, report_row, issue_rows, tree_row) -> AuditReport:

        request_data = json.loads(report_row['request'])
        request = AuditRequest(**request_data)

        summary_data = json.loads(report_row['summary'])
        summary = AuditSummary(**summary_data)

        issues = []
        for row in issue_rows:
            wcag_criteria = json.loads(row['wcag_criteria']) if row['wcag_criteria'] else []
            location = json.loads(row['location']) if row['location'] else None
            remediation = json.loads(row['remediation']) if row['remediation'] else None
            evidence = json.loads(row['evidence']) if row['evidence'] else None
            tags = json.loads(row['tags']) if row['tags'] else []

            issue = UnifiedIssue(
                id=row['id'],
                title=row['title'],
                description=row['description'],
                issue_type=row['issue_type'],
                severity=row['severity'],
                confidence=row['confidence'],
                confidence_score=row['confidence_score'],
                source=row['source'],
                wcag_criteria=wcag_criteria,
                location=location,
                remediation=remediation,
                evidence=evidence,
                engine_name=row['engine_name'],
                tags=tags
            )
            issues.append(issue)

        accessibility_tree = json.loads(tree_row['tree_data']) if tree_row else None
        metadata = json.loads(report_row['metadata']) if report_row['metadata'] else {}

        return AuditReport(
            id=report_row['id'],
            request=request,
            timestamp=datetime.fromisoformat(report_row['timestamp']),
            summary=summary,
            issues=issues,
            accessibility_tree=accessibility_tree,
            metadata=metadata
        )

    async def list_reports(
        self,
        limit: int = 100,
        offset: int = 0,
        url: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        min_score: Optional[float] = None
    ) -> List[Dict[str, Any]]:

        if not self._conn:
            reports = list(self._in_memory_store.values())
            reports.sort(key=lambda x: x.timestamp, reverse=True)
            return [
                {
                    "id": r.id,
                    "url": r.request.url,
                    "timestamp": r.timestamp,
                    "score": r.summary.score,
                    "total_issues": r.summary.total_issues,
                    "critical_count": r.summary.by_severity.get("critical", 0),
                    "serious_count": r.summary.by_severity.get("serious", 0),
                    "moderate_count": r.summary.by_severity.get("moderate", 0),
                    "minor_count": r.summary.by_severity.get("minor", 0),
                    "avg_confidence": r.summary.confidence_avg,
                    "error": r.summary.error
                }
                for r in reports[offset:offset+limit]
            ]

        try:
            query = """
                SELECT 
                    id, url, timestamp, score,
                    COALESCE(json_extract(summary, '$.total_issues'), 0) as total_issues,
                    COALESCE(json_extract(summary, '$.by_severity.critical'), 0) as critical_count,
                    COALESCE(json_extract(summary, '$.by_severity.serious'), 0) as serious_count,
                    COALESCE(json_extract(summary, '$.by_severity.moderate'), 0) as moderate_count,
                    COALESCE(json_extract(summary, '$.by_severity.minor'), 0) as minor_count,
                    COALESCE(json_extract(summary, '$.confidence_avg'), 0) as avg_confidence,
                    json_extract(summary, '$.error') as error
                FROM reports 
                WHERE 1=1
            """
            params = []

            if url:
                query += " AND url = ?"
                params.append(url)

            if from_date:
                query += " AND timestamp >= ?"
                params.append(from_date.isoformat())

            if to_date:
                query += " AND timestamp <= ?"
                params.append(to_date.isoformat())

            if min_score is not None:
                query += " AND score >= ?"
                params.append(min_score)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            async with self._conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            self._logger.error(f"Failed to list reports from SQLite: {e}")
            return []

    async def delete_report(self, report_id: str) -> bool:

        if report_id in self._in_memory_store:
            del self._in_memory_store[report_id]

        if not self._conn:
            return True

        try:
            async with self._conn.execute("DELETE FROM reports WHERE id = ?", (report_id,)):
                pass  # cursor context manager handles the execute
            await self._conn.commit()  # commit after the cursor block closes
            return True
        except Exception as e:
            self._logger.error(f"Failed to delete report {report_id}: {e}")
            return False

    async def get_report_stats(self) -> Dict[str, Any]:

        if not self._conn:
            reports = list(self._in_memory_store.values())
            if not reports:
                return {"total_reports": 0, "avg_score": 0, "total_issues": 0, "unique_urls": 0}

            return {
                "total_reports": len(reports),
                "avg_score": sum(r.summary.score for r in reports) / len(reports),
                "total_issues": sum(r.summary.total_issues for r in reports),
                "unique_urls": len(set(r.request.url for r in reports))
            }

        try:
            async with self._conn.execute("""
                SELECT 
                    COUNT(*) as total_reports,
                    AVG(score) as avg_score,
                    SUM(json_extract(summary, '$.total_issues')) as total_issues,
                    COUNT(DISTINCT url) as unique_urls
                FROM reports
            """) as cursor:
                stats = await cursor.fetchone()
                return dict(stats)

        except Exception as e:
            self._logger.error(f"Failed to get report stats: {e}")
            return {"total_reports": 0, "avg_score": 0, "total_issues": 0, "unique_urls": 0}

    async def get_url_history(self, url: str, limit: int = 10) -> List[Dict[str, Any]]:
        return await self.list_reports(url=url, limit=limit, offset=0)

    async def cleanup_old_reports(self, days: int = 30) -> int:
        """Delete reports older than `days` days. Returns number of deleted rows."""
        if not self._conn:
            # Clean up in-memory store
            cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
            old_ids = [
                rid for rid, r in self._in_memory_store.items()
                if r.timestamp.timestamp() < cutoff
            ]
            for rid in old_ids:
                del self._in_memory_store[rid]
            return len(old_ids)

        try:
            # SQLite date arithmetic using ISO timestamp strings
            async with self._conn.execute(
                "DELETE FROM reports WHERE timestamp < datetime('now', ? || ' days')",
                (f"-{days}",)
            ) as cursor:
                deleted = cursor.rowcount
            await self._conn.commit()
            self._logger.info(f"Cleaned up {deleted} reports older than {days} days")
            return deleted
        except Exception as e:
            self._logger.error(f"Failed to cleanup old reports: {e}")
            return 0

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._logger.info("SQLite connection closed")

report_storage = ReportStorage()