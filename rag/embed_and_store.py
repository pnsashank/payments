import os
import re
import json
import boto3
import psycopg2
from dotenv import load_dotenv

load_dotenv()

REGION = "ap-southeast-2"
BUCKET = "paylens-data-lake"

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

s3 = boto3.client("s3", region_name=REGION)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

SEMANTIC_FILES = [
    ("semantic/table_dictionary.md",   "table_dictionary"),
    ("semantic/metric_definitions.md", "metric_definition"),
    ("semantic/join_rules.md",         "join_rules"),
    ("semantic/business_rules.md",     "business_rules"),
    ("semantic/example_queries.md",    "example_query"),
]

MIN_CHUNK_SIZE = 100
MAX_CHUNK_SIZE = 2000


# Step 1: Download Documents
def download_doc(s3_key):
    response = s3.get_object(Bucket=BUCKET, Key=s3_key)
    return response["Body"].read().decode("utf-8")

# Step 2: Context-Enriched Document-Aware Chunking
def extract_heading_level(line):
    match = re.match(r'^(#{1,4})\s+(.+)', line)
    if match:
        level = len(match.group(1))
        text = match.group(2).strip()
        return level, text
    return None, None


def chunk_document(text, source_file, doc_type):
    lines = text.split("\n")
    chunks = []

    heading_stack = {}
    current_chunk_lines = []
    current_heading_path = ""
    current_heading = ""

    def flush_chunk():
        nonlocal current_chunk_lines, current_heading_path, current_heading
        if not current_chunk_lines:
            return

        chunk_text = "\n".join(current_chunk_lines).strip()

        if len(chunk_text) < MIN_CHUNK_SIZE:
            return

        if current_heading_path:
            enriched_text = f"{current_heading_path}\n\n{chunk_text}"
        else:
            enriched_text = chunk_text

        if len(enriched_text) > MAX_CHUNK_SIZE:
            sub_chunks = split_large_chunk(enriched_text, current_heading_path)
            chunks.extend([
                {
                    "text": sub,
                    "metadata": {
                        "source": source_file,
                        "heading_path": current_heading_path,
                        "heading": current_heading,
                        "document_type": doc_type
                    }
                }
                for sub in sub_chunks
            ])
        else:
            chunks.append({
                "text": enriched_text,
                "metadata": {
                    "source": source_file,
                    "heading_path": current_heading_path,
                    "heading": current_heading,
                    "document_type": doc_type
                }
            })

        current_chunk_lines = []

    def split_large_chunk(text, heading_path):
        paragraphs = re.split(r'\n\n+', text)
        sub_chunks = []
        current_sub = []
        current_len = 0

        for para in paragraphs:
            if current_len + len(para) > MAX_CHUNK_SIZE and current_sub:
                sub_chunks.append("\n\n".join(current_sub))
                current_sub = [f"{heading_path} (continued)"] if heading_path else []
                current_len = len(current_sub[0]) if current_sub else 0

            current_sub.append(para)
            current_len += len(para)

        if current_sub:
            sub_chunks.append("\n\n".join(current_sub))

        return sub_chunks

    for line in lines:
        if line.strip() == "---":
            continue

        level, heading_text = extract_heading_level(line)

        if level is not None:
            flush_chunk()

            heading_stack[level] = heading_text

            keys_to_remove = [k for k in heading_stack if k > level]
            for k in keys_to_remove:
                del heading_stack[k]

            path_parts = [heading_stack[k] for k in sorted(heading_stack.keys())]
            current_heading_path = " > ".join(path_parts)
            current_heading = heading_text
            current_chunk_lines = []
        else:
            current_chunk_lines.append(line)

    flush_chunk()
    return chunks

# Step 3: Embed Chunks Using Cohere via Bedrock
def embed_texts(texts, input_type="search_document"):
    response = bedrock_runtime.invoke_model(
        modelId="cohere.embed-english-v3",
        body=json.dumps({
            "texts": texts,
            "input_type": input_type,
            "truncate": "NONE"
        })
    )
    result = json.loads(response["body"].read())
    return result["embeddings"]


# Step 4: Store in pgvector
def store_embeddings(chunks, embeddings):
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("DELETE FROM bedrock_integration.bedrock_kb;")
    print("  Cleared existing embeddings.")

    for chunk, embedding in zip(chunks, embeddings):
        vector_str = "[" + ",".join(str(x) for x in embedding) + "]"
        cur.execute("""
            INSERT INTO bedrock_integration.bedrock_kb (embedding, chunks, metadata)
            VALUES (%s::vector, %s, %s)
        """, (
            vector_str,
            chunk["text"],
            json.dumps(chunk["metadata"])
        ))

    cur.close()
    conn.close()


# Main
def main():

    print("EMBEDDING SEMANTIC DOCUMENTS INTO PGVECTOR")
    all_chunks = []

    print("\nStep 1: Downloading and chunking documents...")
    for s3_key, doc_type in SEMANTIC_FILES:
        text = download_doc(s3_key)
        chunks = chunk_document(text, s3_key, doc_type)
        all_chunks.extend(chunks)
        print(f"  {s3_key}: {len(chunks)} chunks")

    print(f"\nTotal chunks: {len(all_chunks)}")

    print("\nChunk preview:")
    for i, chunk in enumerate(all_chunks[:5]):
        heading = chunk["metadata"]["heading_path"]
        doc_type = chunk["metadata"]["document_type"]
        size = len(chunk["text"])
        print(f"  {i+1}. [{doc_type}] {heading} ({size} chars)")

    print("\nStep 2: Embedding chunks with Cohere Embed v3...")
    batch_size = 20
    all_embeddings = []

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        texts = [chunk["text"] for chunk in batch]
        embeddings = embed_texts(texts)
        all_embeddings.extend(embeddings)
        print(f"  Embedded batch {i // batch_size + 1}/{(len(all_chunks) + batch_size - 1) // batch_size}")

    print(f"\nTotal embeddings: {len(all_embeddings)}")
    print(f"Embedding dimensions: {len(all_embeddings[0])}")

    print("\nStep 3: Storing in pgvector...")
    store_embeddings(all_chunks, all_embeddings)
    print(f"  Stored {len(all_chunks)} chunks in bedrock_integration.bedrock_kb")

    print("EMBEDDING COMPLETE")


if __name__ == "__main__":
    main()