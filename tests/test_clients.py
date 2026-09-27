"""Unit tests for Calendar, Tasks, Email, and Gemini client modules."""

from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from calendar_client import CalendarClient
from email_dispatcher import EmailDispatcher
from gemini_solver import GeminiAssignmentSolver
from tasks_client import TasksClient


class TestClients:
    def test_calendar_client_create_event(self):
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_service.calendars().get.return_value.execute.return_value = {"timeZone": "UTC"}
        mock_events.insert.return_value.execute.return_value = {"id": "event_abc_123"}

        client = CalendarClient(mock_service, user_timezone="UTC")
        result = client.create_or_update_deadline_event(
            calendar_id="cal_123",
            summary="[CS101] Homework 1",
            description="Details",
            due_datetime=datetime(2026, 10, 15, 18, 0),
            is_all_day=False,
            course_id="c1",
            item_id="i1",
        )

        assert result["id"] == "event_abc_123"
        assert mock_events.insert.call_count == 1

    def test_tasks_client_create_task(self):
        mock_service = MagicMock()
        mock_tasks = MagicMock()
        mock_service.tasks.return_value = mock_tasks
        mock_tasks.insert.return_value.execute.return_value = {"id": "task_xyz"}

        client = TasksClient(mock_service)
        assert client.is_available() is True

        result = client.create_or_update_task(
            tasklist_id="tl_123",
            title="Complete Lab 2",
            notes="Notes here",
            due_datetime=datetime(2026, 11, 1, 23, 59),
        )

        assert result["id"] == "task_xyz"
        assert mock_tasks.insert.call_count == 1

    def test_email_dispatcher_missing_recipient(self):
        mock_service = MagicMock()
        dispatcher = EmailDispatcher(mock_service, default_recipient=None)
        sent = dispatcher.send_solution_email(
            course_name="Math",
            assignment_title="Algebra",
            pdf_name="alg.pdf",
            solution_markdown="Solutions",
            recipient_email=None,
        )
        assert sent is False

    def test_gemini_solver_disabled_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            solver = GeminiAssignmentSolver(api_key=None)
            assert solver.is_available() is False
            result = solver.solve_assignment(
                pdf_text="Some text",
                assignment_title="Test",
                course_name="CS",
                pdf_name="test.pdf",
            )
            assert result is None
