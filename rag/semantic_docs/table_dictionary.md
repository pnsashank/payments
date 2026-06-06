# PayLens Table Dictionary

## Database

All tables are in the `paylens_curated` Athena database. Query engine is Athena (Presto/Trino SQL dialect).

---

## Fact Tables

### fact_transactions

The core fact table. Grain: one row per payment transaction. A payment intent can have multiple transactions when a customer retries with a different payment method.

| Column | Type | Description |
|--------|------|-------------|
| transaction_id | STRING | Primary key. Format: TXN_00001. Unique identifier for each transaction. |
| payment_intent_id | STRING | Foreign key to the parent payment intent. Multiple transactions can share the same intent when a customer retries. |
| merchant_id | STRING | Foreign key to dim_merchant. The merchant being paid. |
| customer_id | STRING | Foreign key to dim_customer. The customer making the payment. |
| payment_method_id | STRING | Foreign key to dim_payment_method. The payment method used for this specific transaction (UPI, credit card, etc). |
| bank_id | STRING | Foreign key to dim_bank. The bank processing this transaction. |
| amount | DOUBLE | Transaction amount in the local currency. Do not sum across different currencies without conversion. |
| currency | STRING | ISO currency code (USD, GBP, EUR, INR, AUD, SGD, JPY). This is also the partition column. |
| transaction_status | STRING | Outcome of the transaction. Values: SUCCESS, FAILED, CANCELLED, INITIATED, PENDING. Only SUCCESS means money was collected. |
| intent_status | STRING | Outcome of the parent payment intent. Values: SUCCEEDED, FAILED. An intent SUCCEEDED if at least one of its transactions was SUCCESS. |
| transaction_timestamp | TIMESTAMP | When the transaction was initiated by the customer. |
| completed_at | TIMESTAMP | When the transaction reached a terminal state (SUCCESS or FAILED). NULL if still PENDING. |
| processing_time_seconds | BIGINT | Computed: completed_at minus transaction_timestamp in seconds. Measures how long the transaction took to process. NULL if completed_at is NULL. |
| transaction_date | DATE | Date portion of transaction_timestamp. Use for daily aggregations. |
| date_key | INT | Foreign key to dim_date. Format: YYYYMMDD as integer (e.g., 20240715). |

### fact_attempts

Gateway-level attempt details. Grain: one row per gateway attempt. A single transaction can have multiple attempts when the system retries through different payment gateways.

| Column | Type | Description |
|--------|------|-------------|
| attempt_id | STRING | Primary key. Format: ATT_00001. |
| transaction_id | STRING | Foreign key to fact_transactions. The parent transaction this attempt belongs to. |
| payment_intent_id | STRING | Denormalized from fact_transactions for query convenience. |
| merchant_id | STRING | Denormalized from fact_transactions. |
| customer_id | STRING | Denormalized from fact_transactions. |
| payment_method_id | STRING | Denormalized from fact_transactions. |
| bank_id | STRING | Denormalized from fact_transactions. |
| gateway_provider | STRING | The payment gateway that processed this attempt. Values: Stripe, Adyen, Braintree, Checkout.com, WorldPay. |
| attempt_status | STRING | Outcome of this attempt. Values: SUCCESS, FAILED, TIMEOUT, PENDING. |
| failure_code | STRING | Foreign key to dim_failure_code. NULL for successful attempts. Contains the specific error code for failed attempts. |
| latency_ms | INT | Time in milliseconds the gateway took to respond. Key performance metric. |
| currency | STRING | Partition column. Same currency as the parent transaction. |
| attempted_at | TIMESTAMP | When this attempt was made. |
| attempt_date | DATE | Date portion of attempted_at. |
| date_key | INT | Foreign key to dim_date. |

### fact_refunds

Refund events. Grain: one row per refund. Only successful transactions can be refunded.

| Column | Type | Description |
|--------|------|-------------|
| refund_id | STRING | Primary key. Format: REF_00001. |
| transaction_id | STRING | Foreign key to fact_transactions. The successful transaction being refunded. |
| merchant_id | STRING | Foreign key to dim_merchant. The merchant issuing the refund. |
| refund_amount | DOUBLE | Amount refunded in local currency. |
| currency | STRING | Partition column. |
| refund_status | STRING | Current state. Values: PROCESSED, FAILED, PENDING. |
| refund_reason | STRING | Why the refund was initiated. Values: CUSTOMER_REQUEST, ORDER_CANCELLED, DUPLICATE_PAYMENT, FRAUD, OTHER. |
| refund_timestamp | TIMESTAMP | When the refund was initiated. |
| processed_at | TIMESTAMP | When the refund was actually processed. NULL if still PENDING. |
| refund_processing_time_seconds | BIGINT | Computed: processed_at minus refund_timestamp in seconds. Measures refund processing speed. NULL if processed_at is NULL. |
| refund_date | DATE | Date portion of refund_timestamp. |
| date_key | INT | Foreign key to dim_date. |

### fact_settlements

Merchant settlement payouts. Grain: one row per settlement period per merchant.

| Column | Type | Description |
|--------|------|-------------|
| settlement_id | STRING | Primary key. Format: SET_00001. |
| merchant_id | STRING | Foreign key to dim_merchant. The merchant being paid out. |
| settlement_period_start | DATE | First day of the settlement period. |
| settlement_period_end | DATE | Last day of the settlement period. |
| settlement_date | DATE | When the settlement was actually paid to the merchant. |
| gross_payment_amount | DOUBLE | Total transaction value before any deductions. |
| refund_deductions | DOUBLE | Amount deducted for refunds during this period. |
| chargeback_deductions | DOUBLE | Amount deducted for chargebacks. |
| platform_fee | DOUBLE | PayLens platform fee (2% of gross). This is PayLens revenue. |
| tax_amount | DOUBLE | Tax on the platform fee (18% GST). |
| net_settlement_amount | DOUBLE | What the merchant actually receives: gross minus refunds minus chargebacks minus platform fee minus tax. |
| settlement_status | STRING | Values: SETTLED, PENDING, FAILED. |
| settlement_delay_days | INT | Computed: settlement_date minus settlement_period_end in days. Measures how many days after the period ended before the merchant got paid. |
| date_key | INT | Foreign key to dim_date based on settlement_date. |

---

## Dimension Tables

### dim_merchant

Merchant profile information.

| Column | Type | Description |
|--------|------|-------------|
| merchant_id | STRING | Primary key. Format: MER_00001. |
| merchant_name | STRING | Display name of the merchant. |
| merchant_category | STRING | Business category. Values: ecommerce, food, travel, education, retail, saas, healthcare, gaming. |
| merchant_city | STRING | City where the merchant is based. |
| merchant_state | STRING | State or region. |
| merchant_country | STRING | Country. Values: United States, United Kingdom, Germany, India, Australia, Singapore, Japan. |
| risk_tier | STRING | Risk classification. Values: LOW, MEDIUM, HIGH. Assigned during onboarding. |
| onboarding_date | DATE | When the merchant joined PayLens. |
| is_active | BOOLEAN | Whether the merchant is currently active on the platform. |

### dim_customer

Customer profile information.

| Column | Type | Description |
|--------|------|-------------|
| customer_id | STRING | Primary key. Format: CUS_00001. |
| customer_city | STRING | Customer's city. |
| customer_state | STRING | Customer's state or region. |
| customer_country | STRING | Customer's country. |
| customer_segment | STRING | Values: NEW, RETURNING, PREMIUM, FREQUENT. Based on historical behavior. |

### dim_payment_method

Payment method definitions.

| Column | Type | Description |
|--------|------|-------------|
| payment_method_id | STRING | Primary key. Values: PM_UPI, PM_CREDIT, PM_DEBIT, PM_NETBANKING, PM_WALLET. |
| method_name | STRING | Display name. Values: UPI, CREDIT_CARD, DEBIT_CARD, NET_BANKING, WALLET. |
| method_group | STRING | Grouping. Values: UPI, CARD, BANK_BASED, WALLET. CARD includes both credit and debit. |

### dim_bank

Bank information.

| Column | Type | Description |
|--------|------|-------------|
| bank_id | STRING | Primary key. Format: BNK_00001. |
| bank_name | STRING | Full bank name (e.g., JPMorgan Chase, HDFC Bank, Commonwealth Bank). |
| bank_type | STRING | Values: PUBLIC, PRIVATE. |
| bank_country | STRING | Country where the bank operates. |

### dim_failure_code

Failure code definitions for diagnosing payment failures.

| Column | Type | Description |
|--------|------|-------------|
| failure_code | STRING | Primary key. The specific error code (e.g., BANK_TIMEOUT, INSUFFICIENT_FUNDS). |
| failure_category | STRING | High-level category. Values: CUSTOMER_SIDE, BANK_SIDE, MERCHANT_SIDE, GATEWAY_SIDE, NETWORK_SIDE, UNKNOWN. |
| failure_description | STRING | Plain English description of what caused the failure. |
| is_retryable | BOOLEAN | Whether the failure is transient and worth retrying. TRUE means the same attempt might succeed if retried. |

### dim_date

Calendar dimension covering June 2024 to May 2025.

| Column | Type | Description |
|--------|------|-------------|
| date_key | INT | Primary key. Format: YYYYMMDD as integer (e.g., 20240715). Join to fact tables on this column. |
| full_date | DATE | The actual date value. |
| year | INT | Four-digit year (2024 or 2025). |
| quarter | INT | Quarter number (1-4). |
| month | INT | Month number (1-12). |
| month_name | STRING | Full month name (January, February, etc.). |
| week_of_year | INT | ISO week number (1-52). |
| day_of_week | INT | Day number (1=Sunday, 7=Saturday). |
| day_name | STRING | Full day name (Monday, Tuesday, etc.). |
| is_weekend | BOOLEAN | TRUE for Saturday and Sunday. |