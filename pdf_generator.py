"""Generates styled, professional PDF solution documents from Gemini markdown answers."""

import re
from pathlib import Path
from typing import List, Optional
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

from config import BASE_DIR


class SolutionPDFGenerator:
    """Converts markdown assignment solutions into clean, styled PDF documents."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or (BASE_DIR / "solutions")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_pdf(
        self,
        course_name: str,
        assignment_title: str,
        pdf_name: str,
        solution_markdown: str,
    ) -> Path:
        """Generates a professional PDF from the solution markdown and returns the file path."""
        safe_name = "".join(c for c in f"{course_name}_{assignment_title}" if c.isalnum() or c in "._- ")
        pdf_path = self.output_dir / f"{safe_name}_Solutions.pdf"

        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()

        # Custom Palette
        primary_color = HexColor("#1a73e8")
        dark_text = HexColor("#202124")
        code_bg = HexColor("#f1f3f4")
        border_color = HexColor("#dadce0")

        # Custom Typography Styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=primary_color,
            spaceAfter=6,
        )

        meta_style = ParagraphStyle(
            "DocMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=HexColor("#5f6368"),
            spaceAfter=12,
        )

        h1_style = ParagraphStyle(
            "H1",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=primary_color,
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True,
        )

        h2_style = ParagraphStyle(
            "H2",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=HexColor("#185abc"),
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        )

        h3_style = ParagraphStyle(
            "H3",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=dark_text,
            spaceBefore=8,
            spaceAfter=3,
            keepWithNext=True,
        )

        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=dark_text,
            spaceAfter=6,
        )

        bullet_style = ParagraphStyle(
            "Bullet",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=dark_text,
            leftIndent=15,
            firstLineIndent=-10,
            spaceAfter=3,
        )

        code_style = ParagraphStyle(
            "CodeBlock",
            parent=styles["Normal"],
            fontName="Courier",
            fontSize=8.5,
            leading=11,
            textColor=HexColor("#202124"),
        )

        story = []

        # Document Header
        story.append(Paragraph(f"📚 {assignment_title} — Solutions", title_style))
        story.append(Paragraph(f"<b>Course:</b> {course_name} &nbsp;|&nbsp; <b>Source PDF:</b> {pdf_name}", meta_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceAfter=14))

        # Parse markdown lines
        lines = solution_markdown.splitlines()
        in_code_block = False
        code_lines = []

        for line in lines:
            line_str = line.strip()

            # Handle code / diagram blocks ```
            if line_str.startswith("```"):
                if in_code_block:
                    in_code_block = False
                    block_text = "\n".join(code_lines)
                    code_lines = []
                    t = Table(
                        [[Preformatted(block_text, code_style)]],
                        colWidths=[letter[0] - 80],
                    )
                    t.setStyle(
                        TableStyle([
                            ("BACKGROUND", (0, 0), (-1, -1), code_bg),
                            ("BOX", (0, 0), (-1, -1), 1, border_color),
                            ("PADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ])
                    )
                    story.append(t)
                    story.append(Spacer(1, 8))
                else:
                    in_code_block = True
                    code_lines = []
                continue

            if in_code_block:
                code_lines.append(line)
                continue

            if not line_str:
                story.append(Spacer(1, 4))
                continue

            # Headers
            if line_str.startswith("# "):
                clean_txt = self._clean_inline_markdown(line_str[2:])
                story.append(Paragraph(clean_txt, h1_style))
            elif line_str.startswith("## "):
                clean_txt = self._clean_inline_markdown(line_str[3:])
                story.append(Paragraph(clean_txt, h1_style))
            elif line_str.startswith("### "):
                clean_txt = self._clean_inline_markdown(line_str[4:])
                story.append(Paragraph(clean_txt, h2_style))
            elif line_str.startswith("#### "):
                clean_txt = self._clean_inline_markdown(line_str[5:])
                story.append(Paragraph(clean_txt, h3_style))
            elif line_str.startswith("---") or line_str.startswith("***"):
                story.append(HRFlowable(width="100%", thickness=0.5, color=border_color, spaceBefore=6, spaceAfter=6))
            elif line_str.startswith("* ") or line_str.startswith("- ") or line_str.startswith("• "):
                clean_txt = self._clean_inline_markdown(line_str[2:])
                story.append(Paragraph(f"&bull; {clean_txt}", bullet_style))
            elif re.match(r"^\d+\.\s", line_str):
                clean_txt = self._clean_inline_markdown(line_str)
                story.append(Paragraph(clean_txt, bullet_style))
            else:
                clean_txt = self._clean_inline_markdown(line_str)
                story.append(Paragraph(clean_txt, body_style))

        # Build PDF
        doc.build(story)
        print(f"[PDF Generator] Successfully generated PDF: {pdf_path}")
        return pdf_path

    def _clean_inline_markdown(self, text: str) -> str:
        """Converts inline markdown like **bold**, *italic*, `code` to reportlab XML tags."""
        # Replace XML characters
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # **bold** -> <b>bold</b>
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # *italic* -> <i>italic</i>
        text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", text)
        # `code` -> <font name="Courier" color="#c7254e">\1</font>
        text = re.sub(r"`([^`]+?)`", r'<font name="Courier" color="#1a73e8">\1</font>', text)

        return text
