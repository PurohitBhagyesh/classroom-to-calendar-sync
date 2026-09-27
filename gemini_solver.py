"""Gemini AI Assistant for solving Google Classroom Assignment PDFs."""

import os
from pathlib import Path
from typing import Optional
from google import genai
from google.genai import types

from config import BASE_DIR


class GeminiAssignmentSolver:
    """Uses Gemini API to analyze assignment PDFs and generate step-by-step solutions."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Failed to initialize Gemini Client: {e}")

    def is_available(self) -> bool:
        """Checks whether Gemini client is configured with a valid API key."""
        return self.client is not None

    def solve_assignment(
        self,
        pdf_text: str,
        assignment_title: str,
        course_name: str,
        pdf_name: str,
        assignment_link: Optional[str] = None,
    ) -> Optional[str]:
        """Generates comprehensive answers for assignment questions using Gemini."""
        if not self.is_available():
            print("[Info] GEMINI_API_KEY is not set. To automatically solve assignments with AI, set your GEMINI_API_KEY.")
            return None

        if not pdf_text.strip():
            return None

        prompt = f"""You are an expert tutor in Computer Engineering and Diploma subjects.
A student has a new assignment from Google Classroom. Please solve all the questions, exercises, or tasks in this assignment PDF with high accuracy, clear step-by-step explanations, diagrams in text, and clean code/examples where required.

---
Course Name: {course_name}
Assignment Title: {assignment_title}
Source PDF File: {pdf_name}
Classroom Link: {assignment_link or 'N/A'}
---

Here is the extracted text of the Assignment PDF:
{pdf_text}

---
Please structure your response as:
# 📚 Solutions for: {assignment_title}
**Course:** {course_name}  
**Source Document:** {pdf_name}  

---
## 📝 Question-by-Question Answers

Provide clear, formatted markdown solutions with proper numbering, explanations, and code blocks.
"""

        # Fast and reliable models
        models_to_try = [
            "gemini-flash-lite-latest",
            "gemini-3.1-flash-lite",
            "gemini-3.8-flash-lite-tts",
            "gemini-flash-latest",
        ]

        for model_name in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                    ),
                )
                solution_text = response.text
                if solution_text:
                    solutions_dir = BASE_DIR / "solutions"
                    solutions_dir.mkdir(parents=True, exist_ok=True)
                    safe_filename = "".join(c for c in f"{course_name}_{assignment_title}" if c.isalnum() or c in "._- ")
                    solution_file = solutions_dir / f"{safe_filename}.md"
                    with open(solution_file, "w", encoding="utf-8") as f:
                        f.write(solution_text)

                    print(f"[Gemini] Solved assignment using {model_name}! Saved solution to: {solution_file}")
                    return solution_text

            except Exception as e:
                continue

        print("[Error] Gemini failed to solve assignment across available models.")
        return None
