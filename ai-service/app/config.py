import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')

def storage_root() -> Path:
    value = Path(os.getenv('DOCUMENT_STORAGE_PATH', './storage'))
    return (value if value.is_absolute() else ROOT / value).resolve()

def checked_path(value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_relative_to(storage_root()) or not path.is_file():
        raise ValueError('Invalid storage path')
    return path

def database_url() -> str:
    """Prisma accepts ?schema=; libpq does not."""
    url = urlsplit(os.environ['DATABASE_URL'])
    query = urlencode([(key, value) for key, value in parse_qsl(url.query) if key != 'schema'])
    return urlunsplit((url.scheme, url.netloc, url.path, query, url.fragment))
