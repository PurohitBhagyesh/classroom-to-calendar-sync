"""Synchronization engine combining Google Classroom, PDF extraction, Google Calendar, Google Tasks, and Gemini AI Solver."""

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pytz

from config import DATABASE_FILE, DEFAULT_CALENDAR_NAME, DEFAULT_TASKLIST_NAME
from classroom_client import AttachmentInfo, ClassroomClient, CourseworkInfo
from calendar_client import CalendarClient
from email_dispatcher import EmailDispatcher
from gemini_solver import GeminiAssignmentSolver
from pdf_extractor import DeadlineItem, PDFDeadlineExtractor
from pdf_generator import SolutionPDFGenerator
from tasks_client import TasksClient


@dataclass
class SyncStats:
    """Statistics for a synchronization run."""

    courses_scanned: int = 0
    items_scanned: int = 0
    pdfs_analyzed: int = 0
    events_created: int = 0
    events_updated: int = 0
    events_skipped: int = 0
    tasks_synced: int = 0
    assignments_solved: int = 0
    errors: int = 0


class SyncManager:
    """Coordinates Classroom fetching, PDF deadline parsing, Calendar, Tasks, and Gemini Solutions."""

    def __init__(
        self,
        classroom_client: ClassroomClient,
        calendar_client: CalendarClient,
        tasks_client: Optional[TasksClient] = None,
        email_dispatcher: Optional[EmailDispatcher] = None,
        gemini_solver: Optional[GeminiAssignmentSolver] = None,
        db_path: Path = DATABASE_FILE,
        calendar_name: str = DEFAULT_CALENDAR_NAME,
        tasklist_name: str = DEFAULT_TASKLIST_NAME,
    ):
        self.classroom = classroom_client
        self.calendar = calendar_client
        self.tasks = tasks_client
        self.email_dispatcher = email_dispatcher
        self.gemini_solver = gemini_solver or GeminiAssignmentSolver()
        self.extractor = PDFDeadlineExtractor()
        self.pdf_generator = SolutionPDFGenerator()
        self.db_path = Path(db_path)
        self.calendar_name = calendar_name
        self.tasklist_name = tasklist_name
        self._init_db()

    def _init_db(self):
        """Initializes local SQLite database for deduplication and state tracking."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_records (
                    sync_key TEXT PRIMARY KEY,
                    course_id TEXT,
                    course_name TEXT,
                    item_id TEXT,
                    item_title TEXT,
                    file_id TEXT,
                    file_name TEXT,
                    calendar_event_id TEXT,
                    task_id TEXT,
                    answers_generated INTEGER DEFAULT 0,
                    deadline_iso TEXT,
                    is_all_day INTEGER,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            # Add columns if upgrading
            try:
                conn.execute("ALTER TABLE sync_records ADD COLUMN task_id TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE sync_records ADD COLUMN answers_generated INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def _get_record(self, sync_key: str) -> Optional[sqlite3.Row]:
        """Fetches existing sync record by unique key."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sync_records WHERE sync_key = ?", (sync_key,))
            return cursor.fetchone()

    def _save_record(
        self,
        sync_key: str,
        course_id: str,
        course_name: str,
        item_id: str,
        item_title: str,
        file_id: Optional[str],
        file_name: Optional[str],
        calendar_event_id: str,
        task_id: Optional[str],
        deadline_iso: str,
        is_all_day: bool,
        answers_generated: int = 0,
    ):
        """Inserts or updates a sync record."""
        now_str = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sync_records (
                    sync_key, course_id, course_name, item_id, item_title,
                    file_id, file_name, calendar_event_id, task_id, answers_generated,
                    deadline_iso, is_all_day, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sync_key) DO UPDATE SET
                    calendar_event_id = excluded.calendar_event_id,
                    task_id = excluded.task_id,
                    answers_generated = excluded.answers_generated,
                    deadline_iso = excluded.deadline_iso,
                    is_all_day = excluded.is_all_day,
                    updated_at = excluded.updated_at
                """,
                (
                    sync_key,
                    course_id,
                    course_name,
                    item_id,
                    item_title,
                    file_id or "",
                    file_name or "",
                    calendar_event_id,
                    task_id or "",
                    answers_generated,
                    deadline_iso,
                    1 if is_all_day else 0,
                    now_str,
                    now_str,
                ),
            )
            conn.commit()

    def _is_within_age(self, item: CourseworkInfo, max_age_days: Optional[int]) -> bool:
        """Checks if coursework was created/updated recently or has a future/recent deadline."""
        if not max_age_days:
            return True

        cutoff_date = datetime.now(pytz.utc) - timedelta(days=max_age_days)

        for t in [item.update_time, item.creation_time]:
            if t:
                t_aware = t if t.tzinfo else pytz.utc.localize(t)
                if t_aware >= cutoff_date:
                    return True

        if item.native_due_datetime:
            due_aware = item.native_due_datetime if item.native_due_datetime.tzinfo else pytz.utc.localize(item.native_due_datetime)
            if due_aware >= cutoff_date:
                return True

        return False

    def sync(
        self,
        filter_course_id: Optional[str] = None,
        filter_course_name: Optional[str] = None,
        max_age_days: Optional[int] = None,
        dry_run: bool = False,
        force: bool = False,
    ) -> Tuple[SyncStats, List[Dict]]:
        """Executes full synchronization cycle across courses."""
        stats = SyncStats()
        event_logs = []

        # 1. Resolve or create Google Calendar & Tasks List
        calendar_id = "primary" if dry_run else self.calendar.get_or_create_calendar(self.calendar_name)
        tasklist_id = None
        if self.tasks and self.tasks.is_available() and not dry_run:
            tasklist_id = self.tasks.get_or_create_tasklist(self.tasklist_name)

        # 2. Retrieve courses
        courses = self.classroom.get_courses(states=["ACTIVE"])
        if filter_course_id:
            courses = [c for c in courses if c.get("id") == filter_course_id]
        elif filter_course_name:
            query = filter_course_name.lower().strip()
            courses = [c for c in courses if query in c.get("name", "").lower()]

        stats.courses_scanned = len(courses)

        for course in courses:
            course_id = course.get("id")
            course_name = course.get("name", "Unnamed Course")
            print(f"[Sync] Scanning course: {course_name} (ID: {course_id})")

            items = self.classroom.get_coursework_items(course_id, course_name)

            for item in items:
                if max_age_days and not self._is_within_age(item, max_age_days):
                    continue

                stats.items_scanned += 1

                # 3A. Check native assignment due date
                if item.native_due_datetime:
                    self._process_native_deadline(
                        course_name, item, calendar_id, tasklist_id, dry_run, stats, event_logs, force
                    )

                # 3B. Check PDF attachments for submission dates and Gemini solutions
                for attachment in item.attachments:
                    if attachment.is_pdf and attachment.drive_file_id:
                        stats.pdfs_analyzed += 1
                        self._process_pdf_attachment(
                            course_name, item, attachment, calendar_id, tasklist_id, dry_run, stats, event_logs, force
                        )

        return stats, event_logs

    def _process_native_deadline(
        self,
        course_name: str,
        item: CourseworkInfo,
        calendar_id: str,
        tasklist_id: Optional[str],
        dry_run: bool,
        stats: SyncStats,
        event_logs: List[Dict],
        force: bool = False,
    ):
        """Processes native Classroom due date."""
        sync_key = f"native:{item.course_id}:{item.item_id}"
        deadline_iso = item.native_due_datetime.isoformat()
        is_all_day = False

        existing_record = self._get_record(sync_key)
        if existing_record and existing_record["deadline_iso"] == deadline_iso and not force:
            stats.events_skipped += 1
            return

        summary = f"[{course_name}] {item.title} (Due)"
        description = (
            f"🔗 DIRECT ASSIGNMENT LINK: {item.alternate_link or 'N/A'}\n\n"
            f"📚 Course: {course_name}\n"
            f"📝 Assignment: {item.title}\n"
            f"⏰ Submission Due: {item.native_due_datetime.strftime('%Y-%m-%d %I:%M %p')}\n\n"
            f"Details / Description:\n{item.description or 'No additional description provided.'}\n\n"
            f"🔔 Email & Popup Reminders: Active (24 hours & 2 hours before deadline)\n"
            f"⚡ Automatically synced by Google Classroom Automation."
        )

        task_notes = (
            f"🔗 Link: {item.alternate_link or 'N/A'}\n"
            f"📚 Course: {course_name}\n"
            f"📝 Assignment: {item.title}\n"
            f"⏰ Deadline: {item.native_due_datetime.strftime('%Y-%m-%d %I:%M %p')}"
        )

        if dry_run:
            stats.events_created += 1
            event_logs.append({
                "action": "DRY_RUN_CREATE",
                "summary": summary,
                "due": deadline_iso,
                "source": "Classroom Native Due Date",
            })
            return

        try:
            existing_event_id = existing_record["calendar_event_id"] if existing_record else None
            existing_task_id = existing_record["task_id"] if existing_record and "task_id" in existing_record.keys() else None

            # 1. Google Calendar Event
            event_result = self.calendar.create_or_update_deadline_event(
                calendar_id=calendar_id,
                summary=summary,
                description=description,
                due_datetime=item.native_due_datetime,
                is_all_day=is_all_day,
                course_id=item.course_id,
                item_id=item.item_id,
                event_link=item.alternate_link,
                existing_event_id=existing_event_id,
            )

            # 2. Google Task
            task_result = None
            if self.tasks and tasklist_id:
                task_result = self.tasks.create_or_update_task(
                    tasklist_id=tasklist_id,
                    title=summary,
                    notes=task_notes,
                    due_datetime=item.native_due_datetime,
                    existing_task_id=existing_task_id,
                )
                if task_result:
                    stats.tasks_synced += 1

            self._save_record(
                sync_key=sync_key,
                course_id=item.course_id,
                course_name=course_name,
                item_id=item.item_id,
                item_title=item.title,
                file_id=None,
                file_name=None,
                calendar_event_id=event_result.get("id"),
                task_id=task_result.get("id") if task_result else None,
                deadline_iso=deadline_iso,
                is_all_day=is_all_day,
            )

            if existing_record:
                stats.events_updated += 1
                event_logs.append({"action": "UPDATED", "summary": summary, "due": deadline_iso})
            else:
                stats.events_created += 1
                event_logs.append({"action": "CREATED", "summary": summary, "due": deadline_iso})

        except Exception as e:
            stats.errors += 1
            print(f"[Error] Failed to sync native deadline for {item.title}: {e}")

    def _process_pdf_attachment(
        self,
        course_name: str,
        item: CourseworkInfo,
        attachment: AttachmentInfo,
        calendar_id: str,
        tasklist_id: Optional[str],
        dry_run: bool,
        stats: SyncStats,
        event_logs: List[Dict],
        force: bool = False,
    ):
        """Downloads attached PDF, extracts text, finds submission dates, generates Gemini solutions and syncs."""
        try:
            pdf_bytes = self.classroom.download_drive_file(attachment.drive_file_id)
        except Exception as e:
            print(f"[Warning] Failed to download PDF '{attachment.title}' (ID: {attachment.drive_file_id}): {e}")
            return

        pdf_text = self.extractor.extract_text(pdf_bytes)

        # 1. Check & Solve assignment with Gemini if configured
        answers_generated = 0
        if self.gemini_solver and self.gemini_solver.is_available() and pdf_text.strip():
            # Check if solutions were already generated for this PDF
            pdf_solution_key = f"solution:{attachment.drive_file_id}"
            solution_record = self._get_record(pdf_solution_key)
            if not solution_record or force:
                solutions_md = self.gemini_solver.solve_assignment(
                    pdf_text=pdf_text,
                    assignment_title=item.title,
                    course_name=course_name,
                    pdf_name=attachment.title,
                    assignment_link=item.alternate_link,
                )
                if solutions_md:
                    stats.assignments_solved += 1
                    answers_generated = 1

                    # Generate styled solutions PDF
                    solution_pdf_path = None
                    try:
                        solution_pdf_path = self.pdf_generator.generate_pdf(
                            course_name=course_name,
                            assignment_title=item.title,
                            pdf_name=attachment.title,
                            solution_markdown=solutions_md,
                        )
                    except Exception as e:
                        print(f"[Warning] Failed to compile solution PDF: {e}")

                    # Email solutions + attached PDF if EmailDispatcher is available
                    if self.email_dispatcher:
                        self.email_dispatcher.send_solution_email(
                            course_name=course_name,
                            assignment_title=item.title,
                            pdf_name=attachment.title,
                            solution_markdown=solutions_md,
                            attachment_pdf_path=solution_pdf_path,
                            assignment_link=item.alternate_link,
                        )
                    # Record solution saved
                    self._save_record(
                        sync_key=pdf_solution_key,
                        course_id=item.course_id,
                        course_name=course_name,
                        item_id=item.item_id,
                        item_title=item.title,
                        file_id=attachment.drive_file_id,
                        file_name=attachment.title,
                        calendar_event_id="",
                        task_id="",
                        deadline_iso="",
                        is_all_day=False,
                        answers_generated=1,
                    )

        # 2. Extract deadlines from PDF
        deadlines = self.extractor.extract_deadlines(
            text_or_pdf=pdf_text,
            file_name=attachment.title,
            context_hint=item.title,
        )

        for idx, dl in enumerate(deadlines):
            sync_key = f"pdf:{item.course_id}:{item.item_id}:{attachment.drive_file_id}:{idx}"
            deadline_iso = dl.due_datetime.isoformat()

            existing_record = self._get_record(sync_key)
            if existing_record and existing_record["deadline_iso"] == deadline_iso and not force:
                stats.events_skipped += 1
                continue

            summary = f"[{course_name}] {dl.title}"
            description = (
                f"🔗 DIRECT ASSIGNMENT LINK: {item.alternate_link or 'N/A'}\n"
                f"📎 DIRECT PDF ATTACHMENT: {attachment.alternate_link or 'N/A'}\n\n"
                f"📚 Course: {course_name}\n"
                f"📝 Assignment: {item.title}\n"
                f"📄 Source PDF: {attachment.title}\n"
                f"⏰ Extracted Submission Date: {dl.due_datetime.strftime('%Y-%m-%d %I:%M %p')}\n\n"
                f"📌 Extracted Context from PDF:\n\"{dl.context_snippet}\"\n\n"
                f"🔔 Email & Popup Reminders: Active (24 hours & 2 hours before deadline)\n"
                f"⚡ Automatically extracted and synced by Google Classroom Automation."
            )

            task_notes = (
                f"🔗 Assignment Link: {item.alternate_link or 'N/A'}\n"
                f"📎 PDF File Link: {attachment.alternate_link or 'N/A'}\n"
                f"📚 Course: {course_name}\n"
                f"📄 PDF: {attachment.title}\n"
                f"📌 Context: {dl.context_snippet}"
            )

            if dry_run:
                stats.events_created += 1
                event_logs.append({
                    "action": "DRY_RUN_CREATE",
                    "summary": summary,
                    "due": deadline_iso,
                    "source": f"PDF ({attachment.title})",
                    "context": dl.context_snippet,
                })
                continue

            try:
                existing_event_id = existing_record["calendar_event_id"] if existing_record else None
                existing_task_id = existing_record["task_id"] if existing_record and "task_id" in existing_record.keys() else None

                # Google Calendar Event
                event_result = self.calendar.create_or_update_deadline_event(
                    calendar_id=calendar_id,
                    summary=summary,
                    description=description,
                    due_datetime=dl.due_datetime,
                    is_all_day=dl.is_all_day,
                    course_id=item.course_id,
                    item_id=item.item_id,
                    file_id=attachment.drive_file_id,
                    event_link=item.alternate_link,
                    existing_event_id=existing_event_id,
                )

                # Google Task
                task_result = None
                if self.tasks and tasklist_id:
                    task_result = self.tasks.create_or_update_task(
                        tasklist_id=tasklist_id,
                        title=summary,
                        notes=task_notes,
                        due_datetime=dl.due_datetime,
                        existing_task_id=existing_task_id,
                    )
                    if task_result:
                        stats.tasks_synced += 1

                self._save_record(
                    sync_key=sync_key,
                    course_id=item.course_id,
                    course_name=course_name,
                    item_id=item.item_id,
                    item_title=item.title,
                    file_id=attachment.drive_file_id,
                    file_name=attachment.title,
                    calendar_event_id=event_result.get("id"),
                    task_id=task_result.get("id") if task_result else None,
                    deadline_iso=deadline_iso,
                    is_all_day=dl.is_all_day,
                    answers_generated=answers_generated,
                )

                if existing_record:
                    stats.events_updated += 1
                    event_logs.append({"action": "UPDATED", "summary": summary, "due": deadline_iso})
                else:
                    stats.events_created += 1
                    event_logs.append({"action": "CREATED", "summary": summary, "due": deadline_iso})

            except Exception as e:
                stats.errors += 1
                print(f"[Error] Failed to sync PDF deadline for {attachment.title}: {e}")

    def list_synced_events(self) -> List[Dict]:
        """Lists all currently tracked records from the SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sync_records ORDER BY deadline_iso ASC")
            return [dict(row) for row in cursor.fetchall()]
