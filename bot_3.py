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

# Define Functions
# ... [other functions remain unchanged] ...

# Main Loop
last_balance_log_time = time.time()
successful_orders = 0

while successful_orders < MAX_ORDERS:
    offers = search_gpu().get('offers', [])
    for offer in offers:
        machine_id = offer.get('machine_id')
        price = offer.get('price', float('inf'))  # Get the price or use infinity if not present
        if machine_id not in IGNORE_MACHINE_IDS and price <= SEARCH_CRITERIA['price']['lte']:  # Check the price criteria
            response = place_order(offer["id"])
            if response.get('success'):
                logging.info(f"Successfully placed order for machine_id: {machine_id} at a price of ${price:.3f}")
                successful_orders += 1
                if successful_orders >= MAX_ORDERS:
                    logging.info("Maximum order limit reached. Exiting...")
                    exit(0)
            else:
                logging.error(f"Failed to place order for machine_id: {machine_id}. Reason: {response.get('msg')}")

    # Log balance and successful orders count every 5 minutes
    current_time = time.time()
    if current_time - last_balance_log_time >= BALANCE_LOG_INTERVAL:
        logging.info(f"Current balance: ${balance:.2f}")
        logging.info(f"Number of successful orders: {successful_orders}")
        last_balance_log_time = current_time

    time.sleep(CHECK_INTERVAL)

logging.info("Script finished execution.")
