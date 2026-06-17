import sqlite3
import hashlib
import time
import threading
import re
import math
import os
from typing import Optional, Dict, List, Tuple

def tokenize(text: str) -> List[str]:
    return re.findall(r'\w+', text.lower())

class HeadroomStorage:
    def __init__(self, db_path: str = None, ttl: int = 300):
        if db_path is None:
            db_path = os.path.expanduser("~/.antigravity_headroom.db")
        self.db_path = db_path
        self.ttl = ttl
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        is_local = not self.db_path.startswith(":memory:")
        db_existed = os.path.exists(self.db_path) if is_local else True
        
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            if is_local and not db_existed:
                try:
                    os.chmod(self.db_path, 0o600)
                except OSError:
                    pass
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS headroom_store (
                        hash TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS headroom_metadata (
                        key TEXT PRIMARY KEY,
                        value INTEGER DEFAULT 0
                    )
                """)
                # Initialize default keys
                for k in ['hits', 'misses', 'saved_bytes']:
                    cursor.execute(
                        "INSERT OR IGNORE INTO headroom_metadata (key, value) VALUES (?, 0)",
                        (k,)
                    )
                conn.commit()
            finally:
                conn.close()

    def store(self, content: str) -> str:
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        now = time.time()
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            try:
                cursor = conn.cursor()
                # Check if hash already exists to prevent double-counting savings
                cursor.execute("SELECT 1 FROM headroom_store WHERE hash = ?", (content_hash,))
                exists = cursor.fetchone() is not None
                
                cursor.execute(
                    "INSERT OR REPLACE INTO headroom_store (hash, content, created_at) VALUES (?, ?, ?)",
                    (content_hash, content, now)
                )
                
                if not exists:
                    # Update savings: original length minus token overhead (approx 80 bytes)
                    savings = max(0, len(content) - 80)
                    cursor.execute(
                        "UPDATE headroom_metadata SET value = value + ? WHERE key = 'saved_bytes'",
                        (savings,)
                    )
                conn.commit()
            finally:
                conn.close()
        return content_hash

    def retrieve(self, content_hash: str) -> Optional[str]:
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            try:
                self._clean_expired_unlocked(conn)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT content FROM headroom_store WHERE hash = ?",
                    (content_hash,)
                )
                row = cursor.fetchone()
                if row:
                    cursor.execute("UPDATE headroom_metadata SET value = value + 1 WHERE key = 'hits'")
                    conn.commit()
                    return row[0]
                else:
                    cursor.execute("UPDATE headroom_metadata SET value = value + 1 WHERE key = 'misses'")
                    conn.commit()
            finally:
                conn.close()
        return None

    def retrieve_bm25(self, query: str) -> Optional[str]:
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            try:
                self._clean_expired_unlocked(conn)
                cursor = conn.cursor()
                cursor.execute("SELECT hash, content FROM headroom_store")
                docs = cursor.fetchall()
            finally:
                conn.close()
        
        if not docs:
            return None
        
        query_tokens = tokenize(query)
        if not query_tokens:
            return None
        
        N = len(docs)
        doc_tokens = {}
        doc_lengths = []
        doc_tf = {}  # hash -> token -> count
        df = {}      # token -> count of docs containing token
        
        for doc_hash, content in docs:
            tokens = tokenize(content)
            doc_tokens[doc_hash] = tokens
            doc_lengths.append(len(tokens))
            tf = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            doc_tf[doc_hash] = tf
            for token in tf:
                df[token] = df.get(token, 0) + 1
                
        avgdl = sum(doc_lengths) / N if N > 0 else 0
        k1 = 1.5
        b = 0.75
        
        best_content = None
        best_score = -1.0
        
        for doc_hash, content in docs:
            score = 0.0
            tokens = doc_tokens[doc_hash]
            dl = len(tokens)
            tf = doc_tf[doc_hash]
            
            for q in query_tokens:
                if q not in df:
                    continue
                # IDF
                nq = df[q]
                idf = math.log((N - nq + 0.5) / (nq + 0.5) + 1.0)
                
                # TF score
                fq = tf.get(q, 0)
                numerator = fq * (k1 + 1)
                denominator = fq + k1 * (1.0 - b + b * (dl / avgdl) if avgdl > 0 else 1.0)
                score += idf * (numerator / denominator)
                
            if score > best_score and score > 0:
                best_score = score
                best_content = content
                
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            try:
                cursor = conn.cursor()
                if best_content is not None:
                    cursor.execute("UPDATE headroom_metadata SET value = value + 1 WHERE key = 'hits'")
                else:
                    cursor.execute("UPDATE headroom_metadata SET value = value + 1 WHERE key = 'misses'")
                conn.commit()
            finally:
                conn.close()
                
        return best_content

    def _clean_expired_unlocked(self, conn: sqlite3.Connection):
        now = time.time()
        cutoff = now - self.ttl
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM headroom_store WHERE created_at < ?",
            (cutoff,)
        )
        conn.commit()

    def clean_expired(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            try:
                self._clean_expired_unlocked(conn)
            finally:
                conn.close()

    def clear_cache(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM headroom_store")
                cursor.execute("UPDATE headroom_metadata SET value = 0")
                conn.commit()
            finally:
                conn.close()

    def get_stats(self) -> dict:
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            try:
                self._clean_expired_unlocked(conn)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*), SUM(LENGTH(content)) FROM headroom_store")
                count, total_bytes = cursor.fetchone()
                
                cursor.execute("SELECT key, value FROM headroom_metadata")
                meta = {k: v for k, v in cursor.fetchall()}
                
                hits = meta.get('hits', 0)
                misses = meta.get('misses', 0)
                saved_bytes = meta.get('saved_bytes', 0)
                
                total_retrievals = hits + misses
                hit_ratio = (hits / total_retrievals) if total_retrievals > 0 else 0.0
                
                return {
                    "count": count or 0,
                    "total_bytes": total_bytes or 0,
                    "db_path": self.db_path,
                    "ttl": self.ttl,
                    "hits": hits,
                    "misses": misses,
                    "hit_ratio": hit_ratio,
                    "saved_bytes": saved_bytes
                }
            finally:
                conn.close()
