# PayLens Business Rules

## Payment Lifecycle Rules

### Intent → Transaction → Attempt Hierarchy

- A payment intent represents a customer's desire to pay a specific amount to a specific merchant.
- Each intent can have multiple transactions. A new transaction is created when the customer retries with a different payment method.
- Each transaction can have multiple attempts. A new attempt is created when the system retries through a different payment gateway.
- Only one transaction per intent can have status SUCCESS. Once an intent succeeds, no more successful transactions are possible.

### Transaction Status Values

- **SUCCESS** — Payment collected successfully. Money has moved.
- **FAILED** — Payment was attempted but did not go through. No money moved.
- **CANCELLED** — Transaction was cancelled before completion. Typically happens after a prior transaction on the same intent already succeeded.
- **INITIATED** — Transaction has been created but no attempt has been made yet.
- **PENDING** — Transaction is being processed. Terminal status not yet reached.

### Intent Status Values

- **SUCCEEDED** — At least one transaction under this intent has status SUCCESS.
- **FAILED** — All transactions under this intent have failed or been cancelled. The customer gave up or the intent expired.

---

## Currency Rules

### Never sum amounts across currencies

Transaction amounts are in local currency. USD 100 + INR 5000 + JPY 8000 is a meaningless number. All amount aggregations must either filter by a single currency or group by currency.

### Currency is determined by merchant region

The currency on a transaction is always the local currency of the merchant's country:
- United States → USD
- United Kingdom → GBP
- Germany → EUR
- India → INR
- Australia → AUD
- Singapore → SGD
- Japan → JPY

---

## Success Rate Calculation Rules

### Transaction-level success rate

Uses fact_transactions. Denominator is ALL transactions (SUCCESS + FAILED + CANCELLED). This measures "what percentage of transaction attempts work."

### Intent-level completion rate

Uses fact_transactions with DISTINCT on payment_intent_id. Denominator is all unique intents. Numerator is intents that have at least one SUCCESS transaction. This measures "what percentage of customers eventually pay."

### Completion rate is always >= success rate

Because an intent with 2 failed transactions and 1 successful transaction has 33% transaction success rate but 100% intent completion rate.

---

## Refund Rules

### Only successful transactions can be refunded

A refund is always linked to a transaction with status SUCCESS. You cannot refund a failed transaction.

### Refund amount equals transaction amount

In this system, refunds are always full refunds. The refund_amount equals the original transaction amount. Partial refunds are not supported.

### Refund reasons

- **CUSTOMER_REQUEST** — Customer asked for a refund
- **ORDER_CANCELLED** — The order was cancelled after payment
- **DUPLICATE_PAYMENT** — Customer was charged twice
- **FRAUD** — Transaction flagged as fraudulent
- **OTHER** — Other reasons

---

## Settlement Rules

### Settlement period

Settlements are monthly. Each settlement covers transactions from the first to last day of a calendar month.

### Settlement formula

```
net_settlement_amount = gross_payment_amount
                       - refund_deductions
                       - chargeback_deductions
                       - platform_fee
                       - tax_amount
```

### Platform fee

PayLens charges a 2% platform fee on gross payment amount. This is PayLens's revenue.

### Tax

18% GST is charged on the platform fee (not on the gross amount). So tax = platform_fee * 0.18.

### Settlement delay

Settlement delay is measured from the end of the settlement period, not the start. A settlement for June 2024 (period_end = June 30) that settles on July 3 has a delay of 3 days.

---

## Failure Code Rules

### Failure categories

- **CUSTOMER_SIDE** — The customer caused the failure (wrong PIN, insufficient funds, expired card)
- **BANK_SIDE** — The issuing bank caused the failure (timeout, server error, declined)
- **MERCHANT_SIDE** — Merchant configuration issue
- **GATEWAY_SIDE** — Payment gateway error or timeout
- **NETWORK_SIDE** — Network connectivity issue
- **UNKNOWN** — Could not determine the cause

### Retryable failures

Some failures are transient and worth retrying (is_retryable = TRUE): bank timeouts, gateway timeouts, network errors. Others are permanent (is_retryable = FALSE): insufficient funds, expired cards, fraud flags.

### Failure codes only exist on failed attempts

Successful attempts have failure_code = NULL. Always use LEFT JOIN when joining fact_attempts to dim_failure_code, and filter to failed attempts when analyzing failures.

---

## Dimension Rules

### Merchant risk tier

- **LOW** — Standard merchants with good track record
- **MEDIUM** — Merchants with some risk indicators
- **HIGH** — High-risk merchants requiring additional monitoring

Risk tier is assigned at onboarding and can change over time based on performance.

### Customer segment

- **NEW** — First-time customer
- **RETURNING** — Has made previous purchases
- **PREMIUM** — High-value customer
- **FREQUENT** — Makes regular purchases

### Payment method groups

- **UPI** — India-specific real-time payment system
- **CARD** — Includes both CREDIT_CARD and DEBIT_CARD
- **BANK_BASED** — NET_BANKING (direct bank transfers)
- **WALLET** — Digital wallets

When analyzing by "cards", filter by method_group = 'CARD' in dim_payment_method to include both credit and debit cards.

---

## Athena SQL Dialect Notes

### Use CAST for division

Integer division in Athena truncates to 0. Always CAST to DOUBLE before dividing:
```sql
CAST(numerator AS DOUBLE) / denominator
```

### Use APPROX_PERCENTILE for percentiles

Athena does not support exact PERCENTILE_CONT. Use APPROX_PERCENTILE instead:
```sql
APPROX_PERCENTILE(latency_ms, 0.95)
```

### Date functions

```sql
DATE_TRUNC('month', transaction_date)    -- truncate to first day of month
DATE_FORMAT(timestamp, '%Y-%m')          -- format as '2024-07'
YEAR(date_column)                        -- extract year
MONTH(date_column)                       -- extract month
```

### Partition pruning

fact_transactions, fact_attempts, and fact_refunds are partitioned by currency. Including `WHERE currency = 'USD'` in queries dramatically reduces the data scanned and lowers cost.

---

## Query Optimization Rules

Always follow these rules when generating SQL for Athena to minimize cost and maximize performance.

### Rule 1: Always use partition filters when querying a single currency

Athena charges per TB scanned. Partition pruning skips irrelevant data entirely.

```sql
-- BAD: scans all 7 currency partitions
SELECT SUM(amount)
FROM fact_transactions
WHERE transaction_status = 'SUCCESS'

-- GOOD: scans only USD partition
SELECT SUM(amount)
FROM fact_transactions
WHERE transaction_status = 'SUCCESS'
AND currency = 'USD'
```

If the user asks about a specific country, infer the currency from the country and add the filter:
- United States → currency = 'USD'
- United Kingdom → currency = 'GBP'
- Germany → currency = 'EUR'
- India → currency = 'INR'
- Australia → currency = 'AUD'
- Singapore → currency = 'SGD'
- Japan → currency = 'JPY'

If the user asks across all currencies, always GROUP BY currency — never sum across currencies.

### Rule 2: Filter dimension tables before joining to large fact tables

When filtering by a dimension attribute (merchant country, payment method name, etc.), filter the dimension first to reduce the join size.

```sql
-- LESS OPTIMAL: joins all merchants then filters
SELECT COUNT(*)
FROM fact_transactions ft
JOIN dim_merchant m ON ft.merchant_id = m.merchant_id
WHERE m.merchant_country = 'India'

-- MORE OPTIMAL: filter dimension first
WITH india_merchants AS (
    SELECT merchant_id
    FROM dim_merchant
    WHERE merchant_country = 'India'
)
SELECT COUNT(*)
FROM fact_transactions ft
JOIN india_merchants m ON ft.merchant_id = m.merchant_id
```

### Rule 3: Aggregate at the correct grain before joining

When combining data from different fact tables, aggregate each fact table independently first, then join the results.

```sql
-- BAD: joining facts directly inflates numbers
SELECT m.merchant_name, SUM(ft.amount), COUNT(fa.attempt_id)
FROM fact_transactions ft
JOIN fact_attempts fa ON ft.transaction_id = fa.transaction_id
JOIN dim_merchant m ON ft.merchant_id = m.merchant_id
GROUP BY m.merchant_name

-- GOOD: aggregate each fact separately then combine
WITH txn_summary AS (
    SELECT merchant_id, SUM(amount) as total_amount
    FROM fact_transactions
    WHERE transaction_status = 'SUCCESS'
    GROUP BY merchant_id
),
attempt_summary AS (
    SELECT merchant_id, COUNT(*) as total_attempts
    FROM fact_attempts
    GROUP BY merchant_id
)
SELECT
    m.merchant_name,
    t.total_amount,
    a.total_attempts
FROM txn_summary t
JOIN attempt_summary a ON t.merchant_id = a.merchant_id
JOIN dim_merchant m ON t.merchant_id = m.merchant_id
```

### Rule 4: Use LIMIT for top/bottom N queries

Always include LIMIT when the user asks for "top", "worst", "best", or "bottom" results. This prevents Athena from returning unnecessarily large result sets.

```sql
-- User asks: "Which are the top 5 merchants by GMV?"
SELECT m.merchant_name, SUM(ft.amount) as gmv
FROM fact_transactions ft
JOIN dim_merchant m ON ft.merchant_id = m.merchant_id
WHERE ft.transaction_status = 'SUCCESS'
GROUP BY m.merchant_name
ORDER BY gmv DESC
LIMIT 5
```

### Rule 5: Use APPROX functions for large aggregations

Athena provides approximate aggregation functions that are faster and cheaper on large datasets.

```sql
-- Use APPROX_PERCENTILE instead of exact percentile
APPROX_PERCENTILE(latency_ms, 0.95)

-- Use APPROX_DISTINCT for approximate count distinct on large datasets
APPROX_DISTINCT(customer_id)
```

### Rule 6: Prefer date_key joins over date function comparisons

Joining on the integer date_key is faster than applying date functions inline.

```sql
-- LESS OPTIMAL: applies function to every row
SELECT *
FROM fact_transactions
WHERE MONTH(transaction_date) = 7 AND YEAR(transaction_date) = 2024

-- MORE OPTIMAL: join to dim_date and filter there
SELECT ft.*
FROM fact_transactions ft
JOIN dim_date d ON ft.date_key = d.date_key
WHERE d.month = 7 AND d.year = 2024
```

### Rule 7: Use COALESCE for NULL-safe calculations

When columns can be NULL (like bank_id for wallet payments, or failure_code for successful attempts), use COALESCE to provide defaults.

```sql
-- NULL-safe refund calculation
SELECT
    COALESCE(refund_count, 0) as refunds,
    COALESCE(refund_amount, 0.0) as refund_total
FROM ...
```

### Rule 8: Always CAST before division

Integer division in Athena returns 0 for values less than 1. Always CAST the numerator to DOUBLE.

```sql
-- BAD: returns 0 because 1805/18294 < 1
SELECT 1805 / 18294

-- GOOD: returns 0.0987...
SELECT CAST(1805 AS DOUBLE) / 18294
```