import csv
import io
import re
from .base import BaseCompressor

class TabularCrusher(BaseCompressor):
    def __init__(self, k_rows: int = 5):
        self.k_rows = k_rows
        self.anomaly_patterns = [
            re.compile(r'error', re.IGNORECASE),
            re.compile(r'fail', re.IGNORECASE),
            re.compile(r'exception', re.IGNORECASE),
            re.compile(r'warn', re.IGNORECASE),
            re.compile(r'critical', re.IGNORECASE),
            re.compile(r'fatal', re.IGNORECASE),
        ]

    def is_anomaly(self, row: list) -> bool:
        for val in row:
            if any(pat.search(str(val)) for pat in self.anomaly_patterns):
                return True
        return False

    def compress(self, text: str, **kwargs) -> str:
        if not text or not text.strip():
            return ""

        k = kwargs.get('k_rows', self.k_rows)
        k = max(0, k)

        delimiter = kwargs.get('delimiter')
        if not delimiter:
            first_line = text.splitlines()[0] if text else ""
            if '\t' in first_line:
                delimiter = '\t'
            else:
                delimiter = ','

        f = io.StringIO(text)
        reader = csv.reader(f, delimiter=delimiter)
        try:
            rows = list(reader)
        except Exception:
            return text

        if not rows:
            return text

        header = rows[0]
        data_rows = rows[1:]
        n = len(data_rows)

        if k == 0:
            head = []
            tail = []
            middle_rows = data_rows
        elif n <= 2 * k:
            return text
        else:
            head = data_rows[:k]
            tail = data_rows[-k:]
            middle_rows = data_rows[k:-k]

        anomalies = []
        for idx, row in enumerate(middle_rows):
            original_idx = k + idx + 1
            if self.is_anomaly(row):
                anomalies.append((original_idx, row))

        out = io.StringIO()
        writer = csv.writer(out, delimiter=delimiter, lineterminator='\n')
        
        # Write header
        writer.writerow(header)

        # Write head
        for row in head:
            writer.writerow(row)

        last_kept_idx = k

        for idx, row in anomalies:
            omitted_before = idx - last_kept_idx - 1
            if omitted_before > 0:
                writer.writerow([f"... [omitted {omitted_before} rows] ..."] + [""] * (len(header) - 1))
            writer.writerow([f"[Row {idx + 1}]"] + row)
            last_kept_idx = idx

        omitted_after = (n - k) - last_kept_idx
        if omitted_after > 0:
            writer.writerow([f"... [omitted {omitted_after} rows] ..."] + [""] * (len(header) - 1))

        # Write tail
        for row in tail:
            writer.writerow(row)

        return out.getvalue()
