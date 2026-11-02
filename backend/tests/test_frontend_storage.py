"""Static audit of the frontend source.

Tokens must never be written to localStorage/sessionStorage/IndexedDB, and user
text must never be injected as HTML.
"""
from pathlib import Path

from django.conf import settings

STORAGE_APIS = ("localstorage", "sessionstorage", "indexeddb")
TOKEN_WORDS = ("token", "jwt", "credential", "bearer", "password")
# The cleanup module is the only file allowed to name token keys in storage.
CLEANUP_MODULE = "legacyTokenCleanup.js"


def _source_files():
    root = Path(settings.ROOT_DIR) / "frontend" / "src"
    return sorted(
        path
        for path in root.rglob("*")
        if path.suffix in {".js", ".jsx", ".ts", ".tsx"} and path.is_file()
    )


def test_source_files_are_found():
    assert _source_files(), "frontend/src not found; the audit would be vacuous"


def test_frontend_never_stores_credentials_in_web_storage():
    offenders = []
    for path in _source_files():
        if path.name == CLEANUP_MODULE:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            lowered = line.lower()
            if not any(api in lowered for api in STORAGE_APIS):
                continue
            # Look at the statement and the two lines above it, where a key
            # constant such as ACCESS_TOKEN_KEY would be declared.
            window = " ".join(lines[max(0, index - 2) : index + 1]).lower()
            if any(word in window for word in TOKEN_WORDS):
                offenders.append(f"{path.name}:{index + 1}: {line.strip()}")
    assert not offenders, "tokens must live in HttpOnly cookies:\n" + "\n".join(offenders)


def test_frontend_does_not_inject_raw_html():
    offenders = [
        str(path)
        for path in _source_files()
        if "dangerouslySetInnerHTML" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, "unexpected raw HTML injection: " + ", ".join(offenders)
