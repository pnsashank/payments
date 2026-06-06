import os
import json
import boto3
import psycopg2
from dotenv import load_dotenv

load_dotenv()

REGION = "ap-southeast-2"

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)


def embed_query(text):
    """Embed a user question using Cohere Embed v3.
    Uses input_type='search_query' which is optimized for queries 
    (vs 'search_document' used during indexing)."""
    response = bedrock_runtime.invoke_model(
        modelId="cohere.embed-english-v3",
        body=json.dumps({
            "texts": [text],
            "input_type": "search_query",
            "truncate": "NONE"
        })
    )
    result = json.loads(response["body"].read())
    return result["embeddings"][0]


def search_pgvector(query_embedding, top_k=5):
    """Search pgvector for the most similar chunks using cosine distance."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    cur.execute("""
        SELECT
            chunks,
            metadata,
            1 - (embedding <=> %s::vector) as similarity
        FROM bedrock_integration.bedrock_kb
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (vector_str, vector_str, top_k))

    results = []
    for row in cur.fetchall():
        results.append({
            "text": row[0],
            "metadata": row[1] if isinstance(row[1], dict) else json.loads(row[1]),
            "similarity": round(float(row[2]), 4)
        })

    cur.close()
    conn.close()
    return results


def retrieve(question, top_k=5):
    """Full retrieval pipeline: embed question -> search pgvector -> return chunks."""
    embedding = embed_query(question)
    results = search_pgvector(embedding, top_k=top_k)
    return results


if __name__ == "__main__":
    test_questions = [
        "What is the payment success rate?",
        "Which gateways have the highest latency?",
        "How do I join fact_transactions to dim_merchant?",
        "What is the refund rate by merchant?",
        "How does UPI compare to credit cards in India?"
    ]

    for question in test_questions:
        print(f"\nQuestion: {question}")
        results = retrieve(question, top_k=3)
        for i, result in enumerate(results):
            source = result["metadata"].get("source", "unknown")
            heading = result["metadata"].get("heading_path", "unknown")
            similarity = result["similarity"]
            preview = result["text"][:100].replace("\n", " ")
            print(f" {i+1}. [{similarity}] {heading}")
            print(f" {preview}...")