# PayLens Join Rules

## Overview

All tables are in the `paylens_curated` database. Fact tables connect to dimension tables via foreign keys. Use LEFT JOIN from facts to dimensions to preserve all fact rows even when a dimension value is NULL.

---

## Fact to Dimension Joins

### fact_transactions joins

```sql
-- To get merchant details
FROM fact_transactions ft
JOIN dim_merchant m ON ft.merchant_id = m.merchant_id

-- To get customer details
FROM fact_transactions ft
JOIN dim_customer c ON ft.customer_id = c.customer_id

-- To get payment method name
FROM fact_transactions ft
JOIN dim_payment_method pm ON ft.payment_method_id = pm.payment_method_id

-- To get bank name
FROM fact_transactions ft
LEFT JOIN dim_bank b ON ft.bank_id = b.bank_id
-- LEFT JOIN because bank_id can be NULL for wallet payments

-- To get date attributes (month name, quarter, is_weekend)
FROM fact_transactions ft
JOIN dim_date d ON ft.date_key = d.date_key
```

### fact_attempts joins

```sql
-- To get failure details (only for failed attempts)
FROM fact_attempts fa
LEFT JOIN dim_failure_code fc ON fa.failure_code = fc.failure_code
-- LEFT JOIN because successful attempts have NULL failure_code

-- To get merchant details
FROM fact_attempts fa
JOIN dim_merchant m ON fa.merchant_id = m.merchant_id

-- To get payment method details
FROM fact_attempts fa
JOIN dim_payment_method pm ON fa.payment_method_id = pm.payment_method_id

-- To get bank details
FROM fact_attempts fa
LEFT JOIN dim_bank b ON fa.bank_id = b.bank_id

-- To get date attributes
FROM fact_attempts fa
JOIN dim_date d ON fa.date_key = d.date_key
```

### fact_refunds joins

```sql
-- To get merchant details
FROM fact_refunds fr
JOIN dim_merchant m ON fr.merchant_id = m.merchant_id

-- To get the original transaction details
FROM fact_refunds fr
JOIN fact_transactions ft ON fr.transaction_id = ft.transaction_id

-- To get date attributes
FROM fact_refunds fr
JOIN dim_date d ON fr.date_key = d.date_key
```

### fact_settlements joins

```sql
-- To get merchant details
FROM fact_settlements fs
JOIN dim_merchant m ON fs.merchant_id = m.merchant_id

-- To get date attributes
FROM fact_settlements fs
JOIN dim_date d ON fs.date_key = d.date_key
```

---

## Fact to Fact Joins

### fact_transactions to fact_attempts

Join when you need both transaction-level and attempt-level data together.

```sql
FROM fact_transactions ft
JOIN fact_attempts fa ON ft.transaction_id = fa.transaction_id
```

**Caution:** This is a one-to-many join. One transaction can have multiple attempts. If you aggregate transaction amounts after this join, you will get inflated numbers. Always aggregate at the correct grain.

### fact_transactions to fact_refunds

Join when you need to connect refunds to their original transactions.

```sql
FROM fact_transactions ft
LEFT JOIN fact_refunds fr ON ft.transaction_id = fr.transaction_id
```

**Note:** Only successful transactions can have refunds. Use LEFT JOIN to keep all transactions.

---

## Join Key Reference

| From Table | To Table | Join Key | Join Type | Notes |
|-----------|----------|----------|-----------|-------|
| fact_transactions | dim_merchant | merchant_id | INNER JOIN | |
| fact_transactions | dim_customer | customer_id | INNER JOIN | |
| fact_transactions | dim_payment_method | payment_method_id | INNER JOIN | |
| fact_transactions | dim_bank | bank_id | LEFT JOIN | NULL for wallet payments |
| fact_transactions | dim_date | date_key | INNER JOIN | |
| fact_attempts | dim_merchant | merchant_id | INNER JOIN | Denormalized key |
| fact_attempts | dim_customer | customer_id | INNER JOIN | Denormalized key |
| fact_attempts | dim_payment_method | payment_method_id | INNER JOIN | Denormalized key |
| fact_attempts | dim_bank | bank_id | LEFT JOIN | Denormalized key |
| fact_attempts | dim_failure_code | failure_code | LEFT JOIN | NULL for successful attempts |
| fact_attempts | dim_date | date_key | INNER JOIN | |
| fact_refunds | dim_merchant | merchant_id | INNER JOIN | |
| fact_refunds | dim_date | date_key | INNER JOIN | |
| fact_settlements | dim_merchant | merchant_id | INNER JOIN | |
| fact_settlements | dim_date | date_key | INNER JOIN | |
| fact_attempts | fact_transactions | transaction_id | INNER JOIN | One-to-many: one txn has many attempts |
| fact_refunds | fact_transactions | transaction_id | INNER JOIN | One-to-one |

---

## Common Anti-Patterns to Avoid

### Do not join fact_transactions to fact_settlements directly

There is no direct foreign key between transactions and settlements. Settlements aggregate multiple transactions over a time period. To connect them, join through merchant_id and date range:

```sql
FROM fact_settlements fs
JOIN fact_transactions ft
  ON fs.merchant_id = ft.merchant_id
  AND ft.transaction_date BETWEEN fs.settlement_period_start AND fs.settlement_period_end
```

### Do not aggregate amounts after a one-to-many join without care

If you join fact_transactions to fact_attempts and then SUM(amount), every transaction amount gets counted once per attempt. Always aggregate at the transaction level first, then join.

```sql
-- WRONG: inflates amounts
SELECT SUM(ft.amount)
FROM fact_transactions ft
JOIN fact_attempts fa ON ft.transaction_id = fa.transaction_id

-- CORRECT: aggregate at transaction level
SELECT SUM(amount)
FROM fact_transactions
WHERE transaction_status = 'SUCCESS'
```

### Do not sum amounts across currencies

Amounts are in local currency. Summing USD + INR + JPY produces a meaningless number. Always filter by a single currency or group by currency.