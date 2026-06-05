-- 1. merchants
CREATE TABLE merchants (
    merchant_id VARCHAR(20) PRIMARY KEY,
    merchant_name VARCHAR(100) NOT NULL,
    merchant_category VARCHAR(50) NOT NULL,
    merchant_city VARCHAR(50),
    merchant_state VARCHAR(50),
    merchant_country VARCHAR(50) NOT NULL DEFAULT 'India',
    onboarding_date DATE NOT NULL,
    risk_tier VARCHAR(10) NOT NULL CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
-- 2. customers
CREATE TABLE customers (
    customer_id VARCHAR(20) PRIMARY KEY,
    customer_city VARCHAR(50),
    customer_state VARCHAR(50),
    customer_country VARCHAR(50) NOT NULL DEFAULT 'India',
    customer_segment VARCHAR(20) NOT NULL CHECK (customer_segment IN ('NEW', 'RETURNING', 'PREMIUM', 'FREQUENT')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
-- 3. payment_methods
CREATE TABLE payment_methods (
    payment_method_id VARCHAR(20) PRIMARY KEY,
    method_name VARCHAR(30) NOT NULL CHECK (method_name IN ('UPI', 'CREDIT_CARD', 'DEBIT_CARD', 'NET_BANKING', 'WALLET')),
    method_group VARCHAR(20) NOT NULL CHECK (method_group IN ('UPI', 'CARD', 'BANK_BASED', 'WALLET')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
-- 4. banks
CREATE TABLE banks (
    bank_id VARCHAR(20) PRIMARY KEY,
    bank_name VARCHAR(100) NOT NULL,
    bank_type VARCHAR(20) NOT NULL CHECK (bank_type IN ('PUBLIC', 'PRIVATE', 'SMALL_FINANCE', 'FOREIGN')),
    country VARCHAR(50) NOT NULL DEFAULT 'India',
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
-- 5. failure_codes
CREATE TABLE failure_codes (
    failure_code VARCHAR(50) PRIMARY KEY,
    failure_category VARCHAR(20) NOT NULL CHECK (failure_category IN ('CUSTOMER_SIDE', 'BANK_SIDE', 'MERCHANT_SIDE', 'GATEWAY_SIDE', 'NETWORK_SIDE', 'UNKNOWN')),
    failure_description TEXT NOT NULL,
    is_retryable BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
-- 6. payment_intents
CREATE TABLE payment_intents (
    payment_intent_id VARCHAR(30) PRIMARY KEY,
    merchant_id VARCHAR(20) NOT NULL REFERENCES merchants(merchant_id),
    customer_id VARCHAR(20) NOT NULL REFERENCES customers(customer_id),
    requested_amount  NUMERIC(12, 2) NOT NULL CHECK (requested_amount > 0),
    currency VARCHAR(5) NOT NULL DEFAULT 'INR',
    intent_status VARCHAR(20) NOT NULL CHECK (intent_status IN ('CREATED', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'EXPIRED')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
-- 7. payment_transactions
CREATE TABLE payment_transactions (
    transaction_id VARCHAR(30) PRIMARY KEY,
    payment_intent_id VARCHAR(30) NOT NULL REFERENCES payment_intents(payment_intent_id),
    merchant_id VARCHAR(20) NOT NULL REFERENCES merchants(merchant_id),
    customer_id VARCHAR(20) NOT NULL REFERENCES customers(customer_id),
    payment_method_id VARCHAR(20) NOT NULL REFERENCES payment_methods(payment_method_id),
    bank_id VARCHAR(20) REFERENCES banks(bank_id),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(5) NOT NULL DEFAULT 'INR',
    transaction_status VARCHAR(20) NOT NULL CHECK (transaction_status IN ('INITIATED', 'SUCCESS', 'FAILED', 'PENDING', 'CANCELLED')),
    transaction_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Enforce only one SUCCESS transaction per payment intent
CREATE UNIQUE INDEX unique_successful_transaction_per_intent
    ON payment_transactions(payment_intent_id)
    WHERE transaction_status = 'SUCCESS';

-- 8. payment_attempts
CREATE TABLE payment_attempts (
    attempt_id VARCHAR(30) PRIMARY KEY,
    transaction_id VARCHAR(30) NOT NULL REFERENCES payment_transactions(transaction_id),
    gateway_provider VARCHAR(50) NOT NULL,
    attempt_status VARCHAR(20) NOT NULL CHECK (attempt_status IN ('SUCCESS', 'FAILED', 'TIMEOUT', 'PENDING')),
    failure_code VARCHAR(50) REFERENCES failure_codes(failure_code),
    latency_ms INTEGER CHECK (latency_ms >= 0),
    attempted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
-- 9. refunds
CREATE TABLE refunds (
    refund_id VARCHAR(30) PRIMARY KEY,
    transaction_id VARCHAR(30) NOT NULL REFERENCES payment_transactions(transaction_id),
    merchant_id VARCHAR(20) NOT NULL REFERENCES merchants(merchant_id),
    refund_amount NUMERIC(12, 2) NOT NULL CHECK (refund_amount > 0),
    currency VARCHAR(5) NOT NULL DEFAULT 'INR',
    refund_status VARCHAR(20) NOT NULL CHECK (refund_status IN ('INITIATED', 'PROCESSED', 'FAILED', 'PENDING')),
    refund_reason VARCHAR(50) NOT NULL CHECK (refund_reason IN ('CUSTOMER_REQUEST', 'ORDER_CANCELLED', 'DUPLICATE_PAYMENT', 'FRAUD', 'OTHER')),
    refund_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
-- 10. settlements
CREATE TABLE settlements (
    settlement_id VARCHAR(30) PRIMARY KEY,
    merchant_id VARCHAR(20) NOT NULL REFERENCES merchants(merchant_id),
    settlement_period_start DATE NOT NULL,
    settlement_period_end DATE NOT NULL,
    settlement_date DATE,
    gross_payment_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    refund_deductions NUMERIC(14, 2) NOT NULL DEFAULT 0,
    chargeback_deductions NUMERIC(14, 2) NOT NULL DEFAULT 0,
    platform_fee NUMERIC(14, 2) NOT NULL DEFAULT 0,
    tax_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    net_settlement_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    settlement_status VARCHAR(20) NOT NULL CHECK (settlement_status IN ('PENDING', 'SETTLED', 'FAILED')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
-- 11. settlement_transactions
CREATE TABLE settlement_transactions (
    settlement_id VARCHAR(30) NOT NULL REFERENCES settlements(settlement_id),
    transaction_id VARCHAR(30) NOT NULL REFERENCES payment_transactions(transaction_id),
    gross_amount NUMERIC(12, 2) NOT NULL,
    fee_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    tax_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    net_amount NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (settlement_id, transaction_id)
);
