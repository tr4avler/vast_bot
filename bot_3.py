import requests
import logging
import time

# Constants
API_KEY_FILE = 'api_key.txt'
CHECK_INTERVAL = 120  # 2 minutes
MAX_ORDERS = 2
SEARCH_CRITERIA = {
    "verified": {},
    "external": {"eq": False},
    "rentable": {"eq": True},
    "gpu_name": {"eq": "RTX 3060"},
    "dph_total": {"lte": 0.052},  
    "cuda_max_good": {"gte": 12},
    "type": "on-demand",
    "intended_status": "running"
}
global IGNORE_MACHINE_IDS
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

def search_gpu(successful_orders_count):
    url = "https://console.vast.ai/api/v0/bundles/"
    headers = {'Accept': 'application/json'}
    response = requests.post(url, headers=headers, json=SEARCH_CRITERIA)
    if response.status_code == 200:
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

def place_order(offer_id):
    url = f"https://console.vast.ai/api/v0/asks/{offer_id}/?api_key={api_key}"
    payload = {
        "client_id": "me",
        "image": "nvidia/cuda:12.0.1-devel-ubuntu20.04",
        "disk": 3,
        "onstart": "sudo apt update && sudo apt -y install wget && sudo wget https://raw.githubusercontent.com/tr4avler/xgpu/main/vast.sh && sudo chmod +x vast.sh && sudo ./vast.sh"
    }
    headers = {'Accept': 'application/json'}
    response = requests.put(url, headers=headers, json=payload)
    return response.json()
    
def monitor_instance_for_running_status(instance_id, machine_id, api_key, timeout=600, interval=60):
    end_time = time.time() + timeout
    while time.time() < end_time:
        url = f"https://console.vast.ai/api/v0/instances/{instance_id}?api_key={api_key}"
        headers = {'Accept': 'application/json'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            status = response.json().get('actual_status', 'unknown')
            if status == "running":
                logging.info(f"Instance {instance_id} is up and running!")
                return
            else:
                logging.info(f"Instance {instance_id} status: {status}. Waiting for next check...")
        else:
            logging.error(f"Error fetching status for instance {instance_id}. Status code: {response.status_code}. Response: {response.text}")
        time.sleep(interval)
    
    logging.warning(f"Instance {instance_id} did not start running in the expected time frame. Destroying this instance.")
    # destroy_instance(instance_id, machine_id, api_key) 

def destroy_instance(instance_id, machine_id, api_key):
    global IGNORE_MACHINE_IDS
    url = f"https://console.vast.ai/api/v0/instances/{instance_id}?api_key={api_key}"
    headers = {'Accept': 'application/json'}
    response = requests.delete(url, headers=headers)
    if response.status_code == 200:
        logging.info(f"Successfully destroyed instance {instance_id}.")
        IGNORE_MACHINE_IDS.append(machine_id)
        logging.info(f"Added machine_id: {machine_id} to the ignore list.")
    else:
        logging.error(f"Failed to destroy instance {instance_id}. Status code: {response.status_code}. Response: {response.text}")

# Test API connection first
test_api_connection()

# Main Loop
successful_orders = 0

# Add a 10-second delay before the first attempt
logging.info("Waiting for 10 seconds before the first attempt to check offers...")
time.sleep(10)

last_check_time = time.time() - CHECK_INTERVAL  # Initialize to ensure first check happens immediately

while successful_orders < MAX_ORDERS:
    current_time = time.time()
    if current_time - last_check_time >= CHECK_INTERVAL:
        offers = search_gpu(successful_orders).get('offers', [])
        if not offers:
            logging.info("No matching offers found. Will check again after the interval.")
        last_check_time = current_time  # Moved this line up so the interval is maintained even if no offers are found.
        for offer in offers:
            machine_id = offer.get('machine_id')
            if machine_id not in IGNORE_MACHINE_IDS:
                response = place_order(offer["id"])
                if response.get('success'):
                    instance_id = response.get('new_contract')
                    if instance_id:
                        logging.info(f"Successfully placed order for machine_id: {machine_id}. Monitoring instance {instance_id} for 'running' status...")
                        monitor_instance_for_running_status(instance_id, machine_id, api_key)
                        successful_orders += 1
                        if successful_orders >= MAX_ORDERS:
                            logging.info("Maximum order limit reached. Exiting...")
                            exit(0)
                    else:
                        logging.error(f"Order was successful but couldn't retrieve 'new_contract' (instance ID) for machine_id: {machine_id}")

    time.sleep(5)

logging.info("Script finished execution.")
