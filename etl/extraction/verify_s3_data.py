import io
import boto3
import pandas as pd

REGION = "ap-southeast-2"
BUCKET = "paylens-data-lake"

TABLES = [
    "merchants",
    "customers",
    "payment_methods",
    "banks",
    "failure_codes",
    "payment_intents",
    "payment_transactions",
    "payment_attempts",
    "refunds",
    "settlements",
    "settlement_transactions",
]

s3 = boto3.client("s3", region_name=REGION)


def verify_table(table):
    key = f"raw/{table}/{table}.parquet"
    buffer = io.BytesIO()
    s3.download_fileobj(BUCKET, key, buffer)
    buffer.seek(0)

    df = pd.read_parquet(buffer, engine="pyarrow")
    print(f"\n{'=' * 60}")
    print(f"TABLE: {table}")
    print(f"  Rows:    {len(df):,}")
    print(f"  Columns: {len(df.columns)}")
    print(f"  Schema:  {list(df.columns)}")
    print(f"  Sample:")
    print(df.head(2).to_string(max_colwidth=20))


def main():
    print("Verifying Parquet files in S3 raw zone...")
    for table in TABLES:
        try:
            verify_table(table)
        except Exception as e:
            print(f"\nERROR reading {table}: {e}")
    print(f"\n{'=' * 60}")
    print("Verification complete.")


if __name__ == "__main__":
    main()