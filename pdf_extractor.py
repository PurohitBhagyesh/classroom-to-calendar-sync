"""PDF Text and Submission Date / Deadline Extraction Engine."""

import io
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple, Union
import dateparser
from pypdf import PdfReader


@dataclass
class DeadlineItem:
    """Represents an extracted deadline or submission date."""

    title: str
    due_datetime: datetime
    is_all_day: bool
    context_snippet: str
    confidence: str  # 'HIGH', 'MEDIUM', 'LOW'
    source_file_name: Optional[str] = None


class PDFDeadlineExtractor:
    """Extracts text from PDF documents and identifies submission dates and deadlines."""

    SUBMISSION_KEYWORDS = [
        r"submission\s*date",
        r"last\s*date\s*(?:of|for)?\s*submission",
        r"due\s*date",
        r"due\s*on",
        r"due\s*by",
        r"due\s*:",
        r"due\b",
        r"submit\s*(?:on\s*or\s*)?by",
        r"submit\s*before",
        r"turn\s*in\s*by",
        r"turn-in\s*date",
        r"deadline",
        r"final\s*submission",
        r"report\s*submission",
        r"project\s*due",
        r"assignment\s*due",
        r"milestone\s*\d*\s*due",
        r"phase\s*\d*\s*due",
        r"cutoff\s*date",
    ]

    DATE_PATTERNS = [
        # ISO format: 2026-11-15 or 2026/11/15
        r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b",
        # Written month formats: Oct 28, 2026; 28th October 2026; October 28; 28 Oct
        r"\b(?:(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?))|(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?))(?:,?\s+\d{4})?\b",
        # Numerical format: 10/28/2026, 28/10/2026, 28-10-2026
        r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b",
    ]

    TIME_PATTERN = r"(?:\b(\d{1,2}(?::\d{2})?(?::\d{2})?\s*(?:AM|PM|am|pm|a\.m\.|p\.m\.))\b|\b(midnight|noon|23:59|11:59\s*(?:pm|PM))\b)"

    def __init__(self, default_year: Optional[int] = None):
        self.default_year = default_year or datetime.now().year

    def extract_text(self, pdf_source: Union[bytes, io.BytesIO, str]) -> str:
        """Extracts all plain text from a PDF source."""
        if isinstance(pdf_source, str):
            reader = PdfReader(pdf_source)
        elif isinstance(pdf_source, bytes):
            reader = PdfReader(io.BytesIO(pdf_source))
        elif isinstance(pdf_source, io.BytesIO):
            reader = PdfReader(pdf_source)
        else:
            raise ValueError("Unsupported PDF source type.")

        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)

        return "\n".join(text_parts)

    def extract_deadlines(
        self,
        text_or_pdf: Union[str, bytes, io.BytesIO],
        file_name: Optional[str] = None,
        context_hint: Optional[str] = None,
    ) -> List[DeadlineItem]:
        """Parses text or PDF and returns identified submission deadlines."""
        if isinstance(text_or_pdf, (bytes, io.BytesIO)) or (
            isinstance(text_or_pdf, str) and (text_or_pdf.endswith(".pdf") or "\x00" in text_or_pdf)
        ):
            full_text = self.extract_text(text_or_pdf)
        else:
            full_text = text_or_pdf

        if not full_text.strip():
            return []

        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        deadlines: List[DeadlineItem] = []
        seen_timestamps = set()

        combined_keyword_regex = re.compile(
            r"|".join(self.SUBMISSION_KEYWORDS), re.IGNORECASE
        )

        in_deadline_section = False

        for i, line in enumerate(lines):
            # Check if entering a deadlines/schedule section header (e.g. "Project Deadlines:", "Important Dates:")
            if re.match(r"^(?:project\s+)?(?:deadlines|important\s+dates|schedule|milestones)\s*:", line, re.IGNORECASE):
                in_deadline_section = True
                continue

            match = combined_keyword_regex.search(line)
            has_date_in_line, is_all_day, parsed_dt = self._find_date_in_text(line)

            # If inside a schedule section and the line has a date, treat it as a deadline line
            if in_deadline_section and has_date_in_line and not match:
                match = True

            if not match:
                continue

            snippet = line

            # If keyword is on a standalone line without date, look at next line
            if not parsed_dt and i + 1 < len(lines):
                next_line = lines[i + 1]
                has_next_date, is_all_day, parsed_dt = self._find_date_in_text(next_line)
                if parsed_dt:
                    snippet = f"{line} {next_line}"
                    line = next_line  # use next line for title and parsing

            if parsed_dt:
                ts_key = parsed_dt.strftime("%Y-%m-%d %H:%M")
                if ts_key in seen_timestamps:
                    continue
                seen_timestamps.add(ts_key)

                item_title = self._derive_title(line, context_hint, file_name)
                confidence = "HIGH" if (match and not isinstance(match, bool) and any(k in match.group(0).lower() for k in ["submission", "due date", "deadline"])) else "MEDIUM"

                deadlines.append(
                    DeadlineItem(
                        title=item_title,
                        due_datetime=parsed_dt,
                        is_all_day=is_all_day,
                        context_snippet=snippet,
                        confidence=confidence,
                        source_file_name=file_name,
                    )
                )

        return deadlines

    def _find_date_in_text(self, text: str) -> Tuple[Optional[str], bool, Optional[datetime]]:
        """Finds date string in text and parses it to datetime."""
        time_match = re.search(self.TIME_PATTERN, text, re.IGNORECASE)
        time_str = time_match.group(0) if time_match else None
        is_all_day = time_str is None

        for pattern in self.DATE_PATTERNS:
            date_matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for d_match in date_matches:
                raw_date_str = d_match.group(0)

                # Clean ordinal indicators (1st, 2nd, 3rd, etc.)
                clean_date_str = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", raw_date_str)

                # Combine date + time
                full_date_expr = f"{clean_date_str} {time_str}" if time_str else clean_date_str

                # If ISO format (e.g., 2026-11-15)
                if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", clean_date_str):
                    try:
                        iso_dt = datetime.strptime(clean_date_str, "%Y-%m-%d")
                        if time_str:
                            parsed = dateparser.parse(full_date_expr)
                        else:
                            parsed = iso_dt.replace(hour=23, minute=59, second=0)
                        return raw_date_str, is_all_day, parsed
                    except Exception:
                        pass

                # Parse with dateparser
                parsed = dateparser.parse(
                    full_date_expr,
                    settings={
                        "PREFER_DATES_FROM": "future",
                        "RELATIVE_BASE": datetime.now(),
                    },
                )

                if parsed:
                    # If year was omitted in the matched string, assign default_year
                    if not re.search(r"\b\d{4}\b", raw_date_str):
                        parsed = parsed.replace(year=self.default_year)

                    if is_all_day:
                        parsed = parsed.replace(hour=23, minute=59, second=0)

                    return raw_date_str, is_all_day, parsed

        return None, True, None

    def _derive_title(self, line: str, context_hint: Optional[str], file_name: Optional[str]) -> str:
        """Derives a clean, meaningful event title from the line context."""
        parts = re.split(r"[:\-|–]", line)
        if len(parts) > 1 and len(parts[0].strip()) > 3:
            prefix = parts[0].strip()
            # Clean common filler prefixes
            if not prefix.lower().startswith("due date") and not prefix.lower().startswith("deadline"):
                return prefix

        if context_hint:
            return f"{context_hint} Deadline"

        if file_name:
            base_name = file_name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
            return f"{base_name.title()} Deadline"

        return "Assignment Submission Deadline"
