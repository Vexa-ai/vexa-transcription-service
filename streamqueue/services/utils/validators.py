import re

from services.utils.exceptions import MeetingIdFormatError


def check_google_style_type(meeting_id: str) -> None:
    # Define the pattern for the Google-type: vyi-ccyz-sxt
    pattern = r"^[a-z]{3}-[a-z]{4}-[a-z]{3}$"

    if not re.match(pattern, meeting_id):
        raise MeetingIdFormatError(meeting_id)
