import os
import json
import re
from .compressors.json_crusher import JsonCrusher
from .compressors.code_compressor import CodeCompressor
from .compressors.log_crusher import LogCrusher
from .compressors.text_compressor import TextCompressor
from .compressors.tabular_crusher import TabularCrusher
from .compressors.cache_aligner import CacheAligner

class HeadroomRouter:
    def __init__(self, storage=None):
        self.storage = storage
        self.json_crusher = JsonCrusher()
        self.code_compressor = CodeCompressor(storage=storage)
        self.log_crusher = LogCrusher()
        self.tabular_crusher = TabularCrusher()
        self.text_compressor = TextCompressor()
        self.cache_aligner = CacheAligner()

    def route_and_compress(self, text: str, filename: str = None, mime_type: str = None, **kwargs) -> str:
        """
        Routes the text to the appropriate compressor and returns the compressed content.
        
        Optional CacheAligner normalization:
        - If align=True is passed in kwargs, the text runs through CacheAligner first.
        """
        # Guard against empty/whitespace inputs
        if not text or not text.strip():
            return ""

        align = kwargs.get('align', False)
        if align:
            text = self.cache_aligner.normalize(text)

        # 1. Filename Extension Check
        if filename:
            ext = os.path.splitext(filename)[1].lower()
            if ext == '.json':
                return self.json_crusher.compress(text, **kwargs)
            elif ext in ('.py', '.js', '.ts', '.go', '.cpp', '.h', '.hpp', '.java', '.cs', '.rs', '.swift'):
                lang = 'python' if ext == '.py' else ext[1:]
                return self.code_compressor.compress(text, language=lang, **kwargs)
            elif ext == '.log':
                return self.log_crusher.compress(text, **kwargs)
            elif ext in ('.csv', '.tsv'):
                return self.tabular_crusher.compress(text, **kwargs)

        # 2. MIME Type Check
        if mime_type:
            mime_type = mime_type.lower()
            if 'json' in mime_type:
                return self.json_crusher.compress(text, **kwargs)
            elif 'log' in mime_type:
                return self.log_crusher.compress(text, **kwargs)
            elif 'csv' in mime_type or 'tab-separated-values' in mime_type:
                return self.tabular_crusher.compress(text, **kwargs)
            elif 'python' in mime_type or 'javascript' in mime_type or 'code' in mime_type:
                return self.code_compressor.compress(text, **kwargs)

        # 3. JSON Parsing Check
        try:
            json.loads(text)
            return self.json_crusher.compress(text, **kwargs)
        except Exception:
            pass

        # 4. Tabular Heuristics Check
        first_lines = text.splitlines()[:3]
        if len(first_lines) >= 2:
            comma_counts = [line.count(',') for line in first_lines if line.strip()]
            tab_counts = [line.count('\t') for line in first_lines if line.strip()]
            if len(comma_counts) >= 2 and len(set(comma_counts)) == 1 and comma_counts[0] > 0:
                return self.tabular_crusher.compress(text, **kwargs)
            if len(tab_counts) >= 2 and len(set(tab_counts)) == 1 and tab_counts[0] > 0:
                return self.tabular_crusher.compress(text, **kwargs)

        # 5. AST / Code signature check
        if ("def " in text and ":" in text) or "import " in text or ("class " in text and "{" in text) or ("function " in text and "{" in text):
            return self.code_compressor.compress(text, **kwargs)

        # 6. Log Heuristics Check
        log_indicators = ['[info]', '[error]', '[warn]', '[debug]', 'error:', 'warning:', 'traceback', 'exception:']
        log_lines_count = sum(1 for line in text.splitlines()[:20] if any(ind in line.lower() for ind in log_indicators))
        if log_lines_count >= 2 or 'traceback' in text.lower():
            return self.log_crusher.compress(text, **kwargs)

        # 7. Fallback
        return self.text_compressor.compress(text, **kwargs)

    def decompress(self, text: str) -> str:
        """
        Reconstructs the original text by replacing <<ccr:hash,lang,size>> tags inline
        with original contents retrieved from SQLite storage.
        """
        if not text:
            return ""

        # Matches leading spaces/tabs followed by typical <<ccr:hash,lang,size>> token structure
        ccr_pat = re.compile(r'([ \t]*)<<ccr:([a-f0-9]{64}),[^,>]+,\d+>>')

        def replace_match(match):
            indent = match.group(1)
            content_hash = match.group(2)
            if self.storage:
                original = self.storage.retrieve(content_hash)
                if original is not None:
                    if original.startswith(indent):
                        return original
                    return indent + original
            return match.group(0)

        return ccr_pat.sub(replace_match, text)
