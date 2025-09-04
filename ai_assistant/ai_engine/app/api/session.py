import secrets


COOKIE_NAME = "cqa_sid"


def make_session_id() -> str:
    return secrets.token_urlsafe(16)
