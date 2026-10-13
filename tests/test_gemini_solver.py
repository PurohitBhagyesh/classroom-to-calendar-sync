"""Unit tests for GeminiAssignmentSolver."""

from unittest.mock import MagicMock, patch
import pytest

from gemini_solver import GeminiAssignmentSolver


def test_gemini_solver_init_no_key():
    """Solver is unavailable if no API key is set."""
    solver = GeminiAssignmentSolver(api_key="")
    assert not solver.is_available()


def test_gemini_solver_empty_pdf_text():
    """Empty or blank PDF text returns None without calling API."""
    solver = GeminiAssignmentSolver(api_key="test-key")
    solver.client = MagicMock()
    result = solver.solve_assignment(
        pdf_text="   ",
        assignment_title="Test Assignment",
        course_name="Computer Science",
        pdf_name="assignment1.pdf",
    )
    assert result is None
    solver.client.models.generate_content.assert_not_called()


def test_gemini_solver_unavailable_returns_none():
    """Calling solve_assignment when client is unavailable returns None."""
    solver = GeminiAssignmentSolver(api_key="")
    result = solver.solve_assignment(
        pdf_text="Question 1: Explain recursion.",
        assignment_title="Algorithms",
        course_name="CS101",
        pdf_name="homework.pdf",
    )
    assert result is None


def test_gemini_solver_success_and_file_save(tmp_path):
    """Successful model response generates solution and saves file."""
    solver = GeminiAssignmentSolver(api_key="test-key")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "## Solved: Question 1\nRecursion is a process..."
    mock_client.models.generate_content.return_value = mock_response
    solver.client = mock_client

    with patch("gemini_solver.BASE_DIR", tmp_path):
        solution = solver.solve_assignment(
            pdf_text="Question 1: Define recursion.",
            assignment_title="HW1 Recursion",
            course_name="Data Structures",
            pdf_name="recursion_hw.pdf",
            assignment_link="https://classroom.google.com/test",
        )

    assert solution == "## Solved: Question 1\nRecursion is a process..."
    mock_client.models.generate_content.assert_called_once()

    solution_file = tmp_path / "solutions" / "Data Structures_HW1 Recursion.md"
    assert solution_file.exists()
    assert solution_file.read_text(encoding="utf-8") == solution
