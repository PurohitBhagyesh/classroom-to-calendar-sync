"""Unit and integration tests for Sync Manager state tracking and deduplication."""

from datetime import datetime
from unittest.mock import MagicMock
import pytest

from classroom_client import AttachmentInfo, CourseworkInfo
from sync_manager import SyncManager


class TestSyncManager:
    @pytest.fixture
    def temp_db(self, tmp_path):
        return tmp_path / "test_sync_state.sqlite"

    @pytest.fixture
    def mock_classroom(self):
        client = MagicMock()
        client.get_courses.return_value = [{"id": "c101", "name": "CS101 Algorithms"}]
        return client

    @pytest.fixture
    def mock_calendar(self):
        client = MagicMock()
        client.get_or_create_calendar.return_value = "cal_test_id"
        client.create_or_update_deadline_event.return_value = {"id": "event_12345"}
        return client

    @pytest.fixture
    def mock_gemini(self):
        solver = MagicMock()
        solver.is_available.return_value = False
        return solver

    @pytest.fixture
    def mock_tasks(self):
        tasks = MagicMock()
        tasks.is_available.return_value = False
        tasks.get_or_create_tasklist.return_value = None
        return tasks

    def test_sync_native_deadline(self, temp_db, mock_classroom, mock_calendar, mock_gemini, mock_tasks):
        mock_classroom.get_coursework_items.return_value = [
            CourseworkInfo(
                course_id="c101",
                course_name="CS101 Algorithms",
                item_id="cw_01",
                item_type="ASSIGNMENT",
                title="Homework 1",
                description="Solve problems 1-5",
                alternate_link="https://classroom.google.com/cw/01",
                native_due_datetime=datetime(2026, 10, 15, 23, 59),
                attachments=[],
            )
        ]

        manager = SyncManager(
            classroom_client=mock_classroom,
            calendar_client=mock_calendar,
            tasks_client=mock_tasks,
            gemini_solver=mock_gemini,
            db_path=temp_db,
        )

        # Run 1: Should create event
        stats1, _ = manager.sync()
        assert stats1.events_created == 1
        assert stats1.events_skipped == 0
        assert mock_calendar.create_or_update_deadline_event.call_count == 1

        # Run 2: Without change, should skip creating duplicate
        stats2, _ = manager.sync()
        assert stats2.events_created == 0
        assert stats2.events_skipped == 1
        # Call count remains 1
        assert mock_calendar.create_or_update_deadline_event.call_count == 1

    def test_sync_pdf_deadline(self, temp_db, mock_classroom, mock_calendar, mock_gemini, mock_tasks):
        # Create a sample PDF bytes
        from tests.test_pdf_extractor import create_sample_pdf

        pdf_content = create_sample_pdf([
            "Term Paper Guidelines",
            "Submission Date: November 12, 2026 at 5:00 PM",
        ])

        mock_classroom.download_drive_file.return_value = pdf_content
        mock_classroom.get_coursework_items.return_value = [
            CourseworkInfo(
                course_id="c101",
                course_name="CS101 Algorithms",
                item_id="cw_02",
                item_type="ASSIGNMENT",
                title="Term Paper",
                description="Final paper guidelines attached",
                alternate_link="https://classroom.google.com/cw/02",
                native_due_datetime=None,
                attachments=[
                    AttachmentInfo(
                        id="drive_file_99",
                        title="term_paper_rubric.pdf",
                        alternate_link="https://drive.google.com/file/99",
                        mime_type="application/pdf",
                        is_pdf=True,
                        drive_file_id="drive_file_99",
                    )
                ],
            )
        ]

        manager = SyncManager(
            classroom_client=mock_classroom,
            calendar_client=mock_calendar,
            tasks_client=mock_tasks,
            gemini_solver=mock_gemini,
            db_path=temp_db,
        )

        stats1, logs1 = manager.sync()
        assert stats1.pdfs_analyzed == 1
        assert stats1.events_created == 1
        assert stats1.events_skipped == 0

        # Verify record in database
        records = manager.list_synced_events()
        assert len(records) == 1
        assert records[0]["file_name"] == "term_paper_rubric.pdf"
        assert "2026-11-12" in records[0]["deadline_iso"]

    def test_sync_with_tasks(self, temp_db, mock_classroom, mock_calendar, mock_gemini):
        mock_tasks = MagicMock()
        mock_tasks.is_available.return_value = True
        mock_tasks.get_or_create_tasklist.return_value = "tasklist_test_id"
        mock_tasks.create_or_update_task.return_value = {"id": "task_123"}

        mock_classroom.get_coursework_items.return_value = [
            CourseworkInfo(
                course_id="c101",
                course_name="CS101 Algorithms",
                item_id="cw_03",
                item_type="ASSIGNMENT",
                title="Homework 3",
                description="Graph algorithms",
                alternate_link="https://classroom.google.com/cw/03",
                native_due_datetime=datetime(2026, 11, 20, 23, 59),
                attachments=[],
            )
        ]

        manager = SyncManager(
            classroom_client=mock_classroom,
            calendar_client=mock_calendar,
            tasks_client=mock_tasks,
            gemini_solver=mock_gemini,
            db_path=temp_db,
        )

        stats, _ = manager.sync()
        assert stats.events_created == 1
        assert stats.tasks_synced == 1
        assert mock_tasks.create_or_update_task.call_count == 1

    def test_sync_with_gemini_solver(self, temp_db, mock_classroom, mock_calendar, mock_tasks):
        from tests.test_pdf_extractor import create_sample_pdf

        pdf_content = create_sample_pdf([
            "Math Assignment 1",
            "Question 1: Find derivative of x^2",
            "Due Date: December 1, 2026",
        ])

        mock_gemini = MagicMock()
        mock_gemini.is_available.return_value = True
        mock_gemini.solve_assignment.return_value = "# Solution\n1. Derivative of x^2 is 2x."

        mock_classroom.download_drive_file.return_value = pdf_content
        mock_classroom.get_coursework_items.return_value = [
            CourseworkInfo(
                course_id="c101",
                course_name="CS101 Algorithms",
                item_id="cw_04",
                item_type="ASSIGNMENT",
                title="Math Homework",
                description="Attached exercises",
                alternate_link="https://classroom.google.com/cw/04",
                native_due_datetime=None,
                attachments=[
                    AttachmentInfo(
                        id="math_pdf_01",
                        title="math_hw.pdf",
                        alternate_link="https://drive.google.com/file/math01",
                        mime_type="application/pdf",
                        is_pdf=True,
                        drive_file_id="math_pdf_01",
                    )
                ],
            )
        ]

        manager = SyncManager(
            classroom_client=mock_classroom,
            calendar_client=mock_calendar,
            tasks_client=mock_tasks,
            gemini_solver=mock_gemini,
            db_path=temp_db,
        )

        stats, _ = manager.sync()
        assert stats.pdfs_analyzed == 1
        assert stats.assignments_solved == 1
        assert mock_gemini.solve_assignment.call_count == 1

