import os
import tempfile
import time
import threading
import pytest
from antigravity_headroom.storage import HeadroomStorage

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass

def test_store_and_retrieve(temp_db):
    storage = HeadroomStorage(db_path=temp_db, ttl=300)
    content = "Hello, Headroom storage test!"
    
    # Store
    content_hash = storage.store(content)
    assert len(content_hash) == 64  # SHA-256 hex is 64 chars
    
    # Retrieve
    retrieved = storage.retrieve(content_hash)
    assert retrieved == content

def test_ttl_eviction(temp_db):
    # Set TTL to 1 second
    storage = HeadroomStorage(db_path=temp_db, ttl=1)
    content = "Temporary data"
    
    content_hash = storage.store(content)
    assert storage.retrieve(content_hash) == content
    
    # Wait for TTL to expire
    time.sleep(1.2)
    
    assert storage.retrieve(content_hash) is None

def test_bm25_retrieval(temp_db):
    storage = HeadroomStorage(db_path=temp_db, ttl=300)
    
    doc1 = "Python ast-based code compression for headroom"
    doc2 = "Rust programming and cargo build tools"
    doc3 = "SQLite database for context storage with TTL support"
    
    storage.store(doc1)
    storage.store(doc2)
    storage.store(doc3)
    
    # Match doc2
    match = storage.retrieve_bm25("cargo rust programming")
    assert match == doc2
    
    # Match doc3
    match = storage.retrieve_bm25("sqlite TTL database")
    assert match == doc3

def test_thread_safety(temp_db):
    storage = HeadroomStorage(db_path=temp_db, ttl=300)
    num_threads = 10
    loops = 20
    errors = []

    def worker(worker_id):
        try:
            for i in range(loops):
                content = f"Thread {worker_id} content item {i}"
                h = storage.store(content)
                retrieved = storage.retrieve(h)
                assert retrieved == content
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    assert len(errors) == 0, f"Thread safety errors: {errors}"

def test_db_file_permissions():
    import stat
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        os.remove(path)
    except OSError:
        pass
        
    try:
        # DB does not exist, initializing storage will create it and apply chmod 0o600
        storage = HeadroomStorage(db_path=path)
        assert os.path.exists(path)
        
        if os.name == 'posix':
            mode = os.stat(path).st_mode
            assert stat.S_IMODE(mode) == 0o600
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
