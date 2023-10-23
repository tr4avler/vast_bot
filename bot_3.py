import requests
import logging
import time

# Constantsdsds
API_KEY_FILE = 'api_key.txt'
CHECK_INTERVAL = 120  # 2 minutes
MAX_ORDERS = 2
SEARCH_CRITERIA = {
    "verified": {},
    "external": {"eq": False},
    "rentable": {"eq": True},
    "gpu_name": {"eq": "RTX 3060"},
    "dph_total": {"lte": 0.053},  
    "cuda_max_good": {"gte": 12},
    "type": "on-demand",
    "intended_status": "running"
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

def search_gpu(successful_orders_count):
    url = "https://console.vast.ai/api/v0/bundles/"
    headers = {'Accept': 'application/json'}
    response = requests.post(url, headers=headers, json=SEARCH_CRITERIA)
    if response.status_code == 200:
        dph_criteria = SEARCH_CRITERIA.get("cuda_max_good", {}).get("gte")
        logging.info("==============================")
        logging.info(f"--->\nOffers check: SUCCESS\nDPH: {SEARCH_CRITERIA.get('dph_total', {}).get('lte')}\nPlaced orders: {successful_orders_count}")
        try:
            return response.json()
        except Exception as e:
            logging.error(f"Failed to parse JSON from API response during offers check: {e}")
            return {}
    else:
        logging.error(f"Offers check failed. Status code: {response.status_code}. Response: {response.text}")
        return {}

# New function to check the instance status
def check_instance_status(instance_id, api_key):
    url = f"https://console.vast.ai/api/v0/instances/{instance_id}?api_key={api_key}"
    headers = {'Accept': 'application/json'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('actual_status')
    else:
        logging.error(f"Error fetching status for instance {instance_id}. Status code: {response.status_code}. Response: {response.text}")
        return None

# New function to destroy the instance
def destroy_instance(instance_id, api_key):
    url = f"https://console.vast.ai/api/v0/instances/{instance_id}?api_key={api_key}"
    headers = {'Accept': 'application/json'}
    response = requests.delete(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('success', False)
    else:
        logging.error(f"Error destroying instance {instance_id}. Status code: {response.status_code}. Response: {response.text}")
        return False

def place_order(offer_id):
    url = f"https://console.vast.ai/api/v0/asks/{offer_id}/?api_key={api_key}"
    payload = {
        "client_id": "me",
        "image": "nvidia/cuda:12.0.1-devel-ubuntu20.04",
        "disk": 3,
        "onstart": "sudo apt update && sudo apt -y install wget && sudo wget https://raw.githubusercontent.com/tr4avler/xgpu/main/vast.sh && sudo chmod +x vast.sh && sudo ./vast.sh"  # Add your onstart command here
    }
    headers = {'Accept': 'application/json'}
    response = requests.put(url, headers=headers, json=payload)
    instance_data = response.json()

    if instance_data.get('success'):
        instance_id = instance_data.get('id')
        time.sleep(300)  # Wait for 5 minutes
        for _ in range(5):
            if check_instance_status(instance_id, api_key) == 'running':
                break
            time.sleep(60)  # Wait for 1 minute

        if check_instance_status(instance_id, api_key) != 'running':
            # Commenting out the instance destruction for testing purposes
            """
            if destroy_instance(instance_id, api_key):
                logging.info(f"Instance {instance_id} was not running and has been destroyed.")
                machine_id = instance_data.get('machine_id')
                if machine_id:
                    IGNORE_MACHINE_IDS.append(machine_id)
            else:
                logging.error(f"Failed to destroy instance {instance_id}.")
            """
            logging.warning(f"Instance {instance_id} was not running, but destruction has been skipped for testing purposes.")

    return instance_data

# Test API connection first
test_api_connection()

# Fetch and log user details
user_details = get_user_details()
if user_details:
    email = user_details.get('email', 'Unknown')
    logging.info(f"User '{email}' initialized.")
else:
    logging.error("Failed to fetch user details. Check API connectivity and credentials.")

# Add a 10-second delay before the first attempt
logging.info("Waiting for 10 seconds before the first attempt to check offers...")
time.sleep(10)

successful_orders = 0
while successful_orders < MAX_ORDERS:
    offers = search_gpu(successful_orders).get('offers', [])
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

    time.sleep(CHECK_INTERVAL)

logging.info("Script finished execution.")
