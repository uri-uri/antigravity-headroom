# Antigravity Headroom - Session Pickup Instructions

Welcome back! This file is designed to help you (the next AI agent session, running under Claude Code, Codex CLI, or Antigravity) instantly pick up the state of the codebase and continue developing or testing.

## 📌 Context Overview

**Antigravity Headroom** is a context-aware token compression and retrieval (CCR) utility customized for agentic workflows.
It strips boilerplate function bodies, repetitive logs, and tabular data, caching them in a local SQLite database and replacing them with short tokens (e.g. `<<ccr:hash,lang,size>>`). If the LLM needs the original details, it retrieves them inline using the MCP server or the CLI.

- **Workspace Path**: `C:/Users/user/antigravity-headroom`
- **GitHub Repository**: `https://github.com/uri-uri/antigravity-headroom`
- **Current Status**: All implementation and security hardening complete. All **24/24 unit tests pass**.

---

## 📂 Core Code Map

- [antigravity_headroom/](file:///C:/Users/user/antigravity-headroom/antigravity_headroom):
  - [storage.py](file:///C:/Users/user/antigravity-headroom/antigravity_headroom/storage.py): SQLite local cache with owner-only file permissions (`0o600`), automatic TTL (default 5m), and BM25 text retrieval.
  - [router.py](file:///C:/Users/user/antigravity-headroom/antigravity_headroom/router.py): Routes file paths, MIME-types, and heuristically detects text type. Contains `decompress()` for inline tag replacement.
  - [compressors/](file:///C:/Users/user/antigravity-headroom/antigravity_headroom/compressors):
    - [json_crusher.py](file:///C:/Users/user/antigravity-headroom/antigravity_headroom/compressors/json_crusher.py): statistical array truncation, CSV/Markdown formatting, and recursion depth limit protection.
    - [code_compressor.py](file:///C:/Users/user/antigravity-headroom/antigravity_headroom/compressors/code_compressor.py): Python AST-based method body stripping, and curly-brace language regex signature parser.
    - [log_crusher.py](file:///C:/Users/user/antigravity-headroom/antigravity_headroom/compressors/log_crusher.py): Collapses repetitive stdout logs, preserving stack traces and errors.
    - [tabular_crusher.py](file:///C:/Users/user/antigravity-headroom/antigravity_headroom/compressors/tabular_crusher.py): Row-based CSV/TSV table compressor.
    - [cache_aligner.py](file:///C:/Users/user/antigravity-headroom/antigravity_headroom/compressors/cache_aligner.py): Normalizes volatile date/times, UUIDs, and git commits to static placeholders.
  - [cli.py](file:///C:/Users/user/antigravity-headroom/antigravity_headroom/cli.py): CLI interface (adds `--shell` command verification).
  - [mcp_server.py](file:///C:/Users/user/antigravity-headroom/antigravity_headroom/mcp_server.py): Stdio MCP server registration.
- [tests/](file:///C:/Users/user/antigravity-headroom/tests):
  - [test_compressors.py](file:///C:/Users/user/antigravity-headroom/tests/test_compressors.py) (Unit tests for compressors, cli, cache_aligner, tabular, decompressor, and security depth limits).
  - [test_storage.py](file:///C:/Users/user/antigravity-headroom/tests/test_storage.py) (Unit tests for SQLite storage, BM25, thread safety, and DB file permissions).

---

## 🏃 Quick Commands to Verify

To verify everything is active, run the following commands in the workspace:

```bash
# 1. Run the test suite
python -m pytest tests/

# 2. Check CLI commands
python -m antigravity_headroom.cli --help

# 3. View database statistics
python -m antigravity_headroom.cli stats
```

---

## 🎯 Proposed Next Tasks

When the user runs `/pickup`, please read this file and propose these options:

1. **Test MCP Server Integration**: Set up the headroom MCP server configuration locally and verify that Claude / Cursor can call its tools.
2. **Implement Custom Language Support**: Add syntax signatures or regex patterns in `CodeCompressor` for other programming languages (like SQL, HTML/XML, PHP).
3. **Database Performance Tuning**: Analyze latency metrics and adjust SQLite connection timeouts or indexes for heavy concurrent read/write workloads.
4. **General Enhancements**: Ask the user if they want to build any specific client integrations or wrapper scripts for local developer tools.
