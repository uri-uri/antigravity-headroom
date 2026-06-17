import json
import re
import csv
import io
from .base import BaseCompressor
from .text_compressor import TextCompressor

class JsonCrusher(BaseCompressor):
    max_depth = 100

    def __init__(self, k_elements: int = 5, output_format: str = 'json'):
        self.k_elements = k_elements
        self.output_format = output_format
        self.anomaly_pattern = re.compile(r'(error|fail|exception|warn|critical|fatal)', re.IGNORECASE)
        self.max_depth = 100

    def has_anomaly(self, val, depth=0) -> bool:
        if depth > self.max_depth:
            return False
        if isinstance(val, str):
            return bool(self.anomaly_pattern.search(val))
        elif isinstance(val, dict):
            for k, v in val.items():
                if bool(self.anomaly_pattern.search(str(k))) or self.has_anomaly(v, depth + 1):
                    return True
        elif isinstance(val, (list, tuple)):
            for item in val:
                if self.has_anomaly(item, depth + 1):
                    return True
        return False

    def crush_json_data(self, data, k: int, depth=0):
        if depth > self.max_depth:
            return data
        k = max(0, k)
        if isinstance(data, list):
            if k == 0:
                head = []
                tail = []
                anomalies = []
                omitted_count = len(data)
                for idx, x in enumerate(data):
                    if self.has_anomaly(x, depth + 1):
                        anomalies.append({
                            "original_index": idx,
                            "value": self.crush_json_data(x, 0, depth + 1)
                        })
                return {
                    "__type__": "truncated_list",
                    "head": head,
                    "tail": tail,
                    "anomalies": anomalies,
                    "omitted_count": omitted_count
                }
            elif len(data) <= 2 * k:
                return [self.crush_json_data(x, k, depth + 1) for x in data]
            else:
                head = [self.crush_json_data(x, k, depth + 1) for x in data[:k]]
                tail = [self.crush_json_data(x, k, depth + 1) for x in data[-k:]]
                anomalies = []
                omitted_count = len(data) - 2 * k
                for idx, x in enumerate(data[k:-k]):
                    if self.has_anomaly(x, depth + 1):
                        anomalies.append({
                            "original_index": k + idx,
                            "value": self.crush_json_data(x, k, depth + 1)
                        })
                return {
                    "__type__": "truncated_list",
                    "head": head,
                    "tail": tail,
                    "anomalies": anomalies,
                    "omitted_count": omitted_count
                }
        elif isinstance(data, dict):
            return {k_key: self.crush_json_data(v_val, k, depth + 1) for k_key, v_val in data.items()}
        return data

    def compress(self, text: str, **kwargs) -> str:
        k = kwargs.get('k_elements', self.k_elements)
        fmt = kwargs.get('output_format', self.output_format)
        
        # Guard against empty/whitespace inputs
        if not text or not text.strip():
            return ""
            
        try:
            data = json.loads(text)
        except Exception:
            # Fallback if text is not valid JSON
            return TextCompressor().compress(text)
            
        crushed_data = self.crush_json_data(data, k)
        
        if fmt == 'json':
            return json.dumps(crushed_data, indent=2)
        elif fmt == 'csv-schema':
            return self.to_csv_schema(crushed_data)
        elif fmt == 'markdown-kv':
            return self.to_markdown_kv(crushed_data)
        else:
            return json.dumps(crushed_data, indent=2)

    def to_csv_schema(self, data) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Path", "Type", "Value"])
        
        def write_flat(path, val):
            if isinstance(val, dict) and val.get("__type__") == "truncated_list":
                writer.writerow([path, "truncated_list", f"({val['omitted_count']} items omitted)"])
                # Head
                for i, item in enumerate(val["head"]):
                    write_flat(f"{path}[{i}]" if path else f"[{i}]", item)
                # Anomalies
                for anom in val["anomalies"]:
                    orig_idx = anom["original_index"]
                    write_flat(f"{path}[{orig_idx}] (ANOMALY)" if path else f"[{orig_idx}] (ANOMALY)", anom["value"])
                # Tail
                for i, item in enumerate(val["tail"]):
                    write_flat(f"{path}[tail_{i}]" if path else f"[tail_{i}]", item)
            elif isinstance(val, dict):
                for k, v in val.items():
                    sub_path = f"{path}.{k}" if path else k
                    write_flat(sub_path, v)
            elif isinstance(val, list):
                for i, item in enumerate(val):
                    write_flat(f"{path}[{i}]" if path else f"[{i}]", item)
            else:
                writer.writerow([path, type(val).__name__, str(val)])
                
        write_flat("", data)
        return output.getvalue()

    def to_markdown_kv(self, data, indent=0) -> str:
        pad = "  " * indent
        if isinstance(data, dict) and data.get("__type__") == "truncated_list":
            lines = []
            lines.append(f"{pad}* **List (Truncated)**: {data['omitted_count']} items omitted")
            lines.append(f"{pad}  * **Head (First {len(data['head'])} items):**")
            for idx, item in enumerate(data["head"]):
                lines.append(f"{pad}    * [{idx}]:")
                lines.append(self.to_markdown_kv(item, indent + 3))
            
            if data["anomalies"]:
                lines.append(f"{pad}  * **Anomalies Found:**")
                for anom in data["anomalies"]:
                    lines.append(f"{pad}    * [Index {anom['original_index']}]:")
                    lines.append(self.to_markdown_kv(anom["value"], indent + 3))
                    
            lines.append(f"{pad}  * **Tail (Last {len(data['tail'])} items):**")
            for idx, item in enumerate(data["tail"]):
                real_idx = len(data["head"]) + data["omitted_count"] + idx
                lines.append(f"{pad}    * [{real_idx}]:")
                lines.append(self.to_markdown_kv(item, indent + 3))
            return "\n".join(lines)
        elif isinstance(data, dict):
            lines = []
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{pad}* **{k}**:")
                    lines.append(self.to_markdown_kv(v, indent + 1))
                else:
                    lines.append(f"{pad}* **{k}**: {v}")
            return "\n".join(lines)
        elif isinstance(data, list):
            lines = []
            for idx, item in enumerate(data):
                lines.append(f"{pad}* [{idx}]:")
                lines.append(self.to_markdown_kv(item, indent + 1))
            return "\n".join(lines)
        else:
            return f"{pad}{data}"
