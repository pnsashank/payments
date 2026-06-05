import os
import io
import boto3
import psycopg2
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

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


def extract_table(conn, table):
    df = pd.read_sql(f"SELECT * FROM public.{table}", conn)

    buffer = io.BytesIO()
    df.to_parquet(buffer, engine="pyarrow", compression="snappy", index=False)
    buffer.seek(0)

    key = f"raw/{table}/{table}.parquet"
    s3.upload_fileobj(buffer, BUCKET, key)

    print(f"{table}: {len(df):,} rows -> s3://{BUCKET}/{key}")


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        print("Extracting tables from RDS to S3 raw zone...")
        for table in TABLES:
            extract_table(conn, table)
        print("Extraction complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()