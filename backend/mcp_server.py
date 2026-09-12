import re

from email.utils import parseaddr
from pathlib import Path

from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


load_dotenv()


# ============================================================
# MCP SERVER
# ============================================================

mcp = FastMCP("Google Tools")


# ============================================================
# GOOGLE SCOPES
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


# ============================================================
# FILE LOCATIONS
#
# Absolute paths. This server runs as a stdio subprocess and
# does NOT inherit a predictable working directory, so relative
# paths would silently miss token.json and re-trigger auth.
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CREDENTIALS_FILE = BASE_DIR / "credentials.json"

TOKEN_FILE = BASE_DIR / "token.json"


# ============================================================
# GOOGLE AUTHENTICATION
# ============================================================

class AuthRequired(Exception):
    """Raised when no usable token exists and consent must be granted."""


def save_credentials(credentials):

    TOKEN_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8"
    )


def run_consent_flow():

    """
    Interactive Google consent. Opens a browser and blocks.

    Only ever call this from auth.py, never from a tool call:
    the MCP server runs as a stdio subprocess with no console
    attached, so blocking here hangs the request forever.
    """

    if not CREDENTIALS_FILE.exists():

        raise AuthRequired(
            f"Missing OAuth client file: {CREDENTIALS_FILE}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        SCOPES
    )

    credentials = flow.run_local_server(
        port=0
    )

    save_credentials(credentials)

    return credentials


def get_google_credentials():

    """
    Load saved credentials, refreshing them if needed.

    Never prompts. Raises AuthRequired if consent has not been
    granted yet, so a tool call fails fast with a clear message
    instead of hanging on a browser prompt nobody can see.
    """

    if not TOKEN_FILE.exists():

        raise AuthRequired(
            "Google account not authorized yet. Run this once:\n"
            "    python auth.py"
        )

    credentials = Credentials.from_authorized_user_file(
        str(TOKEN_FILE),
        SCOPES
    )

    if credentials.valid:

        return credentials

    if credentials.expired and credentials.refresh_token:

        credentials.refresh(Request())

        # Persist the refreshed access token, otherwise every
        # call pays for a new refresh round-trip.
        save_credentials(credentials)

        return credentials

    raise AuthRequired(
        "Saved Google token is invalid and cannot be refreshed.\n"
        f"Delete {TOKEN_FILE.name} and run: python auth.py"
    )


# ============================================================
# GMAIL SERVICE
# ============================================================

def get_gmail_service():

    credentials = get_google_credentials()

    return build(
        "gmail",
        "v1",
        credentials=credentials
    )


# ============================================================
# DRIVE SERVICE
# ============================================================

def get_drive_service():

    credentials = get_google_credentials()

    return build(
        "drive",
        "v3",
        credentials=credentials
    )


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize(value):

    if not value:
        return ""

    value = value.strip().lower()

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value


# ============================================================
# STRICT SENDER MATCH
# ============================================================

def sender_matches(
    requested_sender,
    actual_name,
    actual_email
):

    requested = normalize(
        requested_sender
    )

    name = normalize(
        actual_name
    )

    email = normalize(
        actual_email
    )

    # --------------------------------------------------------
    # CASE 1:
    # User supplied complete email address
    #
    # Example:
    # mohdkhan2406@gmail.com
    # --------------------------------------------------------

    if "@" in requested:

        return email == requested


    # --------------------------------------------------------
    # CASE 2:
    # User supplied sender name
    #
    # Example:
    # mohd
    #
    # Match ONLY:
    #
    # From: Mohd <mohdkhan2406@gmail.com>
    #
    # Do NOT match:
    #
    # Mohd Saud Khan
    # Mohd Khan
    # notification@mohd.com
    # --------------------------------------------------------

    if name == requested:

        return True


    # --------------------------------------------------------
    # CASE 3:
    # User supplied email username
    #
    # Example:
    #
    # requested = mohdkhan2406
    #
    # actual email:
    # mohdkhan2406@gmail.com
    #
    # This is an exact local-part match.
    # --------------------------------------------------------

    if "@" not in email:

        return False

    local_part = email.split("@")[0]

    return local_part == requested


# ============================================================
# GET GMAIL MESSAGE DETAILS
# ============================================================

def get_header(
    headers,
    name
):

    for header in headers:

        if header["name"].lower() == name.lower():

            return header["value"]

    return ""


# ============================================================
# TOOL 1
# SEARCH GMAIL
# ============================================================

@mcp.tool()
def search_gmail(sender: str) -> str:

    """
    Search Gmail by STRICT sender.

    IMPORTANT:
    Only emails whose actual From header exactly matches
    the requested sender are returned.

    Example:

    search_gmail("mohd")

    searches only emails actually sent by mohd.

    It does NOT search subject or email body.
    """

    sender = sender.strip()

    if not sender:

        return "Invalid sender. Please provide a sender."


    try:
        gmail = get_gmail_service()
    except AuthRequired as error:
        return f"Authorization needed. {error}"


    # --------------------------------------------------------
    # Gmail server-side filtering
    #
    # This reduces the number of messages we inspect.
    # --------------------------------------------------------

    gmail_query = f"from:{sender}"


    response = gmail.users().messages().list(

        userId="me",

        q=gmail_query,

        maxResults=10

    ).execute()


    messages = response.get(
        "messages",
        []
    )


    if not messages:

        return (
            f"No emails found from sender '{sender}'."
        )


    exact_matches = []


    # ========================================================
    # SECOND FILTER
    #
    # Gmail search is NOT enough for strict matching.
    #
    # We inspect the actual From header.
    # ========================================================

    for message in messages:

        message_id = message["id"]


        full_message = gmail.users().messages().get(

            userId="me",

            id=message_id,

            format="metadata",

            metadataHeaders=[
                "From",
                "Subject",
                "Date"
            ]

        ).execute()


        headers = full_message.get(
            "payload",
            {}
        ).get(
            "headers",
            []
        )


        from_value = get_header(
            headers,
            "From"
        )


        subject = get_header(
            headers,
            "Subject"
        )


        date = get_header(
            headers,
            "Date"
        )


        # ----------------------------------------------------
        # Parse:
        #
        # Mohd <mohdkhan2406@gmail.com>
        #
        # into:
        #
        # name = Mohd
        # email = mohdkhan2406@gmail.com
        # ----------------------------------------------------

        actual_name, actual_email = parseaddr(
            from_value
        )


        # ----------------------------------------------------
        # STRICT MATCH
        # ----------------------------------------------------

        if sender_matches(

            requested_sender=sender,

            actual_name=actual_name,

            actual_email=actual_email

        ):

            exact_matches.append({

                "from": from_value,

                "subject": subject,

                "date": date

            })


    # ========================================================
    # NO EXACT MATCH
    # ========================================================

    if not exact_matches:

        return (
            f"No exact sender match found for '{sender}'."
        )


    # ========================================================
    # FORMAT RESULT
    # ========================================================

    result = []

    result.append(
        f"Found {len(exact_matches)} email(s) "
        f"from exact sender '{sender}':"
    )


    for index, email_data in enumerate(
        exact_matches,
        start=1
    ):

        result.append(
            f"\n{index}. "
            f"Subject: {email_data['subject'] or '(No subject)'}\n"
            f"   From: {email_data['from']}\n"
            f"   Date: {email_data['date']}"
        )


    return "\n".join(result)


# ============================================================
# TOOL 2
# SEARCH GOOGLE DRIVE
# ============================================================

@mcp.tool()
def search_google_drive(query: str) -> str:

    """
    Search Google Drive by file name.
    """

    query = query.strip()

    if not query:

        return "Invalid Google Drive search query."


    try:
        drive = get_drive_service()
    except AuthRequired as error:
        return f"Authorization needed. {error}"


    # --------------------------------------------------------
    # Search only file names
    # --------------------------------------------------------

    drive_query = (
        f"name contains '{query}' "
        f"and trashed = false"
    )


    response = drive.files().list(

        q=drive_query,

        pageSize=20,

        fields=(
            "files("
            "id,"
            "name,"
            "mimeType,"
            "webViewLink"
            ")"
        )

    ).execute()


    files = response.get(
        "files",
        []
    )


    if not files:

        return (
            f"No files found in Google Drive "
            f"for '{query}'."
        )


    result = []

    result.append(
        f"Found {len(files)} file(s) in Google Drive:"
    )


    for index, file in enumerate(
        files,
        start=1
    ):

        result.append(

            f"\n{index}. "
            f"Name: {file['name']}\n"
            f"   Type: {file['mimeType']}\n"
            f"   Link: {file.get('webViewLink', 'N/A')}"

        )


    return "\n".join(result)


# ============================================================
# START MCP SERVER
# ============================================================

if __name__ == "__main__":

    mcp.run(
        transport="stdio"
    )