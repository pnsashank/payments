import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext 
from awsglue.job import Job 
from pyspark.sql import functions as F 
from pyspark.sql.types import DateType

args = getResolvedOptions(sys.argv, ["JOB_NAME", "S3_BUCKET", "RAW_DB", "CURATED_DB"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

S3_RAW_BASE = f"s3://{args['S3_BUCKET']}/raw"
S3_CURATED_BASE = f"s3://{args['S3_BUCKET']}/curated"
RAW_DB = args["RAW_DB"]
CURATED_DB = args["CURATED_DB"]

# Read Raw Tables
print("Reading raw tables from S3...")

merchants = spark.read.parquet(f"{S3_RAW_BASE}/merchants/")
customers = spark.read.parquet(f"{S3_RAW_BASE}/customers/")
payment_methods = spark.read.parquet(f"{S3_RAW_BASE}/payment_methods/")
banks = spark.read.parquet(f"{S3_RAW_BASE}/banks/")
failure_codes = spark.read.parquet(f"{S3_RAW_BASE}/failure_codes/")
payment_intents  = spark.read.parquet(f"{S3_RAW_BASE}/payment_intents/")
payment_transactions = spark.read.parquet(f"{S3_RAW_BASE}/payment_transactions/")
payment_attempts = spark.read.parquet(f"{S3_RAW_BASE}/payment_attempts/")
refunds = spark.read.parquet(f"{S3_RAW_BASE}/refunds/")
settlements = spark.read.parquet(f"{S3_RAW_BASE}/settlements/")
settlement_transactions = spark.read.parquet(f"{S3_RAW_BASE}/settlement_transactions/")


# Dimension Tables 

print("Building dimension tables...")

# dim_merchant
dim_merchant = merchants.select(
    F.col("merchant_id"),
    F.col("merchant_name"),
    F.col("merchant_category"),
    F.col("merchant_city"),
    F.col("merchant_state"),
    F.col("merchant_country"),
    F.col("risk_tier"),
    F.col("onboarding_date"),
    F.col("is_active")
)
 
# dim_customer
dim_customer = customers.select(
    F.col("customer_id"),
    F.col("customer_city"),
    F.col("customer_state"),
    F.col("customer_country"),
    F.col("customer_segment")
)
 
# dim_payment_method
dim_payment_method = payment_methods.select(
    F.col("payment_method_id"),
    F.col("method_name"),
    F.col("method_group")
)
 
# dim_bank
dim_bank = banks.select(
    F.col("bank_id"),
    F.col("bank_name"),
    F.col("bank_type"),
    F.col("country").alias("bank_country")
)
 
# dim_failure_code
dim_failure_code = failure_codes.select(
    F.col("failure_code"),
    F.col("failure_category"),
    F.col("failure_description"),
    F.col("is_retryable")
)
 
# dim_date — generated from the data range
print("Generating dim_date...")
date_range = spark.sql("""
    SELECT explode(sequence(
        to_date('2024-06-01'),
        to_date('2025-05-31'),
        interval 1 day
    )) as full_date
""")
 
dim_date = date_range.select(
    F.date_format("full_date", "yyyyMMdd").cast("int").alias("date_key"),
    F.col("full_date"),
    F.year("full_date").alias("year"),
    F.quarter("full_date").alias("quarter"),
    F.month("full_date").alias("month"),
    F.date_format("full_date", "MMMM").alias("month_name"),
    F.weekofyear("full_date").alias("week_of_year"),
    F.dayofweek("full_date").alias("day_of_week"),
    F.date_format("full_date", "EEEE").alias("day_name"),
    F.when(F.dayofweek("full_date").isin(1, 7), True).otherwise(False).alias("is_weekend")
)

# Fact Tables 
print("Building fact tables...")
# fact_transactions — grain: one row per payment transaction
fact_transactions = payment_transactions.join(
    payment_intents.select("payment_intent_id", "intent_status"),
    on="payment_intent_id",
    how="left"
).select(
    F.col("transaction_id"),
    F.col("payment_intent_id"),
    F.col("merchant_id"),
    F.col("customer_id"),
    F.col("payment_method_id"),
    F.col("bank_id"),
    F.col("amount"),
    F.col("currency"),
    F.col("transaction_status"),
    F.col("intent_status"),
    F.col("transaction_timestamp"),
    F.col("completed_at"),
    F.when(
        F.col("completed_at").isNotNull() & F.col("transaction_timestamp").isNotNull(),
        F.unix_timestamp("completed_at") - F.unix_timestamp("transaction_timestamp")
    ).alias("processing_time_seconds"),
    F.to_date("transaction_timestamp").alias("transaction_date"),
    F.date_format("transaction_timestamp", "yyyyMMdd").cast("int").alias("date_key")
)
 
# fact_attempts — grain: one row per gateway attempt
fact_attempts = payment_attempts.join(
    payment_transactions.select(
        "transaction_id", "payment_intent_id", "merchant_id",
        "customer_id", "payment_method_id", "bank_id", "currency"
    ),
    on="transaction_id",
    how="left"
).select(
    F.col("attempt_id"),
    F.col("transaction_id"),
    F.col("payment_intent_id"),
    F.col("merchant_id"),
    F.col("customer_id"),
    F.col("payment_method_id"),
    F.col("bank_id"),
    F.col("gateway_provider"),
    F.col("attempt_status"),
    F.col("failure_code"),
    F.col("latency_ms"),
    F.col("currency"),
    F.col("attempted_at"),
    F.to_date("attempted_at").alias("attempt_date"),
    F.date_format("attempted_at", "yyyyMMdd").cast("int").alias("date_key")
)
 
# fact_refunds — grain: one row per refund
fact_refunds = refunds.select(
    F.col("refund_id"),
    F.col("transaction_id"),
    F.col("merchant_id"),
    F.col("refund_amount"),
    F.col("currency"),
    F.col("refund_status"),
    F.col("refund_reason"),
    F.col("refund_timestamp"),
    F.col("processed_at"),
    F.when(
        F.col("processed_at").isNotNull() & F.col("refund_timestamp").isNotNull(),
        F.unix_timestamp("processed_at") - F.unix_timestamp("refund_timestamp")
    ).alias("refund_processing_time_seconds"),
    F.to_date("refund_timestamp").alias("refund_date"),
    F.date_format("refund_timestamp", "yyyyMMdd").cast("int").alias("date_key")
)
 
# fact_settlements — grain: one row per settlement
fact_settlements = settlements.select(
    F.col("settlement_id"),
    F.col("merchant_id"),
    F.col("settlement_period_start"),
    F.col("settlement_period_end"),
    F.col("settlement_date"),
    F.col("gross_payment_amount"),
    F.col("refund_deductions"),
    F.col("chargeback_deductions"),
    F.col("platform_fee"),
    F.col("tax_amount"),
    F.col("net_settlement_amount"),
    F.col("settlement_status"),
    F.datediff("settlement_date", "settlement_period_end").alias("settlement_delay_days"),
    F.date_format("settlement_date", "yyyyMMdd").cast("int").alias("date_key")
)

# Write Curated Tables and Register in Glue Catalog
def write_curated_table(df, table_name, partition_cols=None):
    path = f"{S3_CURATED_BASE}/{table_name}/"
    print(f"Writing {table_name} ({df.count():,} rows) to {path}")
 
    writer = df.write.mode("overwrite").format("parquet").option("compression", "snappy")
    if partition_cols:
        writer = writer.partitionBy(*partition_cols)
    writer.save(path)

    spark.sql(f"DROP TABLE IF EXISTS {CURATED_DB}.{table_name}")
    spark.sql(f"""
        CREATE EXTERNAL TABLE {CURATED_DB}.{table_name}
        USING PARQUET
        LOCATION '{path}'
    """)
    print(f"{table_name} registered in {CURATED_DB}")

# Dimensions
write_curated_table(dim_merchant, "dim_merchant")
write_curated_table(dim_customer, "dim_customer")
write_curated_table(dim_payment_method, "dim_payment_method")
write_curated_table(dim_bank, "dim_bank")
write_curated_table(dim_failure_code, "dim_failure_code")
write_curated_table(dim_date, "dim_date")
 
# Facts
write_curated_table(fact_transactions, "fact_transactions", partition_cols=["currency"])
write_curated_table(fact_attempts, "fact_attempts", partition_cols=["currency"])
write_curated_table(fact_refunds, "fact_refunds", partition_cols=["currency"])
write_curated_table(fact_settlements, "fact_settlements")
 
print("Transform complete. All curated tables written and registered.")
job.commit()