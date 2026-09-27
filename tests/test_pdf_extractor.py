"""Unit and integration tests for PDF Deadline Extractor."""

import io
from datetime import datetime
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from pdf_extractor import PDFDeadlineExtractor


def create_sample_pdf(lines: list[str]) -> bytes:
    """Helper to generate a real PDF in memory with custom text lines."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    y = 750
    for line in lines:
        p.drawString(50, y, line)
        y -= 25
    p.showPage()
    p.save()
    return buffer.getvalue()


class TestPDFDeadlineExtractor:
    @pytest.fixture
    def extractor(self):
        return PDFDeadlineExtractor(default_year=2026)

    def test_extract_written_date_with_time(self, extractor):
        pdf_bytes = create_sample_pdf([
            "CS 101: Introduction to Algorithms",
            "Project 1 Specification",
            "Please read the instructions carefully.",
            "Submission Date: October 28, 2026 at 11:59 PM",
            "Late submissions will receive a 10% penalty.",
        ])

        deadlines = extractor.extract_deadlines(pdf_bytes, file_name="Project1_Spec.pdf")
        assert len(deadlines) >= 1
        d = deadlines[0]
        assert d.due_datetime.year == 2026
        assert d.due_datetime.month == 10
        assert d.due_datetime.day == 28
        assert d.due_datetime.hour == 23
        assert d.due_datetime.minute == 59
        assert d.is_all_day is False

    def test_extract_iso_date(self, extractor):
        pdf_bytes = create_sample_pdf([
            "Database Systems - Homework 3",
            "Due Date: 2026-11-15",
            "Submit your SQL queries via the classroom portal.",
        ])

        deadlines = extractor.extract_deadlines(pdf_bytes, file_name="HW3.pdf")
        assert len(deadlines) >= 1
        d = deadlines[0]
        assert d.due_datetime.year == 2026
        assert d.due_datetime.month == 11
        assert d.due_datetime.day == 15
        assert d.is_all_day is True

    def test_extract_multiple_milestones(self, extractor):
        pdf_bytes = create_sample_pdf([
            "Senior Capstone Design Project",
            "Schedule & Deliverables:",
            "Milestone 1 Due: 10/15/2026",
            "Milestone 2 Due: 11/20/2026",
            "Final Report Submission: 12/10/2026 5:00 PM",
        ])

        deadlines = extractor.extract_deadlines(pdf_bytes, file_name="capstone_guidelines.pdf")
        assert len(deadlines) == 3
        # Check first milestone
        assert deadlines[0].due_datetime.month == 10
        assert deadlines[0].due_datetime.day == 15
        # Check second milestone
        assert deadlines[1].due_datetime.month == 11
        assert deadlines[1].due_datetime.day == 20
        # Check final report
        assert deadlines[2].due_datetime.month == 12
        assert deadlines[2].due_datetime.day == 10
        assert deadlines[2].due_datetime.hour == 17

    def test_extract_with_submit_before_phrase(self, extractor):
        text = "All groups must submit before 18th November 2026 on Google Classroom."
        deadlines = extractor.extract_deadlines(text, file_name="instructions.pdf")
        assert len(deadlines) == 1
        assert deadlines[0].due_datetime.month == 11
        assert deadlines[0].due_datetime.day == 18

    def test_no_deadlines_in_general_text(self, extractor):
        pdf_bytes = create_sample_pdf([
            "Lecture Notes: Introduction to Sorting Algorithms",
            "Quicksort has an average time complexity of O(n log n).",
            "Merge sort is stable.",
        ])
        deadlines = extractor.extract_deadlines(pdf_bytes, file_name="lecture1.pdf")
        assert len(deadlines) == 0
