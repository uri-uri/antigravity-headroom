import re
from .base import BaseCompressor

class CacheAligner(BaseCompressor):
    # Regexes for normalization
    UUID_PAT = re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b')
    DATETIME_PAT = re.compile(
        r'\b\d{4}-\d{2}-\d{2}(?:T|[ ]+)\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b'
    )
    DATE_PAT = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')
    TIME_PAT = re.compile(r'\b\d{2}:\d{2}:\d{2}(?:\.\d+)?\b')
    COMMIT_PAT = re.compile(r'\b[0-9a-fA-F]{40}\b')

    def compress(self, text: str, **kwargs) -> str:
        return self.normalize(text)

    def normalize(self, text: str) -> str:
        if not text:
            return ""
        text = self.UUID_PAT.sub('[UUID]', text)
        text = self.DATETIME_PAT.sub('[DATETIME]', text)
        text = self.DATE_PAT.sub('[DATE]', text)
        text = self.TIME_PAT.sub('[TIME]', text)
        text = self.COMMIT_PAT.sub('[COMMIT_HASH]', text)
        return text
