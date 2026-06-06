# PayLens Example SQL Queries

These are verified SQL queries for common analytical questions. All queries run on the `paylens_curated` database using Athena (Presto/Trino SQL dialect).

---

## Question: What is the overall payment success rate?

```sql
SELECT
    ROUND(
        CAST(SUM(CASE WHEN transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as success_rate_pct
FROM paylens_curated.fact_transactions
```

---

## Question: What is the success rate for each payment method?

```sql
SELECT
    pm.method_name,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
    ROUND(
        CAST(SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as success_rate_pct
FROM paylens_curated.fact_transactions ft
JOIN paylens_curated.dim_payment_method pm ON ft.payment_method_id = pm.payment_method_id
GROUP BY pm.method_name
ORDER BY success_rate_pct DESC
```

---

## Question: What is the monthly GMV trend for USD transactions?

```sql
SELECT
    d.year,
    d.month_name,
    ROUND(SUM(ft.amount), 2) as gmv_usd
FROM paylens_curated.fact_transactions ft
JOIN paylens_curated.dim_date d ON ft.date_key = d.date_key
WHERE ft.transaction_status = 'SUCCESS'
AND ft.currency = 'USD'
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month
```

---

## Question: Which payment gateways have the highest latency?

```sql
SELECT
    gateway_provider,
    COUNT(*) as total_attempts,
    ROUND(AVG(latency_ms), 0) as avg_latency_ms,
    ROUND(APPROX_PERCENTILE(latency_ms, 0.50), 0) as p50_ms,
    ROUND(APPROX_PERCENTILE(latency_ms, 0.95), 0) as p95_ms,
    ROUND(APPROX_PERCENTILE(latency_ms, 0.99), 0) as p99_ms
FROM paylens_curated.fact_attempts
GROUP BY gateway_provider
ORDER BY p95_ms DESC
```

---

## Question: What are the top failure reasons for payment failures?

```sql
SELECT
    fc.failure_code,
    fc.failure_category,
    fc.failure_description,
    COUNT(*) as failure_count,
    ROUND(
        CAST(COUNT(*) AS DOUBLE)
        / SUM(COUNT(*)) OVER () * 100, 2
    ) as pct_of_total
FROM paylens_curated.fact_attempts fa
JOIN paylens_curated.dim_failure_code fc ON fa.failure_code = fc.failure_code
WHERE fa.attempt_status IN ('FAILED', 'TIMEOUT')
GROUP BY fc.failure_code, fc.failure_category, fc.failure_description
ORDER BY failure_count DESC
LIMIT 10
```

---

## Question: Which merchants have the worst success rate?

```sql
SELECT
    m.merchant_name,
    m.merchant_category,
    m.merchant_country,
    m.risk_tier,
    COUNT(*) as total_transactions,
    ROUND(
        CAST(SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as success_rate_pct
FROM paylens_curated.fact_transactions ft
JOIN paylens_curated.dim_merchant m ON ft.merchant_id = m.merchant_id
GROUP BY m.merchant_name, m.merchant_category, m.merchant_country, m.risk_tier
ORDER BY success_rate_pct ASC
LIMIT 10
```

---

## Question: What is the refund rate by merchant category?

```sql
SELECT
    m.merchant_category,
    successful.total_successful,
    COALESCE(refunded.total_refunds, 0) as total_refunds,
    ROUND(
        CAST(COALESCE(refunded.total_refunds, 0) AS DOUBLE)
        / successful.total_successful * 100, 2
    ) as refund_rate_pct
FROM (
    SELECT
        m.merchant_category,
        COUNT(*) as total_successful
    FROM paylens_curated.fact_transactions ft
    JOIN paylens_curated.dim_merchant m ON ft.merchant_id = m.merchant_id
    WHERE ft.transaction_status = 'SUCCESS'
    GROUP BY m.merchant_category
) successful
LEFT JOIN (
    SELECT
        m.merchant_category,
        COUNT(*) as total_refunds
    FROM paylens_curated.fact_refunds fr
    JOIN paylens_curated.dim_merchant m ON fr.merchant_id = m.merchant_id
    GROUP BY m.merchant_category
) refunded ON successful.merchant_category = refunded.merchant_category
ORDER BY refund_rate_pct DESC
```

---

## Question: How does UPI compare to credit cards in India?

```sql
SELECT
    pm.method_name,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
    ROUND(
        CAST(SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as success_rate_pct,
    ROUND(AVG(CASE WHEN ft.transaction_status = 'SUCCESS' THEN ft.amount END), 2) as avg_successful_amount
FROM paylens_curated.fact_transactions ft
JOIN paylens_curated.dim_merchant m ON ft.merchant_id = m.merchant_id
JOIN paylens_curated.dim_payment_method pm ON ft.payment_method_id = pm.payment_method_id
WHERE m.merchant_country = 'India'
AND pm.method_name IN ('UPI', 'CREDIT_CARD')
GROUP BY pm.method_name
```

---

## Question: What is the average settlement delay by merchant?

```sql
SELECT
    m.merchant_name,
    m.merchant_category,
    COUNT(*) as total_settlements,
    ROUND(AVG(fs.settlement_delay_days), 1) as avg_delay_days,
    MAX(fs.settlement_delay_days) as max_delay_days
FROM paylens_curated.fact_settlements fs
JOIN paylens_curated.dim_merchant m ON fs.merchant_id = m.merchant_id
WHERE fs.settlement_status = 'SETTLED'
GROUP BY m.merchant_name, m.merchant_category
ORDER BY avg_delay_days DESC
LIMIT 10
```

---

## Question: What percentage of customers switch payment methods after a failure?

```sql
WITH intent_methods AS (
    SELECT
        payment_intent_id,
        COUNT(DISTINCT payment_method_id) as distinct_methods,
        COUNT(*) as total_txns
    FROM paylens_curated.fact_transactions
    GROUP BY payment_intent_id
    HAVING COUNT(*) > 1
)
SELECT
    COUNT(*) as intents_with_retries,
    SUM(CASE WHEN distinct_methods > 1 THEN 1 ELSE 0 END) as switched_methods,
    ROUND(
        CAST(SUM(CASE WHEN distinct_methods > 1 THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as method_switch_rate_pct
FROM intent_methods
```

---

## Question: What is the success rate on weekends vs weekdays?

```sql
SELECT
    CASE WHEN d.is_weekend THEN 'Weekend' ELSE 'Weekday' END as day_type,
    COUNT(*) as total_transactions,
    ROUND(
        CAST(SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as success_rate_pct
FROM paylens_curated.fact_transactions ft
JOIN paylens_curated.dim_date d ON ft.date_key = d.date_key
GROUP BY CASE WHEN d.is_weekend THEN 'Weekend' ELSE 'Weekday' END
```

---

## Question: Which banks have the highest failure rate?

```sql
SELECT
    b.bank_name,
    b.bank_country,
    COUNT(*) as total_attempts,
    SUM(CASE WHEN fa.attempt_status IN ('FAILED', 'TIMEOUT') THEN 1 ELSE 0 END) as failed,
    ROUND(
        CAST(SUM(CASE WHEN fa.attempt_status IN ('FAILED', 'TIMEOUT') THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as failure_rate_pct
FROM paylens_curated.fact_attempts fa
JOIN paylens_curated.dim_bank b ON fa.bank_id = b.bank_id
GROUP BY b.bank_name, b.bank_country
ORDER BY failure_rate_pct DESC
```

---

## Question: What is the monthly platform revenue trend?

```sql
SELECT
    d.year,
    d.month_name,
    ROUND(SUM(fs.platform_fee), 2) as platform_revenue,
    ROUND(SUM(fs.net_settlement_amount), 2) as merchant_payouts,
    ROUND(SUM(fs.gross_payment_amount), 2) as gross_volume
FROM paylens_curated.fact_settlements fs
JOIN paylens_curated.dim_date d ON fs.date_key = d.date_key
WHERE fs.settlement_status = 'SETTLED'
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month
```

---

## Question: What is the transaction retry rate?

```sql
SELECT
    ROUND(
        CAST(SUM(CASE WHEN txn_count > 1 THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as retry_rate_pct,
    ROUND(AVG(txn_count), 2) as avg_transactions_per_intent
FROM (
    SELECT payment_intent_id, COUNT(*) as txn_count
    FROM paylens_curated.fact_transactions
    GROUP BY payment_intent_id
) intent_txns
```

---

## Question: What is the success rate by country?

```sql
SELECT
    m.merchant_country,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
    ROUND(
        CAST(SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as success_rate_pct
FROM paylens_curated.fact_transactions ft
JOIN paylens_curated.dim_merchant m ON ft.merchant_id = m.merchant_id
GROUP BY m.merchant_country
ORDER BY success_rate_pct DESC
```

---

## Question: How much fraud-related refunds happened per country?

```sql
SELECT
    m.merchant_country,
    COUNT(*) as fraud_refunds,
    ROUND(SUM(fr.refund_amount), 2) as fraud_refund_amount
FROM paylens_curated.fact_refunds fr
JOIN paylens_curated.dim_merchant m ON fr.merchant_id = m.merchant_id
WHERE fr.refund_reason = 'FRAUD'
GROUP BY m.merchant_country
ORDER BY fraud_refund_amount DESC
```
---

## Question: How many payment intents were created?

```sql
SELECT COUNT(DISTINCT payment_intent_id) as total_intents
FROM paylens_curated.fact_transactions
```

---

## Question: How many total gateway attempts happened?

```sql
SELECT COUNT(*) as total_attempts
FROM paylens_curated.fact_attempts
```