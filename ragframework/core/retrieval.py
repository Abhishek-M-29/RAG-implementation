import hashlib
import logging
import re

logger = logging.getLogger(__name__)


def query_hash(query: str) -> str:
    normalized = re.sub(r"\s+", " ", query.strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()
