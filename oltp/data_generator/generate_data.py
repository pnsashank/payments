import os
import random
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

load_dotenv()

# Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

START_DATE = datetime(2024, 6, 1)
END_DATE = datetime(2025, 5, 31)

NUM_MERCHANTS = 50
NUM_CUSTOMERS = 5000
NUM_PAYMENT_INTENTS = 20000

# Reference Data
REGIONS = {
    "US": {
        "country": "United States",
        "states": ["California", "New York", "Texas", "Florida", "Illinois"],
        "cities": ["San Francisco", "New York", "Austin", "Miami", "Chicago"],
        "currency": "USD",
        "payment_method_weights": {"CREDIT_CARD": 0.45, "DEBIT_CARD": 0.35, "WALLET": 0.15, "NET_BANKING": 0.05},
        "banks": ["JPMorgan Chase", "Bank of America", "Wells Fargo", "Citibank"]
    },
    "UK": {
        "country": "United Kingdom",
        "states": ["England", "Scotland", "Wales"],
        "cities": ["London", "Manchester", "Edinburgh", "Birmingham"],
        "currency": "GBP",
        "payment_method_weights": {"CREDIT_CARD": 0.40, "DEBIT_CARD": 0.40, "WALLET": 0.15, "NET_BANKING": 0.05},
        "banks": ["Barclays", "HSBC", "Lloyds Bank", "NatWest"]
    },
    "DE": {
        "country": "Germany",
        "states": ["Bavaria", "Berlin", "Hamburg", "North Rhine-Westphalia"],
        "cities": ["Berlin", "Munich", "Hamburg", "Frankfurt"],
        "currency": "EUR",
        "payment_method_weights": {"DEBIT_CARD": 0.45, "CREDIT_CARD": 0.25, "NET_BANKING": 0.20, "WALLET": 0.10},
        "banks": ["Deutsche Bank", "Commerzbank", "DZ Bank", "KfW"]
    },
    "IN": {
        "country": "India",
        "states": ["Maharashtra", "Karnataka", "Tamil Nadu", "Delhi", "Telangana"],
        "cities": ["Mumbai", "Bangalore", "Chennai", "Delhi", "Hyderabad"],
        "currency": "INR",
        "payment_method_weights": {"UPI": 0.60, "DEBIT_CARD": 0.15, "CREDIT_CARD": 0.15, "NET_BANKING": 0.10},
        "banks": ["HDFC Bank", "ICICI Bank", "State Bank of India", "Axis Bank"]
    },
    "AU": {
        "country": "Australia",
        "states": ["New South Wales", "Victoria", "Queensland", "Western Australia"],
        "cities": ["Sydney", "Melbourne", "Brisbane", "Perth"],
        "currency": "AUD",
        "payment_method_weights": {"CREDIT_CARD": 0.45, "DEBIT_CARD": 0.35, "WALLET": 0.15, "NET_BANKING": 0.05},
        "banks": ["Commonwealth Bank", "ANZ", "Westpac", "NAB"]
    },
    "SG": {
        "country": "Singapore",
        "states": ["Central Region", "East Region", "West Region"],
        "cities": ["Singapore"],
        "currency": "SGD",
        "payment_method_weights": {"CREDIT_CARD": 0.40, "DEBIT_CARD": 0.30, "WALLET": 0.20, "NET_BANKING": 0.10},
        "banks": ["DBS Bank", "OCBC Bank", "UOB", "Standard Chartered"]
    },
    "JP": {
        "country": "Japan",
        "states": ["Tokyo", "Osaka", "Kanagawa", "Aichi"],
        "cities": ["Tokyo", "Osaka", "Yokohama", "Nagoya"],
        "currency": "JPY",
        "payment_method_weights": {"CREDIT_CARD": 0.50, "WALLET": 0.30, "DEBIT_CARD": 0.15, "NET_BANKING": 0.05},
        "banks": ["Mitsubishi UFJ", "Sumitomo Mitsui", "Mizuho Bank", "Japan Post Bank"]
    }
}

MERCHANT_CATEGORIES = ["ecommerce", "food", "travel", "education", "retail", "saas", "healthcare", "gaming"]

RISK_TIERS = ["LOW", "LOW", "LOW", "MEDIUM", "MEDIUM", "HIGH"]

GATEWAY_PROVIDERS = ["Stripe", "Adyen", "Braintree", "Checkout.com", "WorldPay"]

FAILURE_CODE_DATA = [
    ("INSUFFICIENT_FUNDS",      "CUSTOMER_SIDE",  "Customer account has insufficient funds.",               False),
    ("WRONG_UPI_PIN",           "CUSTOMER_SIDE",  "Customer entered incorrect UPI PIN.",                    True),
    ("CARD_EXPIRED",            "CUSTOMER_SIDE",  "Customer card has expired.",                             False),
    ("INVALID_CARD_DETAILS",    "CUSTOMER_SIDE",  "Card number or CVV entered incorrectly.",                True),
    ("TRANSACTION_LIMIT",       "CUSTOMER_SIDE",  "Transaction exceeds customer daily/monthly limit.",      False),
    ("BANK_TIMEOUT",            "BANK_SIDE",      "Bank did not respond within the timeout window.",        True),
    ("BANK_SERVER_ERROR",       "BANK_SIDE",      "Bank internal server error during processing.",          True),
    ("BANK_DECLINED",           "BANK_SIDE",      "Bank declined the transaction without specific reason.", False),
    ("ISSUER_UNAVAILABLE",      "BANK_SIDE",      "Card issuing bank is temporarily unavailable.",          True),
    ("MERCHANT_ACCOUNT_ERROR",  "MERCHANT_SIDE",  "Merchant account configuration issue.",                  False),
    ("MERCHANT_LIMIT_EXCEEDED", "MERCHANT_SIDE",  "Merchant transaction limit exceeded.",                   False),
    ("GATEWAY_TIMEOUT",         "GATEWAY_SIDE",   "Payment gateway timed out processing the request.",      True),
    ("GATEWAY_ERROR",           "GATEWAY_SIDE",   "Payment gateway returned an unexpected error.",          True),
    ("NETWORK_ERROR",           "NETWORK_SIDE",   "Network connectivity issue during payment processing.",  True),
    ("CONNECTION_RESET",        "NETWORK_SIDE",   "Connection was reset during payment attempt.",           True),
    ("FRAUD_SUSPECTED",         "UNKNOWN",        "Transaction flagged for suspected fraud.",               False),
    ("UNKNOWN_ERROR",           "UNKNOWN",        "An unknown error occurred during payment processing.",   True),
]

PAYMENT_METHOD_DATA = [
    ("PM_UPI",        "UPI",         "UPI"),
    ("PM_CREDIT",     "CREDIT_CARD", "CARD"),
    ("PM_DEBIT",      "DEBIT_CARD",  "CARD"),
    ("PM_NETBANKING", "NET_BANKING", "BANK_BASED"),
    ("PM_WALLET",     "WALLET",      "WALLET"),
]

METHOD_SUCCESS_RATES = {
    "UPI":         0.88,
    "CREDIT_CARD": 0.91,
    "DEBIT_CARD":  0.87,
    "NET_BANKING": 0.82,
    "WALLET":      0.93
}

BANK_RELIABILITY = {
    "JPMorgan Chase":      1.02, "Bank of America":     1.00,
    "Wells Fargo":         0.98, "Citibank":            1.01,
    "Barclays":            1.00, "HSBC":                1.02,
    "Lloyds Bank":         0.99, "NatWest":             0.97,
    "Deutsche Bank":       1.00, "Commerzbank":         0.98,
    "DZ Bank":             0.99, "KfW":                 1.01,
    "HDFC Bank":           1.02, "ICICI Bank":          1.00,
    "State Bank of India": 0.93, "Axis Bank":           0.97,
    "Commonwealth Bank":   1.01, "ANZ":                 1.00,
    "Westpac":             0.99, "NAB":                 0.98,
    "DBS Bank":            1.02, "OCBC Bank":           1.01,
    "UOB":                 1.00, "Standard Chartered":  0.99,
    "Mitsubishi UFJ":      1.01, "Sumitomo Mitsui":     1.00,
    "Mizuho Bank":         0.98, "Japan Post Bank":     0.96,
}

PLATFORM_FEE_RATE = 0.02
TAX_RATE = 0.18

# Helpers
def random_timestamp(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

def weighted_choice(options: dict) -> str:
    keys = list(options.keys())
    weights = list(options.values())
    return random.choices(keys, weights=weights, k=1)[0]

def fmt_id(prefix: str, n: int) -> str:
    return f"{prefix}_{n:05d}"

def batch_insert(cur, sql, rows):
    psycopg2.extras.execute_values(cur, sql, rows, page_size=1000)

# Build All Data In Memory, Then Insert In Batches
def build_reference_data():
    failure_code_rows = [
        (code, category, description, is_retryable)
        for code, category, description, is_retryable in FAILURE_CODE_DATA
    ]
    payment_method_rows = [
        (method_id, method_name, method_group, True)
        for method_id, method_name, method_group in PAYMENT_METHOD_DATA
    ]

    bank_rows = []
    bank_id_map = {}
    bank_counter = 1
    for region_code, region_data in REGIONS.items():
        for bank_name in region_data["banks"]:
            bank_id = fmt_id("BNK", bank_counter)
            bank_id_map[bank_name] = bank_id
            bank_type = "PUBLIC" if bank_name in ["State Bank of India", "Japan Post Bank", "KfW"] else "PRIVATE"
            bank_rows.append((bank_id, bank_name, bank_type, region_data["country"], True))
            bank_counter += 1

    return failure_code_rows, payment_method_rows, bank_rows, bank_id_map


def build_merchants():
    merchant_rows = []
    merchant_region_map = {}
    region_codes = list(REGIONS.keys())

    for i in range(1, NUM_MERCHANTS + 1):
        merchant_id = fmt_id("MER", i)
        region_code = region_codes[i % len(region_codes)]
        region = REGIONS[region_code]
        merchant_region_map[merchant_id] = region_code

        merchant_rows.append((
            merchant_id,
            f"Merchant {i}",
            random.choice(MERCHANT_CATEGORIES),
            random.choice(region["cities"]),
            random.choice(region["states"]),
            region["country"],
            (START_DATE - relativedelta(months=random.randint(1, 24))).date(),
            random.choice(RISK_TIERS),
            True,
            datetime.now(),
            datetime.now()
        ))

    return merchant_rows, merchant_region_map


def build_customers():
    customer_rows = []
    customer_region_map = {}
    region_codes = list(REGIONS.keys())

    for i in range(1, NUM_CUSTOMERS + 1):
        customer_id = fmt_id("CUS", i)
        region_code = random.choice(region_codes)
        region = REGIONS[region_code]
        customer_region_map[customer_id] = region_code

        customer_rows.append((
            customer_id,
            random.choice(region["cities"]),
            random.choice(region["states"]),
            region["country"],
            random.choice(["NEW", "RETURNING", "PREMIUM", "FREQUENT"]),
            datetime.now(),
            datetime.now()
        ))

    return customer_rows, customer_region_map


def build_payment_lifecycle(merchant_region_map, customer_region_map, bank_id_map):
    merchant_ids = list(merchant_region_map.keys())
    customer_ids = list(customer_region_map.keys())

    method_id_map = {
        "UPI":         "PM_UPI",
        "CREDIT_CARD": "PM_CREDIT",
        "DEBIT_CARD":  "PM_DEBIT",
        "NET_BANKING": "PM_NETBANKING",
        "WALLET":      "PM_WALLET"
    }

    failure_codes      = [row[0] for row in FAILURE_CODE_DATA]
    retryable_codes    = [row[0] for row in FAILURE_CODE_DATA if row[3]]

    amount_ranges = {
        "USD": (10, 500), "GBP": (10, 400), "EUR": (10, 450),
        "INR": (100, 50000), "AUD": (10, 600), "SGD": (10, 500), "JPY": (1000, 80000)
    }

    intent_rows           = []
    transaction_rows      = []
    attempt_rows          = []
    refund_rows           = []
    settlement_rows       = []
    settlement_txn_rows   = []

    attempt_counter  = 1
    refund_counter   = 1
    settlement_counter = 1
    settlement_buckets = {}

    for intent_num in range(1, NUM_PAYMENT_INTENTS + 1):
        payment_intent_id = fmt_id("PI", intent_num)
        merchant_id       = random.choice(merchant_ids)
        customer_id       = random.choice(customer_ids)

        merchant_region   = REGIONS[merchant_region_map[merchant_id]]
        currency          = merchant_region["currency"]
        intent_created_at = random_timestamp(START_DATE, END_DATE)

        low, high         = amount_ranges.get(currency, (10, 500))
        requested_amount  = round(random.uniform(low, high), 2)

        num_transactions  = random.choices([1, 2, 3], weights=[0.75, 0.20, 0.05])[0]

        intent_succeeded         = False
        successful_transaction_id = None
        successful_amount        = None
        successful_completed_at  = None

        for txn_num in range(num_transactions):
            method_name       = weighted_choice(merchant_region["payment_method_weights"])
            payment_method_id = method_id_map[method_name]
            bank_name         = random.choice(merchant_region["banks"])
            bank_id           = bank_id_map[bank_name]

            transaction_id        = fmt_id("TXN", (intent_num - 1) * 3 + txn_num + 1)
            transaction_timestamp = intent_created_at + timedelta(seconds=random.randint(1, 300) * txn_num)

            base_success_rate     = METHOD_SUCCESS_RATES[method_name]
            bank_multiplier       = BANK_RELIABILITY.get(bank_name, 1.0)
            adjusted_success_rate = min(base_success_rate * bank_multiplier, 0.99)

            if txn_num > 0:
                adjusted_success_rate = min(adjusted_success_rate * 1.1, 0.99)

            if intent_succeeded:
                transaction_status = random.choice(["FAILED", "CANCELLED"])
            else:
                transaction_status = "SUCCESS" if random.random() < adjusted_success_rate else "FAILED"

            completed_at = (
                transaction_timestamp + timedelta(seconds=random.randint(2, 30))
                if transaction_status in ("SUCCESS", "FAILED") else None
            )

            if transaction_status == "SUCCESS":
                intent_succeeded          = True
                successful_transaction_id = transaction_id
                successful_amount         = requested_amount
                successful_completed_at   = completed_at

            transaction_rows.append((
                transaction_id, payment_intent_id, merchant_id, customer_id,
                payment_method_id, bank_id, requested_amount, currency,
                transaction_status, transaction_timestamp, completed_at,
                transaction_timestamp, transaction_timestamp
            ))

            num_attempts     = random.choices([1, 2, 3], weights=[0.70, 0.25, 0.05])[0]
            attempt_succeeded = False

            for att_num in range(num_attempts):
                attempt_id  = fmt_id("ATT", attempt_counter)
                attempt_counter += 1
                attempted_at = transaction_timestamp + timedelta(seconds=random.randint(1, 10) * att_num)
                gateway      = random.choice(GATEWAY_PROVIDERS)
                latency_ms   = random.randint(100, 3000)

                if attempt_succeeded:
                    attempt_status = "FAILED"
                    failure_code   = random.choice(failure_codes)
                elif att_num == num_attempts - 1 and transaction_status == "SUCCESS":
                    attempt_status  = "SUCCESS"
                    failure_code    = None
                    attempt_succeeded = True
                else:
                    attempt_status = random.choices(["FAILED", "TIMEOUT"], weights=[0.70, 0.30])[0]
                    failure_code   = (
                        random.choice(retryable_codes)
                        if attempt_status == "TIMEOUT"
                        else random.choice(failure_codes)
                    )

                attempt_rows.append((
                    attempt_id, transaction_id, gateway,
                    attempt_status, failure_code, latency_ms,
                    attempted_at, attempted_at
                ))

        intent_status = "SUCCEEDED" if intent_succeeded else "FAILED"
        intent_rows.append((
            payment_intent_id, merchant_id, customer_id,
            requested_amount, currency, intent_status,
            intent_created_at,
            intent_created_at + timedelta(minutes=30),
            intent_created_at
        ))

        if intent_succeeded and random.random() < 0.10:
            refund_id        = fmt_id("REF", refund_counter)
            refund_counter  += 1
            refund_timestamp = successful_completed_at + timedelta(hours=random.randint(1, 72))
            refund_rows.append((
                refund_id, successful_transaction_id, merchant_id,
                successful_amount, currency,
                random.choices(["PROCESSED", "FAILED", "PENDING"], weights=[0.85, 0.05, 0.10])[0],
                random.choice(["CUSTOMER_REQUEST", "ORDER_CANCELLED", "DUPLICATE_PAYMENT", "FRAUD", "OTHER"]),
                refund_timestamp,
                refund_timestamp + timedelta(hours=random.randint(1, 48)) if random.random() > 0.1 else None,
                refund_timestamp, refund_timestamp
            ))

        if intent_succeeded:
            period = successful_completed_at.strftime("%Y-%m")
            key    = (merchant_id, period)
            if key not in settlement_buckets:
                settlement_buckets[key] = []
            settlement_buckets[key].append((successful_transaction_id, successful_amount, currency))

    for (merchant_id, period), txn_list in settlement_buckets.items():
        settlement_id  = fmt_id("SET", settlement_counter)
        settlement_counter += 1

        period_start           = datetime.strptime(period, "%Y-%m").date()
        period_end             = (period_start + relativedelta(months=1) - timedelta(days=1))
        settlement_date        = period_end + timedelta(days=random.randint(2, 5))
        gross_amount           = sum(amount for _, amount, _ in txn_list)
        platform_fee           = round(gross_amount * PLATFORM_FEE_RATE, 2)
        tax_amount             = round(platform_fee * TAX_RATE, 2)
        net_settlement_amount  = round(gross_amount - platform_fee - tax_amount, 2)
        currency               = txn_list[0][2]

        settlement_rows.append((
            settlement_id, merchant_id,
            period_start, period_end, settlement_date,
            gross_amount, 0, 0,
            platform_fee, tax_amount, net_settlement_amount,
            random.choices(["SETTLED", "PENDING", "FAILED"], weights=[0.90, 0.07, 0.03])[0],
            datetime.now(), datetime.now()
        ))

        for txn_id, amount, _ in txn_list:
            fee = round(amount * PLATFORM_FEE_RATE, 2)
            tax = round(fee * TAX_RATE, 2)
            net = round(amount - fee - tax, 2)
            settlement_txn_rows.append((settlement_id, txn_id, amount, fee, tax, net, datetime.now()))

    return intent_rows, transaction_rows, attempt_rows, refund_rows, settlement_rows, settlement_txn_rows


# Main
def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("Building reference data...")
        failure_code_rows, payment_method_rows, bank_rows, bank_id_map = build_reference_data()

        print("Building merchants and customers...")
        merchant_rows, merchant_region_map = build_merchants()
        customer_rows, customer_region_map = build_customers()

        print("Building payment lifecycle in memory...")
        intent_rows, transaction_rows, attempt_rows, refund_rows, settlement_rows, settlement_txn_rows = build_payment_lifecycle(
            merchant_region_map, customer_region_map, bank_id_map
        )

        print("Inserting reference data...")
        batch_insert(cur,
            "INSERT INTO failure_codes (failure_code, failure_category, failure_description, is_retryable) VALUES %s ON CONFLICT DO NOTHING",
            failure_code_rows
        )
        batch_insert(cur,
            "INSERT INTO payment_methods (payment_method_id, method_name, method_group, is_active) VALUES %s ON CONFLICT DO NOTHING",
            payment_method_rows
        )
        batch_insert(cur,
            "INSERT INTO banks (bank_id, bank_name, bank_type, country, is_active) VALUES %s ON CONFLICT DO NOTHING",
            bank_rows
        )
        conn.commit()

        print("Inserting merchants and customers...")
        batch_insert(cur,
            "INSERT INTO merchants (merchant_id, merchant_name, merchant_category, merchant_city, merchant_state, merchant_country, onboarding_date, risk_tier, is_active, created_at, updated_at) VALUES %s",
            merchant_rows
        )
        batch_insert(cur,
            "INSERT INTO customers (customer_id, customer_city, customer_state, customer_country, customer_segment, created_at, updated_at) VALUES %s",
            customer_rows
        )
        conn.commit()

        print(f"Inserting {len(intent_rows):,} payment intents...")
        batch_insert(cur,
            "INSERT INTO payment_intents (payment_intent_id, merchant_id, customer_id, requested_amount, currency, intent_status, created_at, expires_at, updated_at) VALUES %s",
            intent_rows
        )
        conn.commit()

        print(f"Inserting {len(transaction_rows):,} payment transactions...")
        batch_insert(cur,
            "INSERT INTO payment_transactions (transaction_id, payment_intent_id, merchant_id, customer_id, payment_method_id, bank_id, amount, currency, transaction_status, transaction_timestamp, completed_at, created_at, updated_at) VALUES %s",
            transaction_rows
        )
        conn.commit()

        print(f"Inserting {len(attempt_rows):,} payment attempts...")
        batch_insert(cur,
            "INSERT INTO payment_attempts (attempt_id, transaction_id, gateway_provider, attempt_status, failure_code, latency_ms, attempted_at, created_at) VALUES %s",
            attempt_rows
        )
        conn.commit()

        print(f"Inserting {len(refund_rows):,} refunds...")
        batch_insert(cur,
            "INSERT INTO refunds (refund_id, transaction_id, merchant_id, refund_amount, currency, refund_status, refund_reason, refund_timestamp, processed_at, created_at, updated_at) VALUES %s",
            refund_rows
        )
        conn.commit()

        print(f"Inserting {len(settlement_rows):,} settlements...")
        batch_insert(cur,
            "INSERT INTO settlements (settlement_id, merchant_id, settlement_period_start, settlement_period_end, settlement_date, gross_payment_amount, refund_deductions, chargeback_deductions, platform_fee, tax_amount, net_settlement_amount, settlement_status, created_at, updated_at) VALUES %s",
            settlement_rows
        )
        conn.commit()

        print(f"Inserting {len(settlement_txn_rows):,} settlement transactions...")
        batch_insert(cur,
            "INSERT INTO settlement_transactions (settlement_id, transaction_id, gross_amount, fee_amount, tax_amount, net_amount, created_at) VALUES %s",
            settlement_txn_rows
        )
        conn.commit()

        print("\nDone. All data inserted successfully.")
        print(f"  Payment intents:        {len(intent_rows):,}")
        print(f"  Payment transactions:   {len(transaction_rows):,}")
        print(f"  Payment attempts:       {len(attempt_rows):,}")
        print(f"  Refunds:                {len(refund_rows):,}")
        print(f"  Settlements:            {len(settlement_rows):,}")
        print(f"  Settlement transactions:{len(settlement_txn_rows):,}")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()