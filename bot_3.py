import requests
import logging
import time

# Constants
API_KEY_FILE = 'api_key.txt'
CHECK_INTERVAL = 120  # 2 minutes
BALANCE_LOG_INTERVAL = 300  # 5 minutes
MAX_ORDERS = 4
SEARCH_CRITERIA = {
    "verified": {},
    "external": {"eq": False},
    "rentable": {"eq": True},
    "gpu_name": {"eq": "RTX 3060"},
    "price": {"lte": 0.055},
    "cuda_max_good": {"gte": 12},
    "type": "on-demand"
}
IGNORE_MACHINE_IDS = []

# Logging Configuration
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("script_output.log"),
                              logging.StreamHandler()])

# Load API Key
try:
    with open(API_KEY_FILE, 'r') as file:
        api_key = file.read().strip()
except FileNotFoundError:
    logging.error(f"API key file '{API_KEY_FILE}' not found.")
    exit(1)
except Exception as e:
    logging.error(f"Error reading API key: {e}")
    exit(1)

# ... [Function definitions remain the same]

# Test API connection first
test_api_connection()

# Fetch and log user details
user_details = get_user_details()
if user_details:
    email = user_details.get('email', 'Unknown')
    balance = user_details.get('balance', '0.00')
    logging.info(f"User '{email}' initialized with a balance of ${balance:.2f}")
else:
    logging.error("Failed to fetch user details. Check API connectivity and credentials.")

# Main Loop
last_balance_log_time = time.time()
successful_orders = 0

while successful_orders < MAX_ORDERS:
    offers = search_gpu().get('offers', [])
    invalid_offers_count = 0
    for offer in offers:
        machine_id = offer.get('machine_id')
        price = offer.get('price', float('inf'))
        if machine_id not in IGNORE_MACHINE_IDS and price <= SEARCH_CRITERIA['price']['lte']:
            response = place_order(offer["id"])
            if response.get('success'):
                logging.info(f"Successfully placed order for machine_id: {machine_id} at price: ${price:.2f}")
                successful_orders += 1
                if successful_orders >= MAX_ORDERS:
                    logging.info("Maximum order limit reached. Exiting...")
                    exit(0)
            else:
                logging.error(f"Failed to place order for machine_id: {machine_id}. Reason: {response.get('msg')}")
        else:
            invalid_offers_count += 1

    if invalid_offers_count:
        logging.info(f"There were {invalid_offers_count} offers that did not meet the criteria.")

    # Log balance and successful orders count every 5 minutes
    current_time = time.time()
    if current_time - last_balance_log_time >= BALANCE_LOG_INTERVAL:
        # TODO: Consider fetching the balance again for an updated figure
        logging.info(f"Current balance: ${balance:.2f}")
        logging.info(f"Number of successful orders: {successful_orders}")
        last_balance_log_time = current_time

    time.sleep(CHECK_INTERVAL)

logging.info("Script finished execution.")
