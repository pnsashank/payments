import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    print("Enabling pgvector extension...")
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    print("Creating bedrock_integration schema...")
    cur.execute("CREATE SCHEMA IF NOT EXISTS bedrock_integration;")

    print("Creating vector table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bedrock_integration.bedrock_kb (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            embedding vector(1024),
            chunks TEXT,
            metadata JSONB
        );
    """)

    print("Creating HNSW index...")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS bedrock_kb_embedding_idx
        ON bedrock_integration.bedrock_kb
        USING hnsw (embedding vector_cosine_ops);
    """)

    print("pgvector setup complete.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()