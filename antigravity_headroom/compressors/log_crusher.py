import re
from .base import BaseCompressor

class LogCrusher(BaseCompressor):
    def __init__(self, k_lines: int = 20):
        self.k_lines = k_lines
        self.anomaly_patterns = [
            re.compile(r'error', re.IGNORECASE),
            re.compile(r'fail', re.IGNORECASE),
            re.compile(r'exception', re.IGNORECASE),
            re.compile(r'warn', re.IGNORECASE),
            re.compile(r'critical', re.IGNORECASE),
            re.compile(r'fatal', re.IGNORECASE),
            re.compile(r'traceback', re.IGNORECASE),
            re.compile(r'caused\s+by', re.IGNORECASE),
            re.compile(r'^\s+at\s+\w+\.'),  # Java stack trace
            re.compile(r'File\s+"[^"]+",\s+line\s+\d+'), # Python traceback
        ]

    def is_anomaly(self, line: str) -> bool:
        return any(pat.search(line) for pat in self.anomaly_patterns)

    def compress(self, text: str, **kwargs) -> str:
        # Guard against empty/whitespace inputs
        if not text or not text.strip():
            return ""

        k = kwargs.get('k_lines', self.k_lines)
        k = max(0, k)
        
        lines = text.splitlines()
        n = len(lines)
        
        if k == 0:
            head = []
            tail = []
            middle_lines = lines
        elif n <= 2 * k:
            return text
        else:
            head = lines[:k]
            tail = lines[-k:]
            middle_lines = lines[k:-k]
        
        anomalies = []
        for idx, line in enumerate(middle_lines):
            original_idx = k + idx + 1
            if self.is_anomaly(line):
                anomalies.append((original_idx, line))
                
        # Group contiguous anomaly lines
        grouped_anomalies = []
        if anomalies:
            current_group = [anomalies[0]]
            for item in anomalies[1:]:
                if item[0] == current_group[-1][0] + 1:
                    current_group.append(item)
                else:
                    grouped_anomalies.append(current_group)
                    current_group = [item]
            grouped_anomalies.append(current_group)

        result_lines = []
        result_lines.extend(head)
        
        last_kept_idx = k
        
        for group in grouped_anomalies:
            group_start = group[0][0]
            group_end = group[-1][0]
            
            omitted_before = group_start - last_kept_idx - 1
            if omitted_before > 0:
                result_lines.append(f"... [omitted {omitted_before} lines] ...")
                
            result_lines.append(f"--- Preserved anomaly/error lines {group_start}-{group_end} ---")
            for orig_idx, line in group:
                result_lines.append(f"[Line {orig_idx}] {line}")
                
            last_kept_idx = group_end
            
        omitted_after = (n - k) - last_kept_idx
        if omitted_after > 0:
            result_lines.append(f"... [omitted {omitted_after} lines] ...")
            
        result_lines.extend(tail)
        
        return "\n".join(result_lines)
