class MeetingIdFormatError(Exception):
    def __init__(self, wrong_meeting_id: str):
        self.message = f"Not allowed meeting_id format ({wrong_meeting_id})"
        super().__init__(self.message)
