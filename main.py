"""Command Line Interface for Google Classroom to Calendar PDF Automation."""

import argparse
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from auth import AuthManager
from calendar_client import CalendarClient
from classroom_client import ClassroomClient
from config import CREDENTIALS_FILE, DEFAULT_CALENDAR_NAME, DEFAULT_TASKLIST_NAME, DEFAULT_WATCH_INTERVAL_MINUTES
from email_dispatcher import EmailDispatcher
from gemini_solver import GeminiAssignmentSolver
from pdf_extractor import PDFDeadlineExtractor
from pdf_generator import SolutionPDFGenerator
from sync_manager import SyncManager
from tasks_client import TasksClient

console = Console()


def handle_setup(args):
    """Verifies credentials, performs OAuth login, and tests connectivity."""
    console.print(Panel.fit("[bold blue]Google Classroom & Calendar Sync Setup[/bold blue]"))

    if not CREDENTIALS_FILE.exists():
        console.print(f"[bold red]❌ credentials.json not found at:[/bold red] {CREDENTIALS_FILE.resolve()}")
        console.print("\n[bold yellow]Setup Instructions:[/bold yellow]")
        console.print("1. Visit Google Cloud Console: [link]https://console.cloud.google.com/[/link]")
        console.print("2. Enable APIs: Google Classroom API, Google Drive API, Google Calendar API")
        console.print("3. Configure OAuth Consent Screen and add your email to Test Users.")
        console.print("4. Create OAuth 2.0 Client ID (Application type: Desktop App).")
        console.print(f"5. Save the downloaded JSON as [cyan]{CREDENTIALS_FILE.resolve()}[/cyan]")
        return

    console.print("[green]✔ credentials.json found.[/green]")
    console.print("Authenticating with Google...")

    try:
        auth = AuthManager()
        classroom_svc = auth.get_classroom_service()
        drive_svc = auth.get_drive_service()
        calendar_svc = auth.get_calendar_service()

        console.print("[bold green]✔ Authentication successful![/bold green]")

        # Test listing courses
        classroom_client = ClassroomClient(classroom_svc, drive_svc)
        courses = classroom_client.get_courses(states=["ACTIVE"])

        table = Table(title=f"Active Classroom Courses ({len(courses)} found)")
        table.add_column("Course ID", style="cyan")
        table.add_column("Course Name", style="bold green")
        table.add_column("Section / Room", style="magenta")

        for c in courses:
            table.add_row(c.get("id"), c.get("name"), c.get("section", "N/A"))

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Setup / Auth Error:[/bold red] {e}")


def handle_sync(args):
    """Executes synchronization once."""
    console.print("[bold blue]Starting Google Classroom -> Google Calendar Sync...[/bold blue]")
    if args.dry_run:
        console.print("[bold yellow]ℹ Running in DRY-RUN mode (no calendar events will be written).[/bold yellow]")

    try:
        auth = AuthManager()
        classroom_client = ClassroomClient(auth.get_classroom_service(), auth.get_drive_service())
        calendar_client = CalendarClient(auth.get_calendar_service())
        tasks_client = TasksClient(auth.get_tasks_service())
        email_dispatcher = EmailDispatcher(auth.get_gmail_service())
        gemini_solver = GeminiAssignmentSolver()

        manager = SyncManager(
            classroom_client=classroom_client,
            calendar_client=calendar_client,
            tasks_client=tasks_client,
            email_dispatcher=email_dispatcher,
            gemini_solver=gemini_solver,
            calendar_name=args.calendar_name,
        )

        stats, logs = manager.sync(
            filter_course_id=args.course_id,
            filter_course_name=args.filter,
            max_age_days=args.max_age_days,
            dry_run=args.dry_run,
            force=getattr(args, "force", False),
        )

        # Print summary
        summary_table = Table(title="Synchronization Summary")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Count", style="bold")

        summary_table.add_row("Courses Scanned", str(stats.courses_scanned))
        summary_table.add_row("Assignments / Materials Scanned", str(stats.items_scanned))
        summary_table.add_row("PDF Attachments Analyzed", str(stats.pdfs_analyzed))
        summary_table.add_row("Calendar Events Created", f"[green]{stats.events_created}[/green]")
        summary_table.add_row("Calendar Events Updated", f"[yellow]{stats.events_updated}[/yellow]")
        summary_table.add_row("Google Tasks Synced", f"[magenta]{stats.tasks_synced}[/magenta]")
        summary_table.add_row("Assignments Solved by Gemini", f"[bold cyan]{stats.assignments_solved}[/bold cyan]")
        summary_table.add_row("Already Up-to-Date (Skipped)", str(stats.events_skipped))
        summary_table.add_row("Errors", f"[red]{stats.errors}[/red]" if stats.errors > 0 else "0")

        console.print(summary_table)

        if logs:
            event_table = Table(title="Event Details")
            event_table.add_column("Action", style="bold")
            event_table.add_column("Event Summary", style="green")
            event_table.add_column("Due Date/Time", style="cyan")

            for log in logs:
                action_style = "green" if "CREATE" in log["action"] else "yellow"
                event_table.add_row(f"[{action_style}]{log['action']}[/{action_style}]", log["summary"], log["due"])

            console.print(event_table)

    except FileNotFoundError as e:
        console.print(f"[bold red]{e}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Sync Error:[/bold red] {e}")


def handle_watch(args):
    """Runs continuous sync daemon with interval."""
    interval_minutes = args.interval or DEFAULT_WATCH_INTERVAL_MINUTES
    console.print(f"[bold blue]Starting Classroom Watch Daemon (Interval: {interval_minutes}m)...[/bold blue]")

    while True:
        console.print(f"\n[dim]--- Sync triggered at {time.strftime('%Y-%m-%d %H:%M:%S')} ---[/dim]")
        try:
            handle_sync(args)
        except Exception as e:
            console.print(f"[bold red]Daemon error during sync:[/bold red] {e}")

        console.print(f"[dim]Sleeping for {interval_minutes} minutes (Press Ctrl+C to stop)...[/dim]")
        try:
            time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            console.print("\n[yellow]Watch daemon stopped by user.[/yellow]")
            break


def handle_test_pdf(args):
    """Tests the PDF deadline extractor on a local PDF file."""
    pdf_path = Path(args.file_path)
    if not pdf_path.exists():
        console.print(f"[bold red]File not found:[/bold red] {pdf_path}")
        return

    console.print(f"[bold blue]Analyzing PDF for submission deadlines:[/bold blue] {pdf_path.resolve()}")
    extractor = PDFDeadlineExtractor()

    try:
        text = extractor.extract_text(str(pdf_path))
        console.print(Panel(text[:800] + ("..." if len(text) > 800 else ""), title="Extracted Text Preview"))

        deadlines = extractor.extract_deadlines(text, file_name=pdf_path.name)

        if not deadlines:
            console.print("[yellow]No submission dates or deadlines detected in this document.[/yellow]")
            return

        table = Table(title=f"Extracted Deadlines ({len(deadlines)} found)")
        table.add_column("Title / Milestone", style="bold green")
        table.add_column("Due Date & Time", style="bold cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Confidence", style="yellow")
        table.add_column("Context Snippet", style="dim")

        for d in deadlines:
            dt_str = d.due_datetime.strftime("%Y-%m-%d %H:%M") if not d.is_all_day else d.due_datetime.strftime("%Y-%m-%d (All-day)")
            table.add_row(
                d.title,
                dt_str,
                "All-Day" if d.is_all_day else "Timed",
                d.confidence,
                d.context_snippet[:80],
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error parsing PDF:[/bold red] {e}")


def handle_status(args):
    """Displays local SQLite synchronization database records."""
    auth = AuthManager()
    classroom_client = ClassroomClient(None, None)
    calendar_client = CalendarClient(None)
    manager = SyncManager(classroom_client, calendar_client)

    records = manager.list_synced_events()
    if not records:
        console.print("[yellow]No events have been synced yet. Run 'python main.py sync' to start.[/yellow]")
        return

    table = Table(title=f"Synced Deadlines Database ({len(records)} records)")
    table.add_column("Course", style="cyan")
    table.add_column("Assignment / Item", style="bold")
    table.add_column("PDF / Source", style="dim")
    table.add_column("Deadline", style="green")
    table.add_column("Calendar Event ID", style="magenta")

    for r in records:
        source_name = r.get("file_name") or "Classroom Native"
        table.add_row(
            r.get("course_name", "N/A"),
            r.get("item_title", "N/A"),
            source_name,
            r.get("deadline_iso", "N/A"),
            r.get("calendar_event_id", "N/A")[:15] + "..." if r.get("calendar_event_id") else "None",
        )

    console.print(table)


def handle_solve(args):
    """Solves a local PDF assignment using Gemini AI and optionally emails the solution."""
    pdf_path = Path(args.file_path)
    if not pdf_path.exists():
        console.print(f"[bold red]File not found:[/bold red] {pdf_path}")
        return

    console.print(f"[bold blue]Solving assignment PDF with Gemini AI:[/bold blue] {pdf_path.name}")
    extractor = PDFDeadlineExtractor()
    text = extractor.extract_text(str(pdf_path))

    solver = GeminiAssignmentSolver(api_key=args.gemini_api_key)
    if not solver.is_available():
        console.print("[bold yellow]Please provide your GEMINI_API_KEY to solve assignments:[/bold yellow]")
        console.print("Export it: [cyan]export GEMINI_API_KEY='your-key'[/cyan] or pass [cyan]--gemini-api-key 'your-key'[/cyan]")
        return

    solution = solver.solve_assignment(
        pdf_text=text,
        assignment_title=args.title or pdf_path.stem.replace("_", " ").title(),
        course_name=args.course or "General Assignment",
        pdf_name=pdf_path.name,
    )

    if solution:
        console.print(Panel(solution[:1000] + ("..." if len(solution) > 1000 else ""), title="Gemini Solutions Preview"))
        pdf_gen = SolutionPDFGenerator()
        compiled_pdf = pdf_gen.generate_pdf(
            course_name=args.course or "General Assignment",
            assignment_title=args.title or pdf_path.stem.replace("_", " ").title(),
            pdf_name=pdf_path.name,
            solution_markdown=solution,
        )
        console.print(f"[bold green]✔ Generated Solution PDF:[/bold green] {compiled_pdf}")
        if args.email:
            auth = AuthManager()
            dispatcher = EmailDispatcher(auth.get_gmail_service(), default_recipient=args.email)
            dispatcher.send_solution_email(
                course_name=args.course or "General",
                assignment_title=args.title or pdf_path.stem,
                pdf_name=pdf_path.name,
                solution_markdown=solution,
                attachment_pdf_path=compiled_pdf,
                recipient_email=args.email,
            )


def main():
    parser = argparse.ArgumentParser(
        description="Automate syncing Google Classroom assignments, extracting PDF deadlines, and solving questions with Gemini AI."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: sync
    sync_parser = subparsers.add_parser("sync", help="Run a one-time synchronization")
    sync_parser.add_argument("--course-id", help="Sync only a specific Google Classroom course ID")
    sync_parser.add_argument("--filter", help="Filter courses by name (e.g. '5th Sem')")
    sync_parser.add_argument("--max-age-days", type=int, default=30, help="Maximum age of items in days (default: 30 = 1 month)")
    sync_parser.add_argument("--calendar-name", default=DEFAULT_CALENDAR_NAME, help="Target Google Calendar name")
    sync_parser.add_argument("--dry-run", action="store_true", help="Simulate sync without modifying Google Calendar")
    sync_parser.add_argument("--force", action="store_true", help="Force update of all events (updates links & reminders)")

    # Command: watch
    watch_parser = subparsers.add_parser("watch", help="Run continuous periodic synchronization")
    watch_parser.add_argument("--interval", type=int, default=DEFAULT_WATCH_INTERVAL_MINUTES, help="Sync interval in minutes")
    watch_parser.add_argument("--calendar-name", default=DEFAULT_CALENDAR_NAME, help="Target Google Calendar name")
    watch_parser.add_argument("--dry-run", action="store_true", help="Simulate sync without modifying Google Calendar")
    watch_parser.add_argument("--course-id", help="Sync only a specific course ID")
    watch_parser.add_argument("--filter", help="Filter courses by name (e.g. '5th Sem')")
    watch_parser.add_argument("--max-age-days", type=int, default=30, help="Maximum age of items in days (default: 30 = 1 month)")

    # Command: test-pdf
    test_pdf_parser = subparsers.add_parser("test-pdf", help="Test date extractor on a local PDF file")
    test_pdf_parser.add_argument("file_path", help="Path to PDF file to test")

    # Command: solve
    solve_parser = subparsers.add_parser("solve", help="Solve assignment PDF questions using Gemini AI")
    solve_parser.add_argument("file_path", help="Path to PDF file to solve")
    solve_parser.add_argument("--title", help="Assignment title")
    solve_parser.add_argument("--course", help="Course name")
    solve_parser.add_argument("--email", help="Recipient email address")
    solve_parser.add_argument("--gemini-api-key", help="Gemini API Key")

    # Command: status
    subparsers.add_parser("status", help="Show all tracked synced records in local database")

    # Command: setup
    subparsers.add_parser("setup", help="Verify OAuth credentials and connection")

    args = parser.parse_args()

    if args.command == "setup":
        handle_setup(args)
    elif args.command == "sync":
        handle_sync(args)
    elif args.command == "watch":
        handle_watch(args)
    elif args.command == "test-pdf":
        handle_test_pdf(args)
    elif args.command == "solve":
        handle_solve(args)
    elif args.command == "status":
        handle_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
