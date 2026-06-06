import boto3
import os

REGION = "ap-southeast-2"
BUCKET = "paylens-data-lake"

s3 = boto3.client("s3", region_name=REGION)

DOCS_DIR = "."
S3_PREFIX = "semantic"

files = [
    "table_dictionary.md",
    "metric_definitions.md",
    "join_rules.md",
    "business_rules.md",
    "example_queries.md",
]

def main():
    for filename in files:
        local_path = os.path.join(DOCS_DIR, filename)
        s3_key = f"{S3_PREFIX}/{filename}"
        s3.upload_file(local_path, BUCKET, s3_key)
        print(f"Uploaded {filename} -> s3://{BUCKET}/{s3_key}")

    print("\nAll semantic documents uploaded successfully.")
    print(f"Location: s3://{BUCKET}/{S3_PREFIX}/")

if __name__ == "__main__":
    main()