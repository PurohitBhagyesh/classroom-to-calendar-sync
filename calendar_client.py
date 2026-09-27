"""Google Calendar API client for creating and updating deadline events with popup & email reminders."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import pytz
from googleapiclient.discovery import Resource

from config import (
    DEFAULT_CALENDAR_NAME,
    DEFAULT_EVENT_COLOR_ID,
    DEFAULT_REMINDER_METHODS,
    DEFAULT_REMINDER_MINUTES,
)


class CalendarClient:
    """Manages Google Calendar operations, event creation, and deduplication."""

    def __init__(self, calendar_service: Resource, user_timezone: Optional[str] = None):
        self.service = calendar_service
        self.timezone = user_timezone or self._detect_primary_calendar_timezone()

    def _detect_primary_calendar_timezone(self) -> str:
        """Retrieves user's default timezone from primary Google Calendar setting."""
        try:
            primary = self.service.calendars().get(calendarId="primary").execute()
            return primary.get("timeZone", "UTC")
        except Exception:
            return "UTC"

    def get_or_create_calendar(self, calendar_name: str = DEFAULT_CALENDAR_NAME) -> str:
        """Finds existing calendar by summary/name or creates a new secondary calendar."""
        if calendar_name.lower() == "primary":
            return "primary"

        page_token = None
        while True:
            calendar_list = self.service.calendarList().list(pageToken=page_token).execute()
            for cal in calendar_list.get("items", []):
                if cal.get("summary") == calendar_name:
                    return cal.get("id")
            page_token = calendar_list.get("nextPageToken")
            if not page_token:
                break

        # If not found, create new calendar
        new_calendar = {
            "summary": calendar_name,
            "description": "Automated calendar for Google Classroom assignments and PDF submission deadlines.",
            "timeZone": self.timezone,
        }
        created_cal = self.service.calendars().insert(body=new_calendar).execute()
        return created_cal["id"]

    def create_or_update_deadline_event(
        self,
        calendar_id: str,
        summary: str,
        description: str,
        due_datetime: datetime,
        is_all_day: bool,
        course_id: str,
        item_id: str,
        file_id: Optional[str] = None,
        event_link: Optional[str] = None,
        existing_event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates or updates a deadline event with popup and email notifications."""
        tz_str = self.timezone

        if is_all_day:
            date_str = due_datetime.strftime("%Y-%m-%d")
            start_payload = {"date": date_str}
            next_day = (due_datetime + timedelta(days=1)).strftime("%Y-%m-%d")
            end_payload = {"date": next_day}
        else:
            if due_datetime.tzinfo is None:
                tz = pytz.timezone(tz_str)
                localized_due = tz.localize(due_datetime)
            else:
                localized_due = due_datetime

            start_iso = localized_due.isoformat()
            end_iso = (localized_due + timedelta(minutes=30)).isoformat()
            start_payload = {"dateTime": start_iso, "timeZone": tz_str}
            end_payload = {"dateTime": end_iso, "timeZone": tz_str}

        # Build reminder overrides (both Popups and Email Notifications)
        reminder_overrides = []
        for mins in DEFAULT_REMINDER_MINUTES:
            for method in DEFAULT_REMINDER_METHODS:
                reminder_overrides.append({"method": method, "minutes": mins})

        event_body = {
            "summary": summary,
            "description": description,
            "start": start_payload,
            "end": end_payload,
            "colorId": DEFAULT_EVENT_COLOR_ID,
            "reminders": {
                "useDefault": False,
                "overrides": reminder_overrides,
            },
            "extendedProperties": {
                "private": {
                    "source": "google_classroom_pdf_sync",
                    "course_id": str(course_id),
                    "item_id": str(item_id),
                    "file_id": str(file_id or ""),
                }
            },
        }

        if event_link:
            event_body["source"] = {"title": "View Assignment in Google Classroom", "url": event_link}

        if existing_event_id:
            try:
                updated_event = (
                    self.service.events()
                    .patch(calendarId=calendar_id, eventId=existing_event_id, body=event_body)
                    .execute()
                )
                return updated_event
            except Exception as e:
                print(f"[Info] Could not update existing event {existing_event_id} ({e}). Creating new event...")

        created_event = self.service.events().insert(calendarId=calendar_id, body=event_body).execute()
        return created_event
