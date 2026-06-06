# PayLens Metric Definitions

## Metric Framework Overview

PayLens metrics follow a four-level hierarchy: Input Metrics feed into Primary Metrics, which roll up to the North Star Metric, with Guardrail Metrics ensuring healthy growth.

---

## Input Metrics

### Total Payment Volume (TPV)

The total number of payment transactions processed across the platform.

- **Table:** fact_transactions
- **Formula:** COUNT(*)
- **Filters:** None — includes all statuses
- **SQL:**
```sql
SELECT COUNT(*) as total_payment_volume
FROM paylens_curated.fact_transactions
```

### Total Payment Intents

The total number of unique payment intents created by customers. Use this metric to answer questions like "how many payment intents were created", "how many customers tried to pay", or "total number of payment attempts initiated". A payment intent is created each time a customer initiates a checkout, regardless of whether the payment succeeds.

- **Table:** fact_transactions
- **Formula:** COUNT(DISTINCT payment_intent_id)
- **SQL:**
```sql
SELECT COUNT(DISTINCT payment_intent_id) as total_intents
FROM paylens_curated.fact_transactions
```

### Total Gateway Attempts

The total number of gateway-level attempts across all transactions. Use this metric to answer questions like "how many gateway attempts happened", "total attempts across all gateways", or "how many times did gateways process a request". Each transaction can trigger multiple gateway attempts when the system retries through different providers.


- **Table:** fact_attempts
- **Formula:** COUNT(*)
- **SQL:**
```sql
SELECT COUNT(*) as total_attempts
FROM paylens_curated.fact_attempts
```

---

## Primary Metrics

### Payment Success Rate

The percentage of payment transactions that completed successfully. This is the most commonly tracked metric in payments analytics.

- **Table:** fact_transactions
- **Formula:** COUNT(transactions with SUCCESS) / COUNT(all transactions) * 100
- **SQL:**
```sql
SELECT
    ROUND(
        CAST(SUM(CASE WHEN transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as success_rate_pct
FROM paylens_curated.fact_transactions
```
- **Important:** Always use CAST to DOUBLE to avoid integer division returning 0.

### Payment Completion Rate

The percentage of payment intents that eventually resulted in a successful transaction. Measures end-to-end customer conversion.

- **Table:** fact_transactions
- **Formula:** COUNT(DISTINCT intents with at least one SUCCESS transaction) / COUNT(DISTINCT all intents) * 100
- **SQL:**
```sql
SELECT
    ROUND(
        CAST(COUNT(DISTINCT CASE WHEN transaction_status = 'SUCCESS' THEN payment_intent_id END) AS DOUBLE)
        / COUNT(DISTINCT payment_intent_id) * 100, 2
    ) as completion_rate_pct
FROM paylens_curated.fact_transactions
```
- **Note:** This differs from success rate. An intent can have 3 failed transactions and 1 successful — success rate counts 1/4 = 25%, but completion rate counts the intent as completed = 100% for that intent.

### Gross Merchandise Value (GMV)

Total monetary value of all successful transactions. Always filter by currency since amounts cannot be summed across currencies.

- **Table:** fact_transactions
- **Formula:** SUM(amount) WHERE transaction_status = 'SUCCESS'
- **SQL:**
```sql
SELECT
    currency,
    ROUND(SUM(amount), 2) as gmv
FROM paylens_curated.fact_transactions
WHERE transaction_status = 'SUCCESS'
GROUP BY currency
```
- **Critical:** Always include currency in GROUP BY or filter by a single currency. Never sum amounts across different currencies.

### Average Transaction Value (ATV)

Average amount per successful transaction.

- **Table:** fact_transactions
- **Formula:** SUM(amount) / COUNT(*) WHERE transaction_status = 'SUCCESS'
- **SQL:**
```sql
SELECT
    currency,
    ROUND(AVG(amount), 2) as avg_transaction_value
FROM paylens_curated.fact_transactions
WHERE transaction_status = 'SUCCESS'
GROUP BY currency
```

### Platform Revenue

Total platform fees collected from settlements. This is PayLens's revenue.

- **Table:** fact_settlements
- **Formula:** SUM(platform_fee)
- **SQL:**
```sql
SELECT
    ROUND(SUM(platform_fee), 2) as total_platform_revenue
FROM paylens_curated.fact_settlements
WHERE settlement_status = 'SETTLED'
```

### Take Rate

Platform fee as a percentage of gross payment amount.

- **Table:** fact_settlements
- **Formula:** SUM(platform_fee) / SUM(gross_payment_amount) * 100
- **SQL:**
```sql
SELECT
    ROUND(
        CAST(SUM(platform_fee) AS DOUBLE)
        / SUM(gross_payment_amount) * 100, 2
    ) as take_rate_pct
FROM paylens_curated.fact_settlements
WHERE settlement_status = 'SETTLED'
```

---

## North Star Metric

### Net Payment Value (NPV)

The total net amount settled to merchants after all deductions. This is the ultimate measure of platform health — it grows when transaction volume grows, success rates improve, and refunds stay low.

- **Table:** fact_settlements
- **Formula:** SUM(net_settlement_amount)
- **SQL:**
```sql
SELECT
    ROUND(SUM(net_settlement_amount), 2) as net_payment_value
FROM paylens_curated.fact_settlements
WHERE settlement_status = 'SETTLED'
```

---

## Guardrail Metrics

### Transaction Retry Rate

The percentage of payment intents that required more than one transaction. High retry rate means customers are failing on first attempt and having to try again.

- **Table:** fact_transactions
- **Formula:** COUNT(intents with > 1 transaction) / COUNT(all intents) * 100
- **SQL:**
```sql
SELECT
    ROUND(
        CAST(SUM(CASE WHEN txn_count > 1 THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as retry_rate_pct
FROM (
    SELECT payment_intent_id, COUNT(*) as txn_count
    FROM paylens_curated.fact_transactions
    GROUP BY payment_intent_id
) intent_txns
```

### Gateway Retry Rate

The percentage of transactions that required more than one gateway attempt.

- **Table:** fact_attempts
- **Formula:** COUNT(transactions with > 1 attempt) / COUNT(all transactions) * 100
- **SQL:**
```sql
SELECT
    ROUND(
        CAST(SUM(CASE WHEN att_count > 1 THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as gateway_retry_rate_pct
FROM (
    SELECT transaction_id, COUNT(*) as att_count
    FROM paylens_curated.fact_attempts
    GROUP BY transaction_id
) txn_attempts
```

### Refund Rate

The percentage of successful transactions that were subsequently refunded.

- **Table:** fact_transactions, fact_refunds
- **Formula:** COUNT(refunds) / COUNT(successful transactions) * 100
- **SQL:**
```sql
SELECT
    ROUND(
        CAST((SELECT COUNT(*) FROM paylens_curated.fact_refunds) AS DOUBLE)
        / (SELECT COUNT(*) FROM paylens_curated.fact_transactions WHERE transaction_status = 'SUCCESS') * 100, 2
    ) as refund_rate_pct
```

### Fraud Refund Rate

Percentage of refunds that were initiated due to suspected fraud.

- **Table:** fact_refunds
- **Formula:** COUNT(refunds with reason FRAUD) / COUNT(all refunds) * 100
- **SQL:**
```sql
SELECT
    ROUND(
        CAST(SUM(CASE WHEN refund_reason = 'FRAUD' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as fraud_refund_rate_pct
FROM paylens_curated.fact_refunds
```

### Settlement Delay

Average number of days between the end of a settlement period and the actual settlement date.

- **Table:** fact_settlements
- **Formula:** AVG(settlement_delay_days)
- **SQL:**
```sql
SELECT
    ROUND(AVG(settlement_delay_days), 1) as avg_settlement_delay_days
FROM paylens_curated.fact_settlements
WHERE settlement_status = 'SETTLED'
```

### Settlement SLA Compliance

Percentage of settlements completed within 3 days of period end.

- **Table:** fact_settlements
- **Formula:** COUNT(settlements with delay <= 3) / COUNT(all settled) * 100
- **SQL:**
```sql
SELECT
    ROUND(
        CAST(SUM(CASE WHEN settlement_delay_days <= 3 THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as sla_compliance_pct
FROM paylens_curated.fact_settlements
WHERE settlement_status = 'SETTLED'
```

---

## Gateway & Infrastructure Metrics

### Gateway Success Rate

Success rate broken down by payment gateway provider.

- **Table:** fact_attempts
- **SQL:**
```sql
SELECT
    gateway_provider,
    COUNT(*) as total_attempts,
    SUM(CASE WHEN attempt_status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
    ROUND(
        CAST(SUM(CASE WHEN attempt_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as success_rate_pct
FROM paylens_curated.fact_attempts
GROUP BY gateway_provider
ORDER BY success_rate_pct DESC
```

### Gateway Latency Percentiles

P50, P95, and P99 latency for each gateway provider. P95 is the standard monitoring metric.

- **Table:** fact_attempts
- **SQL:**
```sql
SELECT
    gateway_provider,
    ROUND(APPROX_PERCENTILE(latency_ms, 0.50), 0) as p50_latency_ms,
    ROUND(APPROX_PERCENTILE(latency_ms, 0.95), 0) as p95_latency_ms,
    ROUND(APPROX_PERCENTILE(latency_ms, 0.99), 0) as p99_latency_ms
FROM paylens_curated.fact_attempts
GROUP BY gateway_provider
ORDER BY p95_latency_ms
```

### Gateway Timeout Rate

Percentage of attempts that timed out per gateway.

- **Table:** fact_attempts
- **SQL:**
```sql
SELECT
    gateway_provider,
    ROUND(
        CAST(SUM(CASE WHEN attempt_status = 'TIMEOUT' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as timeout_rate_pct
FROM paylens_curated.fact_attempts
GROUP BY gateway_provider
ORDER BY timeout_rate_pct DESC
```

### First Attempt Success Rate

Percentage of transactions that succeeded on the first gateway attempt without needing retries.

- **Table:** fact_attempts
- **SQL:**
```sql
WITH first_attempts AS (
    SELECT
        transaction_id,
        attempt_status,
        ROW_NUMBER() OVER (PARTITION BY transaction_id ORDER BY attempted_at) as attempt_num
    FROM paylens_curated.fact_attempts
)
SELECT
    ROUND(
        CAST(SUM(CASE WHEN attempt_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as first_attempt_success_rate_pct
FROM first_attempts
WHERE attempt_num = 1
```

---

## Customer Behavior Metrics

### Payment Method Preference by Region

Distribution of payment methods used by merchant country.

- **Table:** fact_transactions, dim_merchant, dim_payment_method
- **SQL:**
```sql
SELECT
    m.merchant_country,
    pm.method_name,
    COUNT(*) as transaction_count,
    ROUND(
        CAST(COUNT(*) AS DOUBLE)
        / SUM(COUNT(*)) OVER (PARTITION BY m.merchant_country) * 100, 2
    ) as pct_of_country
FROM paylens_curated.fact_transactions ft
JOIN paylens_curated.dim_merchant m ON ft.merchant_id = m.merchant_id
JOIN paylens_curated.dim_payment_method pm ON ft.payment_method_id = pm.payment_method_id
GROUP BY m.merchant_country, pm.method_name
ORDER BY m.merchant_country, pct_of_country DESC
```

### Method Switch Rate

When a payment intent has multiple transactions, how often does the customer switch to a different payment method.

- **Table:** fact_transactions
- **SQL:**
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
    ROUND(
        CAST(SUM(CASE WHEN distinct_methods > 1 THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as method_switch_rate_pct
FROM intent_methods
```

### Drop-off Rate

Percentage of payment intents that never resulted in a successful transaction.

- **Table:** fact_transactions
- **SQL:**
```sql
SELECT
    ROUND(
        CAST(SUM(CASE WHEN intent_status = 'FAILED' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as dropoff_rate_pct
FROM (
    SELECT DISTINCT payment_intent_id, intent_status
    FROM paylens_curated.fact_transactions
) intents
```

---

## Merchant Health Metrics

### Merchant Success Rate

Payment success rate per merchant. Used to identify struggling merchants.

- **Table:** fact_transactions, dim_merchant
- **SQL:**
```sql
SELECT
    m.merchant_name,
    m.merchant_category,
    COUNT(*) as total_transactions,
    ROUND(
        CAST(SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as success_rate_pct
FROM paylens_curated.fact_transactions ft
JOIN paylens_curated.dim_merchant m ON ft.merchant_id = m.merchant_id
GROUP BY m.merchant_name, m.merchant_category
ORDER BY success_rate_pct ASC
```

### Merchant Refund Rate

Refund rate per merchant. High refund rate indicates potential quality or fraud issues.

- **Table:** fact_transactions, fact_refunds, dim_merchant
- **SQL:**
```sql
SELECT
    m.merchant_name,
    m.merchant_category,
    successful.total_successful,
    COALESCE(refunded.total_refunds, 0) as total_refunds,
    ROUND(
        CAST(COALESCE(refunded.total_refunds, 0) AS DOUBLE)
        / successful.total_successful * 100, 2
    ) as refund_rate_pct
FROM (
    SELECT merchant_id, COUNT(*) as total_successful
    FROM paylens_curated.fact_transactions
    WHERE transaction_status = 'SUCCESS'
    GROUP BY merchant_id
) successful
LEFT JOIN (
    SELECT merchant_id, COUNT(*) as total_refunds
    FROM paylens_curated.fact_refunds
    GROUP BY merchant_id
) refunded ON successful.merchant_id = refunded.merchant_id
JOIN paylens_curated.dim_merchant m ON successful.merchant_id = m.merchant_id
ORDER BY refund_rate_pct DESC
```

### Risk Tier Performance

Success rate comparison across merchant risk tiers.

- **Table:** fact_transactions, dim_merchant
- **SQL:**
```sql
SELECT
    m.risk_tier,
    COUNT(*) as total_transactions,
    ROUND(
        CAST(SUM(CASE WHEN ft.transaction_status = 'SUCCESS' THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as success_rate_pct
FROM paylens_curated.fact_transactions ft
JOIN paylens_curated.dim_merchant m ON ft.merchant_id = m.merchant_id
GROUP BY m.risk_tier
ORDER BY success_rate_pct DESC
```

---

## Failure Analysis Metrics

### Failure Category Distribution

Breakdown of payment failures by category (customer-side, bank-side, etc).

- **Table:** fact_attempts, dim_failure_code
- **SQL:**
```sql
SELECT
    fc.failure_category,
    COUNT(*) as failure_count,
    ROUND(
        CAST(COUNT(*) AS DOUBLE)
        / SUM(COUNT(*)) OVER () * 100, 2
    ) as pct_of_total
FROM paylens_curated.fact_attempts fa
JOIN paylens_curated.dim_failure_code fc ON fa.failure_code = fc.failure_code
WHERE fa.attempt_status IN ('FAILED', 'TIMEOUT')
GROUP BY fc.failure_category
ORDER BY failure_count DESC
```

### Bank Decline Rate

Failure rate per bank. Identifies banks with reliability issues.

- **Table:** fact_attempts, dim_bank
- **SQL:**
```sql
SELECT
    b.bank_name,
    b.bank_country,
    COUNT(*) as total_attempts,
    ROUND(
        CAST(SUM(CASE WHEN fa.attempt_status IN ('FAILED', 'TIMEOUT') THEN 1 ELSE 0 END) AS DOUBLE)
        / COUNT(*) * 100, 2
    ) as decline_rate_pct
FROM paylens_curated.fact_attempts fa
JOIN paylens_curated.dim_bank b ON fa.bank_id = b.bank_id
GROUP BY b.bank_name, b.bank_country
ORDER BY decline_rate_pct DESC
```

### Retryable vs Non-Retryable Failures

Split of failures into those worth retrying vs permanent failures.

- **Table:** fact_attempts, dim_failure_code
- **SQL:**
```sql
SELECT
    fc.is_retryable,
    COUNT(*) as failure_count,
    ROUND(
        CAST(COUNT(*) AS DOUBLE)
        / SUM(COUNT(*)) OVER () * 100, 2
    ) as pct_of_failures
FROM paylens_curated.fact_attempts fa
JOIN paylens_curated.dim_failure_code fc ON fa.failure_code = fc.failure_code
WHERE fa.attempt_status IN ('FAILED', 'TIMEOUT')
GROUP BY fc.is_retryable
```