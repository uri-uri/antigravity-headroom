import os
import sys
import json
from mcp.server.fastmcp import FastMCP
from antigravity_headroom.storage import HeadroomStorage
from antigravity_headroom.router import HeadroomRouter

# Initialize storage and router with default global configurations
storage = HeadroomStorage()
router = HeadroomRouter(storage=storage)

mcp = FastMCP("Antigravity Headroom")

@mcp.tool()
def headroom_compress(text: str, filename: str = None, mime_type: str = None) -> str:
    """
    Compress a piece of content (JSON, Python code, log files, prose)
    and replace heavy components with retrieval tokens.
    Original parts are saved in SQLite storage.
    """
    return router.route_and_compress(text, filename=filename, mime_type=mime_type)

@mcp.tool()
def headroom_retrieve(token_or_hash: str = None, query: str = None) -> str:
    """
    Retrieve original content for a retrieval token or direct SHA-256 hash.
    If 'query' is specified, performs a BM25 similarity search across all stored contents
    to return the best match.
    At least token_or_hash or query must be provided.
    """
    if not token_or_hash and not query:
        return "Error: You must provide either token_or_hash or query."
        
    if query:
        result = storage.retrieve_bm25(query)
        if result:
            return result
        return "No document matching query found in storage."
        
    content_hash = token_or_hash
    if "<<ccr:" in token_or_hash:
        parts = token_or_hash.replace("<<ccr:", "").replace(">>", "").split(",")
        if parts:
            content_hash = parts[0].strip()
            
    result = storage.retrieve(content_hash)
    if result:
        return result
    return f"Content for hash/token {content_hash} not found or expired."

@mcp.tool()
def headroom_decompress(text: str) -> str:
    """
    Reconstruct the original text by replacing any <<ccr:hash,lang,size>> retrieval tokens
    inline with original cached contents from SQLite storage.
    """
    return router.decompress(text)

@mcp.tool()
def headroom_stats() -> str:
    """
    Get headroom storage stats, including count of cached blocks,
    total bytes cached, database path, and TTL.
    """
    stats = storage.get_stats()
    return json.dumps(stats, indent=2)

def run_server():
    mcp.run()
