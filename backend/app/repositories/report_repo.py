"""Report repository."""

from __future__ import annotations

from app.models.report import Report
from app.repositories.base import BaseRepository


class ReportRepository(BaseRepository[Report]):
    model = Report

    def recent_open_by(self, reporter_id: str) -> bool:
        return self.exists(Report.reporter_id == reporter_id)