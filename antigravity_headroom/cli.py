import sys
import os
import click
import subprocess
import shlex
from antigravity_headroom.storage import HeadroomStorage
from antigravity_headroom.router import HeadroomRouter

@click.group()
@click.option('--db-path', type=click.Path(), help='Path to SQLite database.')
@click.option('--ttl', type=int, default=300, help='Time to live for stored contents (seconds).')
@click.pass_context
def cli(ctx, db_path, ttl):
    """Antigravity Headroom: Context Compression Tool"""
    ctx.ensure_object(dict)
    ctx.obj['storage'] = HeadroomStorage(db_path=db_path, ttl=ttl)
    ctx.obj['router'] = HeadroomRouter(storage=ctx.obj['storage'])

@cli.command()
@click.argument('input_file', type=click.Path(exists=True), required=False)
@click.option('--format', type=click.Choice(['json', 'csv-schema', 'markdown-kv']), default='json', help='Output format for JSON.')
@click.option('--k-elements', type=int, default=5, help='Number of elements to keep (JSON).')
@click.option('--k-lines', type=int, default=20, help='Number of lines to keep (Logs).')
@click.option('--k-rows', type=int, default=5, help='Number of rows to keep (CSV/TSV).')
@click.option('--align', is_flag=True, help='Enable prompt cache alignment normalization.')
@click.pass_context
def compress(ctx, input_file, format, k_elements, k_lines, k_rows, align):
    """Compress text from a file or stdin."""
    if input_file:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        filename = os.path.basename(input_file)
    else:
        text = sys.stdin.read()
        filename = None

    router = ctx.obj['router']
    compressed = router.route_and_compress(
        text, 
        filename=filename, 
        output_format=format, 
        k_elements=k_elements, 
        k_lines=k_lines,
        k_rows=k_rows,
        align=align
    )
    click.echo(compressed)

@cli.command()
@click.argument('input_file', type=click.Path(exists=True), required=False)
@click.pass_context
def decompress(ctx, input_file):
    """Reconstruct original text by inflating retrieval tokens."""
    if input_file:
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    router = ctx.obj['router']
    decompressed = router.decompress(text)
    click.echo(decompressed)

@cli.command()
@click.argument('token_or_hash', required=False)
@click.option('--query', help='Perform BM25 search query to retrieve content.')
@click.pass_context
def retrieve(ctx, token_or_hash, query):
    """Retrieve original content by hash, token, or BM25 query."""
    storage = ctx.obj['storage']
    
    if query:
        result = storage.retrieve_bm25(query)
        if result:
            click.echo(result)
        else:
            click.echo("Error: No matching document found.", err=True)
            sys.exit(1)
        return

    if not token_or_hash:
        click.echo("Error: Must provide a token/hash or use --query.", err=True)
        sys.exit(1)

    content_hash = token_or_hash
    if "<<ccr:" in token_or_hash:
        parts = token_or_hash.replace("<<ccr:", "").replace(">>", "").split(",")
        if parts:
            content_hash = parts[0].strip()

    result = storage.retrieve(content_hash)
    if result:
        click.echo(result)
    else:
        click.echo(f"Error: Hash/Token {content_hash} not found or expired.", err=True)
        sys.exit(1)

@cli.command()
@click.argument('command')
@click.option('--k-lines', type=int, default=20, help='Number of lines to keep for log output.')
@click.option('--shell', is_flag=True, default=False, help='Run command in shell mode (allows shell metacharacters).')
@click.pass_context
def run(ctx, command, k_lines, shell):
    """Run a shell command, capture and compress its output using LogCrusher."""
    click.echo(f"Running command: {command}...\n", err=True)
    
    if shell:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
    else:
        metachars = ['|', ';', '&&', '||', '>', '<', '&', '$', '`']
        if any(char in command for char in metachars):
            click.echo("Error: Command contains shell metacharacters. If you want to run this command in a shell, explicitly pass the --shell flag.", err=True)
            sys.exit(1)
            
        cmd_args = shlex.split(command)
        process = subprocess.Popen(
            cmd_args,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
    
    stdout_data, _ = process.communicate()
    
    router = ctx.obj['router']
    compressed = router.log_crusher.compress(stdout_data, k_lines=k_lines)
    
    click.echo(compressed)
    sys.exit(process.returncode)

@cli.command()
@click.option('--clear', is_flag=True, help='Clear all caches and statistics in SQLite.')
@click.option('--clean', is_flag=True, help='Evict expired cache entries immediately.')
@click.pass_context
def stats(ctx, clear, clean):
    """Show cache statistics, size, hit/miss ratios, or clear caches."""
    storage = ctx.obj['storage']
    
    if clear:
        storage.clear_cache()
        click.echo("Cache cleared and metadata statistics reset successfully.")
        return
        
    if clean:
        storage.clean_expired()
        click.echo("Expired cache entries cleaned successfully.")
        return

    s = storage.get_stats()
    click.echo("=== Antigravity Headroom Cache Stats ===")
    click.echo(f"Database Path:   {s['db_path']}")
    click.echo(f"Configured TTL:  {s['ttl']} seconds")
    click.echo(f"Cached Blocks:   {s['count']}")
    click.echo(f"Cache Size:      {s['total_bytes']} bytes")
    click.echo(f"Cache Hits:      {s['hits']}")
    click.echo(f"Cache Misses:    {s['misses']}")
    click.echo(f"Hit/Miss Ratio:  {s['hit_ratio']:.2%}")
    click.echo(f"Total Savings:   {s['saved_bytes']} bytes")

@cli.command()
@click.pass_context
def mcp(ctx):
    """Run the stdio MCP server."""
    from antigravity_headroom.mcp_server import mcp as mcp_instance
    import antigravity_headroom.mcp_server as mcp_module
    
    mcp_module.storage = ctx.obj['storage']
    mcp_module.router = ctx.obj['router']
    
    mcp_instance.run()

if __name__ == '__main__':
    cli()
