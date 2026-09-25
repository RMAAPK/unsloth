from typing import Any, List, Optional
import os
import json

class DatabaseRAGBridge:
    def __init__(self, db_type: str, connection_string: str):
        self.db_type = db_type.lower()
        self.connection_string = connection_string
        
        if self.db_type == "supabase":
            self._init_supabase()
        elif self.db_type == "neon":
            self._init_neon()
        elif self.db_type == "sqlite":
            self._init_sqlite()
        else:
            raise ValueError(f"Unsupported DB type: {self.db_type}")

    def _init_supabase(self):
        # Uses PostgREST / supabase-py
        from supabase import create_client, Client
        url, key = self.connection_string.split('|')
        self.client: Client = create_client(url, key)

    def _init_neon(self):
        # Uses standard psycopg2 for Neon Postgres pgvector
        import psycopg2
        self.conn = psycopg2.connect(self.connection_string)

    def _init_sqlite(self):
        # Uses local sqlite3 with vector extension
        import sqlite3
        import sqlite_vec # Unsloth extension
        self.conn = sqlite3.connect(self.connection_string)
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)

    def store_document(self, text: str, embedding: List[float], metadata: dict) -> bool:
        """Route document storage to the appropriate DB engine."""
        if self.db_type == "supabase":
            data = {"content": text, "embedding": embedding, "metadata": metadata}
            self.client.table("unsloth_documents").insert(data).execute()
            return True
        elif self.db_type == "neon":
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO unsloth_documents (content, embedding, metadata) VALUES (%s, %s, %s)",
                    (text, str(embedding), json.dumps(metadata))
                )
            self.conn.commit()
            return True
        elif self.db_type == "sqlite":
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO unsloth_documents (content, embedding, metadata) VALUES (?, ?, ?)",
                (text, json.dumps(embedding), json.dumps(metadata))
            )
            self.conn.commit()
            return True
        return False

    def search_documents(self, query_embedding: List[float], limit: int = 5) -> List[dict]:
        """Perform vector similarity search across the selected database."""
        results = []
        if self.db_type == "supabase":
            res = self.client.rpc('match_documents', {'query_embedding': query_embedding, 'match_threshold': 0.7, 'match_count': limit}).execute()
            results = res.data
        elif self.db_type == "neon":
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT content, metadata FROM unsloth_documents ORDER BY embedding <-> %s LIMIT %s",
                    (str(query_embedding), limit)
                )
                for row in cur.fetchall():
                    results.append({"content": row[0], "metadata": row[1]})
        elif self.db_type == "sqlite":
            cur = self.conn.cursor()
            cur.execute(
                "SELECT content, metadata FROM unsloth_documents WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
                (json.dumps(query_embedding), limit)
            )
            for row in cur.fetchall():
                results.append({"content": row[0], "metadata": json.loads(row[1])})
        return results

