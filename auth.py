"""Google API OAuth 2.0 authentication helper."""

import os
from pathlib import Path
from typing import Optional

# Allow OAuth scope canonicalization from Google
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

from config import CREDENTIALS_FILE, SCOPES, TOKEN_FILE


class AuthManager:
    """Manages OAuth 2.0 tokens and builds authenticated Google API service clients."""

    def __init__(self, credentials_path: Path = CREDENTIALS_FILE, token_path: Path = TOKEN_FILE):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self._credentials: Optional[Credentials] = None

    def get_credentials(self) -> Credentials:
        """Retrieves or refreshes OAuth 2.0 credentials."""
        creds = None
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as e:
                print(f"[Warning] Failed to load cached token ({e}). Re-authenticating...")

        # If there are no valid credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"[Warning] Failed to refresh token ({e}). Starting fresh login flow...")
                    creds = None

            if not creds:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"\n[Error] Google Cloud credentials file not found at: {self.credentials_path.resolve()}\n"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        self._credentials = creds
        return creds

    def get_classroom_service(self) -> Resource:
        """Returns authenticated Google Classroom API client."""
        creds = self.get_credentials()
        return build("classroom", "v1", credentials=creds)

    def get_drive_service(self) -> Resource:
        """Returns authenticated Google Drive API client."""
        creds = self.get_credentials()
        return build("drive", "v3", credentials=creds)

    def get_calendar_service(self) -> Resource:
        """Returns authenticated Google Calendar API client."""
        creds = self.get_credentials()
        return build("calendar", "v3", credentials=creds)

    def get_tasks_service(self) -> Optional[Resource]:
        """Returns authenticated Google Tasks API client."""
        try:
            creds = self.get_credentials()
            return build("tasks", "v1", credentials=creds)
        except Exception as e:
            print(f"[Warning] Google Tasks service unavailable: {e}")
            return None

    def get_gmail_service(self) -> Optional[Resource]:
        """Returns authenticated Gmail API client."""
        try:
            creds = self.get_credentials()
            return build("gmail", "v1", credentials=creds)
        except Exception as e:
            return None
