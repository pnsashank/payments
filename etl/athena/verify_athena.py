import boto3
import time

REGION = "ap-southeast-2"
BUCKET = "paylens-data-lake"
DATABASE = "paylens_curated"
OUTPUT_LOC = f"s3://{BUCKET}/athena-results/"

athena = boto3.client("athena", region_name=REGION)

def run_query(sql):
    response = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": DATABASE},
        ResultConfiguration={"OutputLocation": OUTPUT_LOC}
    )
    query_id = response["QueryExecutionId"]

    while True:
        result = athena.get_query_execution(QueryExecutionId=query_id)
        status = result["QueryExecution"]["Status"]["State"]
        if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(2)

    if status == "FAILED":
        reason = result["QueryExecution"]["Status"]["StateChangeReason"]
        print(f"FAILED: {reason}")
        return None

    results = athena.get_query_results(QueryExecutionId=query_id)
    return results


def print_results(results):
    if not results:
        return
    rows = results["ResultSet"]["Rows"]
    headers = [col["VarCharValue"] for col in rows[0]["Data"]]
    print(f"  {' | '.join(headers)}")
    for row in rows[1:]:
        values = [col.get("VarCharValue", "NULL") for col in row["Data"]]
        print(f"  {' | '.join(values)}")


def main():

    print("VERIFYING CURATED TABLES IN ATHENA")
    # 1. List all tables
    print("\n1. Tables in paylens_curated:")
    results = run_query("SHOW TABLES")
    if results:
        for row in results["ResultSet"]["Rows"]:
            print(f"  - {row['Data'][0]['VarCharValue']}")

    # 2. Row counts for all tables
    print("\n2. Row counts:")
    tables = [
        "dim_merchant", "dim_customer", "dim_payment_method",
        "dim_bank", "dim_failure_code", "dim_date",
        "fact_transactions", "fact_attempts",
        "fact_refunds", "fact_settlements"
    ]
    for table in tables:
        results = run_query(f"SELECT COUNT(*) as row_count FROM {table}")
        if results:
            count = results["ResultSet"]["Rows"][1]["Data"][0]["VarCharValue"]
            print(f"  {table}: {int(count):,} rows")

    # 3. Sample from fact_transactions
    print("\n3. Sample fact_transactions (5 rows):")
    results = run_query("""
        SELECT transaction_id, payment_method_id, amount, currency,
               transaction_status, processing_time_seconds
        FROM fact_transactions LIMIT 5
    """)
    print_results(results)

    # 4. Success rate by payment method
    print("\n4. Success rate by payment method:")
    results = run_query("""
        SELECT
            pm.method_name,
            COUNT(*) as total,
            SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
            ROUND(
                CAST(SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
                / COUNT(*) * 100, 2
            ) as success_rate_pct
        FROM fact_transactions ft
        JOIN dim_payment_method pm ON ft.payment_method_id = pm.payment_method_id
        GROUP BY pm.method_name
        ORDER BY success_rate_pct DESC
    """)
    print_results(results)

    # 5. Average latency by gateway
    print("\n5. Average latency by gateway provider:")
    results = run_query("""
        SELECT
            gateway_provider,
            COUNT(*) as total_attempts,
            ROUND(AVG(latency_ms), 0) as avg_latency_ms,
            ROUND(APPROX_PERCENTILE(latency_ms, 0.95), 0) as p95_latency_ms
        FROM fact_attempts
        GROUP BY gateway_provider
        ORDER BY avg_latency_ms
    """)
    print_results(results)

    # 6. Refund rate by merchant category
    print("\n6. Top 5 merchants by refund count:")
    results = run_query("""
        SELECT
            m.merchant_name,
            m.merchant_category,
            COUNT(*) as refund_count,
            ROUND(SUM(fr.refund_amount), 2) as total_refunded
        FROM fact_refunds fr
        JOIN dim_merchant m ON fr.merchant_id = m.merchant_id
        GROUP BY m.merchant_name, m.merchant_category
        ORDER BY refund_count DESC
        LIMIT 5
    """)
    print_results(results)

    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()