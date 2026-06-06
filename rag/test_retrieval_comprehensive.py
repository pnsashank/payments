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


def search_pgvector(query_embedding, top_k=3):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    cur.execute("""
        SELECT chunks, metadata, 1 - (embedding <=> %s::vector) as similarity
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


def test_retrieval(question, expected_topic):
    embedding = embed_query(question)
    results = search_pgvector(embedding, top_k=2)
    top_heading = results[0]["metadata"].get("heading_path", "")
    top_score = results[0]["similarity"]
    match = "PASS" if expected_topic.lower() in top_heading.lower() else "MISS"
    print(f"  [{match}] [{top_score:.4f}] {question}")
    print(f"          -> {top_heading}")
    if match == "MISS":
        print(f"          Expected: {expected_topic}")
    return match == "PASS"


if __name__ == "__main__":
    print("COMPREHENSIVE RETRIEVAL TEST")

    tests = [
        # Input Metrics
        ("What is the total payment volume?", "Total Payment Volume"),
        ("How many payment intents were created?", "Total Payment Intents"),
        ("How many gateway attempts happened?", "Total Gateway Attempts"),

        # Primary Metrics
        ("What is the payment success rate?", "Payment Success Rate"),
        ("What is the payment completion rate?", "Payment Completion Rate"),
        ("What is the GMV?", "Gross Merchandise Value"),
        ("What is the average transaction value?", "Average Transaction Value"),
        ("How much platform revenue was generated?", "Platform Revenue"),
        ("What is the take rate?", "Take Rate"),

        # North Star
        ("What is the net payment value?", "Net Payment Value"),

        # Guardrails
        ("What is the transaction retry rate?", "Retry Rate"),
        ("What is the refund rate?", "Refund Rate"),
        ("What is the fraud refund rate?", "Fraud Refund Rate"),
        ("What is the average settlement delay?", "Settlement Delay"),
        ("What percentage of settlements meet the SLA?", "Settlement SLA"),

        # Gateway Metrics
        ("Which gateway has the best success rate?", "Gateway Success Rate"),
        ("What is the P95 latency by gateway?", "Gateway Latency"),
        ("Which gateways timeout the most?", "Gateway Timeout"),
        ("What is the first attempt success rate?", "First Attempt"),

        # Customer Metrics
        ("What payment methods are popular in each country?", "Payment Method Preference"),
        ("How often do customers switch payment methods?", "Method Switch"),
        ("What is the customer drop-off rate?", "Drop-off"),

        # Merchant Metrics
        ("Which merchants have the worst success rate?", "Merchant Success Rate"),
        ("Which merchants have the highest refund rate?", "Merchant Refund Rate"),
        ("How do high risk merchants perform compared to low risk?", "Risk Tier"),

        # Failure Analysis
        ("What are the main failure categories?", "Failure Category"),
        ("Which banks decline the most?", "Bank Decline"),
        ("What percentage of failures are retryable?", "Retryable"),

        # Join Rules
        ("How do I join transactions to merchants?", "fact_transactions joins"),
        ("How do I connect refunds to the original transaction?", "fact_refunds"),

        # Business Rules
        ("Can I sum amounts across currencies?", "Currency"),
        ("What does transaction status SUCCESS mean?", "Transaction Status"),

        # Example Queries
        ("Show me success rate by country", "success rate by country"),
        ("Monthly revenue trend", "monthly platform revenue"),
    ]

    passed = 0
    total = len(tests)

    for question, expected in tests:
        if test_retrieval(question, expected):
            passed += 1
    print(f"RESULTS: {passed}/{total} passed ({round(passed/total*100)}%)")