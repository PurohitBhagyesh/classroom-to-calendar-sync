"""Google Classroom & Drive API client for fetching courses, coursework, and PDF attachments."""

import io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import dateparser
from googleapiclient.discovery import Resource
from googleapiclient.http import MediaIoBaseDownload


@dataclass
class AttachmentInfo:
    """Information about an attached file or link in Classroom."""

    id: str
    title: str
    alternate_link: Optional[str]
    mime_type: Optional[str]
    is_pdf: bool
    drive_file_id: Optional[str] = None


@dataclass
class CourseworkInfo:
    """Represents a Google Classroom assignment, announcement, or material item."""

    course_id: str
    course_name: str
    item_id: str
    item_type: str  # 'ASSIGNMENT', 'ANNOUNCEMENT', 'MATERIAL'
    title: str
    description: str
    alternate_link: Optional[str]
    creation_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    native_due_datetime: Optional[datetime] = None
    attachments: List[AttachmentInfo] = field(default_factory=list)


class ClassroomClient:
    """Client for interacting with Google Classroom API and downloading Drive attachments."""

    def __init__(self, classroom_service: Resource, drive_service: Resource):
        self.classroom = classroom_service
        self.drive = drive_service

    def get_courses(self, states: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Retrieves list of courses where user is enrolled or teaching."""
        if states is None:
            states = ["ACTIVE"]

        courses = []
        page_token = None
        while True:
            response = self.classroom.courses().list(
                courseStates=states,
                pageSize=50,
                pageToken=page_token
            ).execute()

            courses.extend(response.get("courses", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return courses

    def get_coursework_items(self, course_id: str, course_name: str) -> List[CourseworkInfo]:
        """Fetches all coursework (assignments), materials, and announcements for a course."""
        items: List[CourseworkInfo] = []

        # 1. Fetch CourseWork (Assignments)
        try:
            cw_response = self.classroom.courses().courseWork().list(
                courseId=course_id,
                pageSize=100
            ).execute()
            for cw in cw_response.get("courseWork", []):
                items.append(self._parse_coursework_item(course_id, course_name, cw))
        except Exception as e:
            print(f"[Warning] Failed to fetch coursework for course {course_name} ({course_id}): {e}")

        # 2. Fetch Announcements
        try:
            ann_response = self.classroom.courses().announcements().list(
                courseId=course_id,
                pageSize=50
            ).execute()
            for ann in ann_response.get("announcements", []):
                items.append(self._parse_announcement_item(course_id, course_name, ann))
        except Exception as e:
            print(f"[Warning] Failed to fetch announcements for course {course_name} ({course_id}): {e}")

        # 3. Fetch Course Work Materials (if user has permissions)
        try:
            mat_response = self.classroom.courses().courseWorkMaterials().list(
                courseId=course_id,
                pageSize=50
            ).execute()
            for mat in mat_response.get("courseWorkMaterial", []):
                items.append(self._parse_material_item(course_id, course_name, mat))
        except Exception as e:
            # 403 is expected for student accounts as courseWorkMaterials requires teacher permission
            if "403" not in str(e) and "ACCESS_TOKEN_SCOPE_INSUFFICIENT" not in str(e):
                print(f"[Warning] Failed to fetch materials for course {course_name} ({course_id}): {e}")

        return items

    def _parse_datetime_str(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parses ISO timestamp from API."""
        if not dt_str:
            return None
        return dateparser.parse(dt_str)

    def _parse_coursework_item(self, course_id: str, course_name: str, data: Dict[str, Any]) -> CourseworkInfo:
        """Parses a courseWork assignment dictionary into CourseworkInfo."""
        native_due = None
        due_date = data.get("dueDate")
        due_time = data.get("dueTime")
        if due_date:
            year = due_date.get("year", datetime.now().year)
            month = due_date.get("month", 1)
            day = due_date.get("day", 1)
            hour = due_time.get("hours", 23) if due_time else 23
            minute = due_time.get("minutes", 59) if due_time else 59
            try:
                native_due = datetime(year, month, day, hour, minute)
            except ValueError:
                native_due = None

        attachments = self._extract_attachments(data.get("materials", []))

        return CourseworkInfo(
            course_id=course_id,
            course_name=course_name,
            item_id=data.get("id", ""),
            item_type="ASSIGNMENT",
            title=data.get("title", "Untitled Assignment"),
            description=data.get("description", ""),
            alternate_link=data.get("alternateLink"),
            creation_time=self._parse_datetime_str(data.get("creationTime")),
            update_time=self._parse_datetime_str(data.get("updateTime")),
            native_due_datetime=native_due,
            attachments=attachments,
        )

    def _parse_announcement_item(self, course_id: str, course_name: str, data: Dict[str, Any]) -> CourseworkInfo:
        """Parses an announcement dictionary into CourseworkInfo."""
        attachments = self._extract_attachments(data.get("materials", []))
        text = data.get("text", "")
        title = text.split("\n")[0][:60] if text else "Announcement"

        return CourseworkInfo(
            course_id=course_id,
            course_name=course_name,
            item_id=data.get("id", ""),
            item_type="ANNOUNCEMENT",
            title=title,
            description=text,
            alternate_link=data.get("alternateLink"),
            creation_time=self._parse_datetime_str(data.get("creationTime")),
            update_time=self._parse_datetime_str(data.get("updateTime")),
            native_due_datetime=None,
            attachments=attachments,
        )

    def _parse_material_item(self, course_id: str, course_name: str, data: Dict[str, Any]) -> CourseworkInfo:
        """Parses courseWorkMaterial dictionary into CourseworkInfo."""
        attachments = self._extract_attachments(data.get("materials", []))
        return CourseworkInfo(
            course_id=course_id,
            course_name=course_name,
            item_id=data.get("id", ""),
            item_type="MATERIAL",
            title=data.get("title", "Course Material"),
            description=data.get("description", ""),
            alternate_link=data.get("alternateLink"),
            creation_time=self._parse_datetime_str(data.get("creationTime")),
            update_time=self._parse_datetime_str(data.get("updateTime")),
            native_due_datetime=None,
            attachments=attachments,
        )

    def _extract_attachments(self, materials_data: List[Dict[str, Any]]) -> List[AttachmentInfo]:
        """Extracts Drive files and link attachments from Classroom material objects."""
        attachments = []
        for mat in materials_data:
            if "driveFile" in mat:
                df = mat["driveFile"].get("driveFile", {})
                file_id = df.get("id")
                title = df.get("title", "Untitled File")
                alt_link = df.get("alternateLink")
                is_pdf = title.lower().endswith(".pdf")

                attachments.append(
                    AttachmentInfo(
                        id=file_id,
                        title=title,
                        alternate_link=alt_link,
                        mime_type="application/pdf" if is_pdf else None,
                        is_pdf=is_pdf,
                        drive_file_id=file_id,
                    )
                )
            elif "link" in mat:
                link_obj = mat["link"]
                url = link_obj.get("url", "")
                title = link_obj.get("title", url)
                is_pdf = url.lower().endswith(".pdf")
                attachments.append(
                    AttachmentInfo(
                        id=url,
                        title=title,
                        alternate_link=url,
                        mime_type="application/pdf" if is_pdf else None,
                        is_pdf=is_pdf,
                        drive_file_id=None,
                    )
                )
        return attachments

    def download_drive_file(self, file_id: str) -> bytes:
        """Downloads binary file content from Google Drive API."""
        request = self.drive.files().get_media(fileId=file_id, supportsAllDrives=True)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return file_buffer.getvalue()
