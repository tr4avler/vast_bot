import requests
import logging
import time

# Constantswww
API_KEY_FILE = 'api_key.txt'
CHECK_INTERVAL = 120  # 2 minutes
BALANCE_LOG_INTERVAL = 300  # 5 minutes
MAX_ORDERS = 2
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
def test_api_connection():
    """Function to test the API connection."""
    test_url = "https://console.vast.ai/api/v0/"
    try:
        response = requests.get(test_url, headers={"Accept": "application/json"})
        if response.status_code == 200:
            logging.info("Connection with API established and working fine.")
        else:
            logging.error(f"Error connecting to API. Status code: {response.status_code}. Response: {response.text}")
    except Exception as e:
        logging.error(f"Error connecting to API: {e}")

def get_user_details():
    url = f"https://console.vast.ai/api/v0/users/current?api_key={api_key}"
    headers = {'Accept': 'application/json'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            return response.json()
        except Exception as e:
            logging.error(f"Failed to parse JSON from user details API response: {e}. Response text: {response.text}")
            return {}
    else:
        logging.error(f"User details API returned an error. Status code: {response.status_code}. Response: {response.text}")
        return {}

def search_gpu():
    url = "https://console.vast.ai/api/v0/bundles/"
    headers = {'Accept': 'application/json'}
    response = requests.post(url, headers=headers, json=SEARCH_CRITERIA)
    if response.status_code == 200:
        price_criteria = SEARCH_CRITERIA.get("price", {}).get("lte")
        logging.info(f"Initial offers check went successfully. Price criteria: ${price_criteria:.3f}")
        try:
            offers = response.json().get('offers', [])
            valid_offers = []
            for offer in offers:
                machine_id = offer.get('machine_id')
                price = offer.get('price', float('inf'))
                if machine_id not in IGNORE_MACHINE_IDS and price <= price_criteria:
                    valid_offers.append(offer)
            return {"offers": valid_offers}
        except Exception as e:
            logging.error(f"Failed to parse JSON from API response during offers check: {e}")
            return {}
    else:
        logging.error(f"Initial offers check failed. Status code: {response.status_code}. Response: {response.text}")
        return {}

def place_order(offer_id):
    url = f"https://console.vast.ai/api/v0/asks/{offer_id}/?api_key={api_key}"
    payload = {
        "client_id": "me",
        "image": "nvidia/cuda:12.0.1-devel-ubuntu20.04",
        "disk": 3
    }
    headers = {'Accept': 'application/json'}
    response = requests.put(url, headers=headers, json=payload)
    return response.json()

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
    for offer in offers:
        machine_id = offer.get('machine_id')
        if machine_id not in IGNORE_MACHINE_IDS:
            response = place_order(offer["id"])
            if response.get('success'):
                logging.info(f"Successfully placed order for machine_id: {machine_id}")
                successful_orders += 1
                if successful_orders >= MAX_ORDERS:
                    logging.info("Maximum order limit reached. Exiting...")
                    exit(0)
            else:
                logging.error(f"Failed to place order for machine_id: {machine_id}. Reason: {response.get('msg')}")

    # Log balance and successful orders count every 5 minutes
    current_time = time.time()
    if current_time - last_balance_log_time >= BALANCE_LOG_INTERVAL:
        # TODO: Consider fetching the balance again for an updated figure
        logging.info(f"Current balance: ${balance:.2f}")
        logging.info(f"Number of successful orders: {successful_orders}")
        last_balance_log_time = current_time

    time.sleep(CHECK_INTERVAL)

logging.info("Script finished execution.")
