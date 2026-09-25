import os
import hashlib
import sqlite3
import threading
from typing import Dict, List, Optional, Tuple, Any

class TranslationCache:
    """
    Persistent SQLite caching layer for translation requests.
    Keyed by (src_lang, tgt_lang, text_hash).
    Uses WAL mode for high-throughput concurrent reads and writes.
    """
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            default_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
            os.makedirs(default_dir, exist_ok=True)
            db_path = os.getenv("TRANSLATION_CACHE_DB", os.path.join(default_dir, "translation_cache.db"))
        
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS translation_cache (
                        src_lang TEXT NOT NULL,
                        tgt_lang TEXT NOT NULL,
                        text_hash TEXT NOT NULL,
                        original_text TEXT NOT NULL,
                        translated_text TEXT NOT NULL,
                        scheme_slug TEXT DEFAULT '',
                        model_version TEXT DEFAULT 'indictrans2-dist-200m',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (src_lang, tgt_lang, text_hash)
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_trans_cache 
                    ON translation_cache(src_lang, tgt_lang, text_hash);
                """)
        finally:
            conn.close()

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    def get(self, src_lang: str, tgt_lang: str, text: str) -> Optional[str]:
        if not text or not text.strip():
            return text
        thash = self.hash_text(text)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT translated_text FROM translation_cache WHERE src_lang = ? AND tgt_lang = ? AND text_hash = ?",
            (src_lang, tgt_lang, thash)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def get_batch(self, src_lang: str, tgt_lang: str, texts: List[str]) -> Dict[str, str]:
        """
        Returns a dictionary mapping text_hash -> translated_text for cached entries.
        """
        if not texts:
            return {}
        
        hashes = [self.hash_text(t) for t in texts if t and t.strip()]
        if not hashes:
            return {}
        
        unique_hashes = list(set(hashes))
        conn = self._get_connection()
        cursor = conn.cursor()
        
        results = {}
        chunk_size = 500
        for i in range(0, len(unique_hashes), chunk_size):
            chunk = unique_hashes[i:i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            query = f"""
                SELECT text_hash, translated_text 
                FROM translation_cache 
                WHERE src_lang = ? AND tgt_lang = ? AND text_hash IN ({placeholders})
            """
            cursor.execute(query, [src_lang, tgt_lang] + chunk)
            for thash, trans in cursor.fetchall():
                results[thash] = trans
        return results

    def set(
        self,
        src_lang: str,
        tgt_lang: str,
        original_text: str,
        translated_text: str,
        scheme_slug: str = "",
        model_version: str = "indictrans2-dist-200m"
    ) -> None:
        if not original_text or not original_text.strip() or not translated_text:
            return
        self.set_batch(
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            items=[(original_text, translated_text, scheme_slug)],
            model_version=model_version
        )

    def set_batch(
        self,
        src_lang: str,
        tgt_lang: str,
        items: List[Tuple[str, str, Optional[str]]],
        model_version: str = "indictrans2-dist-200m"
    ) -> None:
        """
        Store multiple translated texts in batch.
        items: List of (original_text, translated_text, scheme_slug) or (original_text, translated_text)
        """
        if not items:
            return
        
        records = []
        for item in items:
            if len(item) == 2:
                orig, trans = item  # type: ignore
                slug = ""
            else:
                orig, trans, slug = item  # type: ignore
                
            if not orig or not str(orig).strip() or not trans:
                continue
            thash = self.hash_text(orig)
            records.append((src_lang, tgt_lang, thash, orig.strip(), trans.strip(), slug or "", model_version))
            
        if not records:
            return
            
        conn = self._get_connection()
        try:
            with conn:
                conn.executemany("""
                    INSERT OR REPLACE INTO translation_cache 
                    (src_lang, tgt_lang, text_hash, original_text, translated_text, scheme_slug, model_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, records)
        except Exception as e:
            print(f"[CACHE] Warning: Failed writing batch to translation cache: {e}")

    def count(self) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM translation_cache")
        row = cursor.fetchone()
        return row[0] if row else 0

    def get_size_bytes(self) -> int:
        total = 0
        if os.path.exists(self.db_path):
            total += os.path.getsize(self.db_path)
        wal_path = f"{self.db_path}-wal"
        if os.path.exists(wal_path):
            total += os.path.getsize(wal_path)
        return total

    def stats(self) -> Dict[str, Any]:
        size = self.get_size_bytes()
        return {
            "total_entries": self.count(),
            "size_bytes": size,
            "size_kb": round(size / 1024, 2),
            "size_mb": round(size / (1024 * 1024), 3),
            "db_path": self.db_path
        }

    def clear(self) -> None:
        conn = self._get_connection()
        with conn:
            conn.execute("DELETE FROM translation_cache")

# Global singleton cache instance
translation_cache = TranslationCache()
