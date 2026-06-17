import pytest
import json
import tempfile
import os
from antigravity_headroom.compressors.text_compressor import TextCompressor
from antigravity_headroom.compressors.json_crusher import JsonCrusher
from antigravity_headroom.compressors.code_compressor import CodeCompressor
from antigravity_headroom.compressors.log_crusher import LogCrusher
from antigravity_headroom.router import HeadroomRouter
from antigravity_headroom.storage import HeadroomStorage

def test_text_compressor():
    compressor = TextCompressor()
    text = (
        "Hello World    \n"
        "   Indented   text   here   \n"
        "\n"
        "\n"
        "\n"
        "End of document."
    )
    expected = (
        "Hello World\n"
        "   Indented text here\n"
        "\n"
        "End of document."
    )
    assert compressor.compress(text) == expected

def test_json_crusher_list_truncation():
    crusher = JsonCrusher(k_elements=2, output_format='json')
    data = [
        {"id": 1, "status": "ok"},
        {"id": 2, "status": "ok"},
        {"id": 3, "status": "warn"}, # Anomaly!
        {"id": 4, "status": "ok"},
        {"id": 5, "status": "ok"},
        {"id": 6, "status": "ok"}
    ]
    
    compressed_str = crusher.compress(json.dumps(data), k_elements=2)
    compressed = json.loads(compressed_str)
    
    assert compressed["__type__"] == "truncated_list"
    assert len(compressed["head"]) == 2
    assert len(compressed["tail"]) == 2
    assert compressed["omitted_count"] == 2
    
    assert len(compressed["anomalies"]) == 1
    assert compressed["anomalies"][0]["original_index"] == 2
    assert compressed["anomalies"][0]["value"]["status"] == "warn"

def test_json_crusher_formats():
    crusher = JsonCrusher(k_elements=1)
    data = [
        {"id": 1, "name": "alice"},
        {"id": 2, "name": "bob"},
        {"id": 3, "name": "charlie"}
    ]
    json_text = json.dumps(data)
    
    # csv-schema
    csv_out = crusher.compress(json_text, output_format='csv-schema', k_elements=1)
    assert "Path,Type,Value" in csv_out
    assert "truncated_list" in csv_out
    assert "(1 items omitted)" in csv_out
    
    # markdown-kv
    md_out = crusher.compress(json_text, output_format='markdown-kv', k_elements=1)
    assert "List (Truncated)" in md_out
    assert "Head" in md_out
    assert "Tail" in md_out

def test_code_compressor_python():
    compressor = CodeCompressor()
    code = (
        "def top_level(x):\n"
        "    y = x + 1\n"
        "    return y\n"
        "\n"
        "class Helper:\n"
        "    def method(self):\n"
        "        # Comments here\n"
        "        print('hello')\n"
        "        return True\n"
    )
    
    compressed = compressor.compress(code, language='python')
    assert "<<ccr:" in compressed
    assert "python" in compressed
    assert "def top_level(x):" in compressed
    assert "class Helper:" in compressed
    assert "def method(self):" in compressed
    assert "y = x + 1" not in compressed
    assert "print('hello')" not in compressed

def test_code_compressor_curly_braces():
    compressor = CodeCompressor()
    js_code = (
        "function calculate(a, b) {\n"
        "    let result = a + b;\n"
        "    console.log(result);\n"
        "    return result;\n"
        "}\n"
        "function short() { return; }\n"
    )
    
    compressed = compressor.compress(js_code, language='javascript')
    assert "<<ccr:" in compressed
    assert "javascript" in compressed
    assert "let result = a + b" not in compressed
    assert "short() { return; }" in compressed

def test_log_crusher():
    crusher = LogCrusher(k_lines=3)
    log_text = (
        "LINE 1: init\n"
        "LINE 2: start\n"
        "LINE 3: running\n"
        "LINE 4: ok\n"
        "LINE 5: ok\n"
        "LINE 6: ERROR failed connection\n"
        "LINE 7: ok\n"
        "LINE 8: ok\n"
        "LINE 9: stopped\n"
        "LINE 10: exit\n"
        "LINE 11: done\n"
    )
    compressed = crusher.compress(log_text, k_lines=3)
    
    assert "LINE 1: init" in compressed
    assert "LINE 11: done" in compressed
    assert "LINE 4: ok" not in compressed
    assert "Preserved anomaly/error lines 6-6" in compressed
    assert "[Line 6] LINE 6: ERROR failed connection" in compressed

def test_router():
    router = HeadroomRouter()
    
    json_text = '{"a": 1, "b": [2, 3, 4, 5, 6, 7, 8, 9, 10]}'
    # Preserving user modification
    compressed_json = router.route_and_compress(json_text, filename="test.json", k_elements=2)
    assert "truncated_list" in compressed_json
    
    py_code = "def foo():\n    print('hello')\n    return"
    compressed_code = router.route_and_compress(py_code, filename="test.py")
    assert "<<ccr:" in compressed_code
    
    log_text = "[INFO] Log line 1\n[INFO] Log line 2\n[ERROR] DB failed\n[INFO] Log line 4\n[INFO] Log line 5\n[INFO] Log line 6\n[INFO] Log line 7\n[INFO] Log line 8\n[INFO] Log line 9\n[INFO] Log line 10\n[INFO] Log line 11\n[INFO] Log line 12"
    compressed_log = router.route_and_compress(log_text, k_lines=2)
    assert "Preserved anomaly/error lines" in compressed_log

# Review Round 1 Coverage Gap Tests

def test_malformed_json_fallback():
    crusher = JsonCrusher()
    bad_json = "{'a': 1, 'b': [1,2,3]"
    result = crusher.compress(bad_json)
    assert "{'a': 1, 'b': [1,2,3]" in result

def test_empty_and_whitespace_inputs():
    text_c = TextCompressor()
    json_c = JsonCrusher()
    code_c = CodeCompressor()
    log_c = LogCrusher()
    
    for c in [text_c, json_c, code_c, log_c]:
        assert c.compress("") == ""
        assert c.compress("   \n   ") == ""

def test_code_without_classes_or_functions():
    compressor = CodeCompressor()
    code = (
        "x = 10\n"
        "y = 20\n"
        "print(x + y)\n"
    )
    assert compressor.compress(code, language='python') == code
    assert compressor.compress(code, language='javascript') == code

def test_k_zero_and_negative_parameters():
    # JsonCrusher with K=0
    json_c = JsonCrusher(k_elements=0)
    data = [1, 2, 3, 4, 5]
    res_str = json_c.compress(json.dumps(data), k_elements=0)
    res = json.loads(res_str)
    assert res["__type__"] == "truncated_list"
    assert res["head"] == []
    assert res["tail"] == []
    assert res["omitted_count"] == 5
    
    # JsonCrusher with negative K
    res_str_neg = json_c.compress(json.dumps(data), k_elements=-2)
    res_neg = json.loads(res_str_neg)
    assert res_neg["head"] == []
    assert res_neg["tail"] == []
    assert res_neg["omitted_count"] == 5
    
    # LogCrusher with K=0
    log_c = LogCrusher(k_lines=0)
    logs = "L1\nL2\nL3\nL4\nL5"
    res_log = log_c.compress(logs, k_lines=0)
    assert res_log == "... [omitted 5 lines] ..."

    # LogCrusher with negative K
    res_log_neg = log_c.compress(logs, k_lines=-10)
    assert res_log_neg == "... [omitted 5 lines] ..."

def test_escaped_backslash_in_strings():
    compressor = CodeCompressor()
    code = (
        "function main() {\n"
        "    let path = \"C:\\\\\";\n"
        "    if (true) {\n"
        "        console.log(path);\n"
        "    }\n"
        "}\n"
    )
    compressed = compressor.compress(code, language='javascript')
    assert "<<ccr:" in compressed
    assert "javascript" in compressed
    assert "console.log" not in compressed

# Upgrade Phase Tests

def test_cache_aligner():
    from antigravity_headroom.compressors.cache_aligner import CacheAligner
    aligner = CacheAligner()
    text = (
        "UUID: d3b07384-d113-4956-a5db-251a998c919d\n"
        "Time: 2026-06-18T02:36:08Z\n"
        "Date: 2026-06-18\n"
        "Git Commit: 9f82734a1b0293c4d5e6f7a8b9c0d1e2f3a4b5c6\n"
    )
    normalized = aligner.normalize(text)
    assert "[UUID]" in normalized
    assert "[DATETIME]" in normalized
    assert "[DATE]" in normalized
    assert "[COMMIT_HASH]" in normalized

def test_tabular_crusher():
    from antigravity_headroom.compressors.tabular_crusher import TabularCrusher
    crusher = TabularCrusher(k_rows=2)
    
    csv_data = (
        "id,name,status\n"
        "1,alice,ok\n"
        "2,bob,ok\n"
        "3,charlie,failed\n"\
        "4,dave,ok\n"\
        "5,eve,ok\n"\
        "6,frank,ok\n"\
        "7,grace,ok\n"
    )
    
    compressed = crusher.compress(csv_data, k_rows=2)
    lines = compressed.splitlines()
    assert lines[0] == "id,name,status"
    assert lines[1] == "1,alice,ok"
    assert lines[2] == "2,bob,ok"
    assert "[Row 4],3,charlie,failed" in compressed
    assert "... [omitted 2 rows] ..." in compressed
    assert lines[-2] == "6,frank,ok"
    assert lines[-1] == "7,grace,ok"

def test_decompression_engine():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        storage = HeadroomStorage(db_path=db_path)
        router = HeadroomRouter(storage=storage)
        
        original_code = (
            "def task(x):\n"
            "    print('execute')\n"
            "    return x * 2\n"
        )
        
        compressed = router.route_and_compress(original_code, filename="script.py")
        assert "<<ccr:" in compressed
        
        decompressed = router.decompress(compressed)
        assert decompressed == original_code
    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass

def test_json_crusher_recursion_limit():
    crusher = JsonCrusher()
    # Create a deeply nested dict structure of depth 1050
    # A depth of 1050 would normally exceed Python's recursion limit (default 1000)
    nested = {}
    curr = nested
    for _ in range(1050):
        curr['child'] = {}
        curr = curr['child']
        
    # Check has_anomaly doesn't raise RecursionError and returns False
    assert crusher.has_anomaly(nested) is False
    
    # Check crush_json_data doesn't raise RecursionError and returns data
    crushed = crusher.crush_json_data(nested, k=2)
    assert isinstance(crushed, dict)

def test_cli_run_without_shell_safe():
    from click.testing import CliRunner
    from antigravity_headroom.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ['--db-path', ':memory:', 'run', 'hostname'])
    assert res.exit_code == 0
    assert len(res.output.strip()) > 0

def test_cli_run_with_metacharacters_fails():
    from click.testing import CliRunner
    from antigravity_headroom.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ['--db-path', ':memory:', 'run', 'echo hello && echo world'])
    assert res.exit_code != 0
    assert "Error: Command contains shell metacharacters" in res.output

def test_cli_run_with_shell_flag():
    from click.testing import CliRunner
    from antigravity_headroom.cli import cli

    runner = CliRunner()
    res = runner.invoke(cli, ['--db-path', ':memory:', 'run', '--shell', 'echo hello || echo world'])
    # Validation error should not be present
    assert "Error: Command contains shell metacharacters" not in res.output
