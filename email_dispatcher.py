"""Email Dispatcher for sending solved assignment answers and PDF attachments to user's inbox."""

import base64
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional
from config import DEFAULT_RECIPIENT_EMAIL
from googleapiclient.discovery import Resource


class EmailDispatcher:
    """Dispatches assignment solutions and PDF attachments directly to the user's Gmail."""

    def __init__(self, gmail_service: Optional[Resource], default_recipient: Optional[str] = None):
        self.service = gmail_service
        self.recipient = default_recipient or DEFAULT_RECIPIENT_EMAIL

    def is_available(self) -> bool:
        """Returns whether Gmail API service is available."""
        return self.service is not None

    def send_solution_email(
        self,
        course_name: str,
        assignment_title: str,
        pdf_name: str,
        solution_markdown: str,
        attachment_pdf_path: Optional[Path] = None,
        assignment_link: Optional[str] = None,
        recipient_email: Optional[str] = None,
    ) -> bool:
        """Sends rich formatted email with assignment solutions and attached PDF to the user."""
        target_email = recipient_email or self.recipient
        if not target_email:
            print("[Info] No recipient email specified (set RECIPIENT_EMAIL in .env or pass --email). Skipping email.")
            return False

        subject = f"📚 Solved Assignment: [{course_name}] {assignment_title} (PDF: {pdf_name})"

        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #202124; background-color: #f8f9fa; padding: 20px; }}
                .container {{ max-width: 800px; margin: auto; background: #ffffff; border-radius: 8px; border: 1px solid #dadce0; padding: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
                .header {{ border-bottom: 2px solid #1a73e8; padding-bottom: 15px; margin-bottom: 20px; }}
                .badge {{ background-color: #e8f0fe; color: #1a73e8; font-weight: bold; padding: 4px 8px; border-radius: 4px; display: inline-block; margin-bottom: 10px; }}
                .link-btn {{ display: inline-block; background-color: #1a73e8; color: #ffffff !important; padding: 10px 18px; border-radius: 4px; text-decoration: none; font-weight: bold; margin-top: 15px; }}
                .attachment-notice {{ background-color: #e6f4ea; border: 1px solid #ceead6; color: #137333; padding: 12px; border-radius: 6px; margin: 15px 0; font-weight: 500; }}
                .content {{ margin-top: 20px; }}
                pre {{ background: #f1f3f4; padding: 12px; border-radius: 6px; overflow-x: auto; font-family: Courier, monospace; font-size: 13px; }}
                code {{ font-family: Courier, monospace; background: #f1f3f4; padding: 2px 4px; border-radius: 3px; color: #1a73e8; }}
                h2 {{ color: #1a73e8; margin-top: 25px; }}
                h3 {{ color: #3c4043; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <span class="badge">Google Classroom Assignment Solved</span>
                    <h1 style="margin: 0; color: #1a73e8;">{assignment_title}</h1>
                    <p style="margin: 5px 0 0 0; color: #5f6368;"><strong>Course:</strong> {course_name} | <strong>Source PDF:</strong> {pdf_name}</p>
                    {f'<a class="link-btn" href="{assignment_link}">🔗 Open Assignment in Classroom</a>' if assignment_link else ''}
                </div>

                <div class="attachment-notice">
                    📎 <strong>PDF Solutions Attached:</strong> A printable PDF document containing all step-by-step solutions is attached to this email.
                </div>

                <div class="content">
                    <div style="white-space: pre-wrap; font-size: 14.5px;">{solution_markdown}</div>
                </div>
                <hr style="border: 0; border-top: 1px solid #dadce0; margin-top: 30px;">
                <p style="font-size: 12px; color: #70757a; text-align: center;">⚡ Automatically generated and formatted by Google Classroom & Gemini Automation</p>
            </div>
        </body>
        </html>
        """

        if not self.is_available():
            print(f"[Info] Solutions generated for '{assignment_title}' (PDF: {pdf_name}).")
            return False

        try:
            message = MIMEMultipart("mixed")
            message["to"] = target_email
            message["subject"] = subject

            # Body alternative part (plain + html)
            body_part = MIMEMultipart("alternative")
            body_part.attach(MIMEText(solution_markdown, "plain"))
            body_part.attach(MIMEText(html_body, "html"))
            message.attach(body_part)

            # Attach Solution PDF if available
            if attachment_pdf_path and Path(attachment_pdf_path).exists():
                pdf_file_path = Path(attachment_pdf_path)
                with open(pdf_file_path, "rb") as f:
                    pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
                    pdf_attachment.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=pdf_file_path.name,
                    )
                    message.attach(pdf_attachment)
                print(f"[Email] Attached solutions PDF: {pdf_file_path.name}")

            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            self.service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
            print(f"[Gmail] Successfully sent solutions email with PDF attachment to {target_email}!")
            return True

        except Exception as e:
            print(f"[Warning] Failed to send email via Gmail API: {e}")
            return False
