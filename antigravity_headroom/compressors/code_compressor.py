import ast
import hashlib
import re
from .base import BaseCompressor

# Regex matching potential function/method signatures in curly-brace languages (excluding if, for, while, switch, catch, class)
SIGNATURE_PATTERN = re.compile(
    r'\b(?:func|function)\s+\w+.*?[{]|\b(?!if|for|while|switch|catch|class)\w+\s*\([^)]*\)\s*[^{]*?[{]',
    re.MULTILINE
)

def find_matching_brace(text: str, start_idx: int) -> int:
    """
    Finds the index of the matching closing curly brace, skipping comments and string literals.
    """
    idx = start_idx
    brace_count = 0
    n = len(text)
    
    def is_escaped(t: str, cur_idx: int) -> bool:
        count = 0
        i = cur_idx - 1
        while i >= 0 and t[i] == '\\':
            count += 1
            i -= 1
        return count % 2 == 1

    while idx < n:
        c = text[idx]
        if c == '{':
            brace_count += 1
            idx += 1
        elif c == '}':
            brace_count -= 1
            if brace_count == 0:
                return idx
            idx += 1
        elif c == '"':
            # Skip double-quoted string
            idx += 1
            while idx < n:
                if text[idx] == '"' and not is_escaped(text, idx):
                    idx += 1
                    break
                idx += 1
        elif c == "'":
            # Skip single-quoted string
            idx += 1
            while idx < n:
                if text[idx] == "'" and not is_escaped(text, idx):
                    idx += 1
                    break
                idx += 1
        elif c == '`':
            # Skip backticks (JS template literals)
            idx += 1
            while idx < n:
                if text[idx] == '`' and not is_escaped(text, idx):
                    idx += 1
                    break
                idx += 1
        elif c == '/' and idx + 1 < n and text[idx+1] == '/':
            # Skip line comments
            idx += 2
            while idx < n and text[idx] != '\n':
                idx += 1
        elif c == '/' and idx + 1 < n and text[idx+1] == '*':
            # Skip block comments
            idx += 2
            while idx < n:
                if text[idx] == '*' and idx + 1 < n and text[idx+1] == '/':
                    idx += 2
                    break
                idx += 1
        else:
            idx += 1
    return -1

class CodeCompressor(BaseCompressor):
    def __init__(self, storage=None, language=None):
        self.storage = storage
        self.language = language

    def compress(self, text: str, **kwargs) -> str:
        # Guard against empty/whitespace inputs
        if not text or not text.strip():
            return ""

        lang = kwargs.get('language', self.language)
        if lang == 'python' or (lang is None and self._looks_like_python(text)):
            return self._compress_python(text)
        else:
            return self._compress_curly_braces(text, lang or 'generic')

    def _looks_like_python(self, text: str) -> bool:
        if "def " in text or "import " in text or "class " in text:
            try:
                ast.parse(text)
                return True
            except Exception:
                pass
        return False

    def _compress_python(self, text: str) -> str:
        try:
            tree = ast.parse(text)
        except Exception:
            return self._compress_curly_braces(text, 'python')

        funcs = self._find_functions_to_strip(tree.body)
        if not funcs:
            return text

        # Sort functions by start line of body descending so replacement doesn't break subsequent offsets
        funcs.sort(key=lambda f: f.body[0].lineno, reverse=True)
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines()

        for func in funcs:
            start_line = func.body[0].lineno - 1
            end_line = func.body[-1].end_lineno - 1
            
            # Extract original body text
            body_lines = lines[start_line:end_line + 1]
            body_text = newline.join(body_lines)
            
            if self.storage:
                content_hash = self.storage.store(body_text)
            else:
                content_hash = hashlib.sha256(body_text.encode('utf-8')).hexdigest()
                
            size = len(body_text)
            
            # Match first body line's leading whitespace
            first_line = lines[start_line]
            leading_whitespace = first_line[:len(first_line) - len(first_line.lstrip())]
            
            token = f"<<ccr:{content_hash},python,{size}>>"
            lines[start_line:end_line + 1] = [leading_whitespace + token]

        res = newline.join(lines)
        if text.endswith(newline) or text.endswith("\n"):
            res += newline
        return res

    def _find_functions_to_strip(self, nodes) -> list:
        funcs = []
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.body and node.body[0].lineno > node.lineno:
                    funcs.append(node)
            elif isinstance(node, ast.ClassDef):
                funcs.extend(self._find_functions_to_strip(node.body))
            elif hasattr(node, 'body') and isinstance(node.body, list):
                funcs.extend(self._find_functions_to_strip(node.body))
        return funcs

    def _compress_curly_braces(self, text: str, lang: str) -> str:
        idx = 0
        result_parts = []
        last_idx = 0
        n = len(text)
        
        while idx < n:
            match = SIGNATURE_PATTERN.search(text, idx)
            if not match:
                break
            
            sig_start = match.start()
            sig_end = match.end()
            
            # Get the index of opening brace
            brace_open_idx = text.find('{', sig_start, sig_end)
            if brace_open_idx == -1:
                brace_open_idx = text.find('{', sig_start)
                
            if brace_open_idx == -1 or brace_open_idx >= n:
                idx = sig_end
                continue
                
            brace_close_idx = find_matching_brace(text, brace_open_idx)
            if brace_close_idx == -1:
                idx = sig_end
                continue
                
            body_content = text[brace_open_idx + 1:brace_close_idx]
            
            # Only compress body if it is nontrivial (>10 chars non-whitespace)
            if len(body_content.strip()) > 10:
                if self.storage:
                    content_hash = self.storage.store(body_content)
                else:
                    content_hash = hashlib.sha256(body_content.encode('utf-8')).hexdigest()
                    
                size = len(body_content)
                token = f"<<ccr:{content_hash},{lang},{size}>>"
                
                # Copy preceding text
                result_parts.append(text[last_idx:brace_open_idx + 1])
                result_parts.append(token)
                last_idx = brace_close_idx
                idx = brace_close_idx + 1
            else:
                idx = brace_close_idx + 1
                
        result_parts.append(text[last_idx:])
        return "".join(result_parts)
