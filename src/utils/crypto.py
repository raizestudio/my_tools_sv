import secrets
import string

CHARS = string.ascii_letters + string.digits


def generate_short_code(length: int = 6) -> str:
    return "".join(secrets.choice(CHARS) for _ in range(length))
