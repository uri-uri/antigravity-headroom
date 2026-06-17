import re
from .base import BaseCompressor

class TextCompressor(BaseCompressor):
    def compress(self, text: str, **kwargs) -> str:
        """
        Compresses general text by cleaning trailing whitespaces, removing excessive
        empty lines, and collapsing runs of spaces/tabs inside a line while preserving structure.
        """
        lines = text.splitlines()
        compressed_lines = []
        consecutive_blank = 0
        
        for line in lines:
            trimmed = line.rstrip()
            if not trimmed:
                consecutive_blank += 1
                if consecutive_blank <= 1:
                    compressed_lines.append("")
                continue
            else:
                consecutive_blank = 0
            
            # Collapse internal whitespace but preserve the leading structural indentation
            leading_space_len = len(trimmed) - len(trimmed.lstrip())
            leading = trimmed[:leading_space_len]
            rest = trimmed[leading_space_len:]
            
            # Collapse multiple spaces and tabs to a single space
            collapsed_rest = re.sub(r'[ \t]+', ' ', rest)
            compressed_lines.append(leading + collapsed_rest)
            
        return "\n".join(compressed_lines)
