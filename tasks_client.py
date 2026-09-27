"""Google Tasks API client for creating and updating assignment tasks and reminders."""

from datetime import datetime
from typing import Any, Dict, Optional
import pytz
from googleapiclient.discovery import Resource

from config import DEFAULT_TASKLIST_NAME


class TasksClient:
    """Manages Google Tasks operations, task lists, and task synchronization."""

    def __init__(self, tasks_service: Optional[Resource]):
        self.service = tasks_service

    def is_available(self) -> bool:
        """Returns whether Tasks service is authenticated and available."""
        return self.service is not None

    def get_or_create_tasklist(self, tasklist_name: str = DEFAULT_TASKLIST_NAME) -> Optional[str]:
        """Finds existing Task List by title or creates a new dedicated list."""
        if not self.is_available():
            return None

        try:
            page_token = None
            while True:
                response = self.service.tasklists().list(pageToken=page_token).execute()
                for tl in response.get("items", []):
                    if tl.get("title") == tasklist_name:
                        return tl.get("id")
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            # Create new tasklist if not found
            new_tl = self.service.tasklists().insert(body={"title": tasklist_name}).execute()
            return new_tl.get("id")
        except Exception as e:
            print(f"[Warning] Failed to access Google Tasks list: {e}")
            return None

    def create_or_update_task(
        self,
        tasklist_id: str,
        title: str,
        notes: str,
        due_datetime: datetime,
        existing_task_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Creates or updates a task with deadline and direct link notes."""
        if not self.is_available() or not tasklist_id:
            return None

        # Google Tasks RFC 3339 formatted due date (Zulu/UTC)
        due_utc = due_datetime if due_datetime.tzinfo else pytz.utc.localize(due_datetime)
        due_rfc3339 = due_utc.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        task_body = {
            "title": title,
            "notes": notes,
            "due": due_rfc3339,
            "status": "needsAction",
        }

        try:
            if existing_task_id:
                try:
                    return (
                        self.service.tasks()
                        .patch(tasklist=tasklist_id, task=existing_task_id, body=task_body)
                        .execute()
                    )
                except Exception:
                    pass  # If existing task was deleted or not found, fall back to insert

            return self.service.tasks().insert(tasklist=tasklist_id, body=task_body).execute()
        except Exception as e:
            print(f"[Warning] Failed to sync to Google Tasks: {e}")
            return None
