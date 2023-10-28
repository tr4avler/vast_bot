import requests
import logging
import time
import threading

# Constants
API_KEY_FILE = 'api_key.txt'
CHECK_INTERVAL = 60  # in seconds
MAX_ORDERS = 6
GPU_DPH_RATES = {
    "RTX 3060": 0.042,
    "RTX 3080 Ti": 0.056,
    "RTX 3090": 0.083,
    "RTX 3090 Ti": 0.095,
    "RTX 4070": 0.055,
    "RTX 4080": 0.08,
    "RTX 4090": 0.115,
    "RTX A2000": 0.03,
    "RTX A4000": 0.048,
    "RTX A5000": 0.074,
    "RTX A6000": 0.089,
    "RTX A10": 0.059,
    "RTX A40": 0.08,
    "GTX 1080 Ti": 0.025,
    "RTX 2080 Ti": 0.044,
    "Q RTX 4000": 0.035,
    "Q RTX 8000": 0.1,
}
SEARCH_CRITERIA = {
    "verified": {},
    "external": {"eq": False},
    "rentable": {"eq": True},
    "gpu_name": {"in": list(GPU_DPH_RATES.keys())}, 
    "cuda_max_good": {"gte": 12},
    "type": "on-demand",
    "intended_status": "running"
}
destroyed_instances_count = 0
global IGNORE_MACHINE_IDS
IGNORE_MACHINE_IDS = []
successful_orders = 0

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

def search_gpu(successful_orders):
    url = "https://console.vast.ai/api/v0/bundles/"
    headers = {'Accept': 'application/json'}
    response = requests.post(url, headers=headers, json=SEARCH_CRITERIA)
    if response.status_code == 200:
        logging.info(f"\nOffers check: SUCCESS\nPlaced orders: {successful_orders}/{MAX_ORDERS}\nDestroyed instances: {destroyed_instances_count}\nIgnored machine IDs: {IGNORE_MACHINE_IDS}")
        logging.info("GPU DPH Rates:")
        for gpu_model, dph_rate in GPU_DPH_RATES.items():
            logging.info(f"{gpu_model}: {dph_rate}/hour")
        try:
            offers = response.json().get('offers', [])
            # Filter offers based on DPH rates
            filtered_offers = [offer for offer in offers if offer.get('gpu_name') in GPU_DPH_RATES and offer.get('dph_total') <= GPU_DPH_RATES[offer.get('gpu_name')]]
            if filtered_offers:
                for offer in filtered_offers:
                    gpu_model = offer.get('gpu_name')
                    logging.info(f"Found matching offer for {gpu_model}.")
            else:
                logging.info("No matching offers found based on DPH rates.")
            return {"offers": filtered_offers}
        except Exception as e:
            logging.error(f"Failed to parse JSON from API response during offers check: {e}")
            return {}
    else:
        logging.error(f"Offers check failed. Status code: {response.status_code}. Response: {response.text}")
        return {}

def place_order(offer_id):
    # Step 1: Retrieve the offer details again
    url_get_offer = f"https://console.vast.ai/api/v0/bundles/{offer_id}/?api_key={api_key}"
    headers = {'Accept': 'application/json'}
    response_get_offer = requests.get(url_get_offer, headers=headers)
    
    if response_get_offer.status_code == 200:
        offer_details = response_get_offer.json()
        gpu_model = offer_details.get('gpu_name')
        dph_total = offer_details.get('dph_total')
        
        # Step 2: Check the DPH value
        if gpu_model in GPU_DPH_RATES and dph_total <= GPU_DPH_RATES[gpu_model]:
            logging.info(f"Double verification successful for {gpu_model}. Placing order...")
            
            # Step 3: Proceed with placing the order
            url_place_order = f"https://console.vast.ai/api/v0/asks/{offer_id}/?api_key={api_key}"
            payload = {
                "client_id": "me",
                "image": "nvidia/cuda:12.0.1-devel-ubuntu20.04",
                "disk": 4,
                "onstart": "sudo apt update && sudo apt -y install wget && sudo wget https://raw.githubusercontent.com/tr4avler/xgpu/main/vast.sh && sudo chmod +x vast.sh && sudo ./vast.sh && sudo tail -f /root/XENGPUMiner/miner.log"
            }
            response_place_order = requests.put(url_place_order, headers=headers, json=payload)
            return response_place_order.json()
        else:
            logging.warning(f"Double verification failed for {gpu_model}. DPH has changed to {dph_total}. Order will not be placed.")
            return {"success": False, "message": "DPH verification failed"}
    else:
        logging.error(f"Failed to retrieve offer details for double verification. Status code: {response_get_offer.status_code}. Response: {response_get_offer.text}")
        return {"success": False, "message": "Failed to retrieve offer details"}

    
def monitor_instance_for_running_status(instance_id, machine_id, api_key, timeout=420, interval=30):
    end_time = time.time() + timeout
    instance_running = False  # Add a flag to check if instance is running
    gpu_utilization_met = False  # Flag to check if GPU utilization is 90% or more
    check_counter = 0  # Initialize the interval check counter
    max_checks = timeout // interval  # Calculate maximum number of interval checks
    while time.time() < end_time:
        url = f"https://console.vast.ai/api/v0/instances/{instance_id}?api_key={api_key}"
        headers = {'Accept': 'application/json'}
        response = requests.get(url, headers=headers)
        check_counter += 1  # Increment the interval check counter
        if response.status_code == 200:
            instance_data = response.json()["instances"]
            status = instance_data.get('actual_status', 'unknown')
            gpu_utilization = instance_data.get('gpu_util', 0)  # Get GPU utilization, default to unknown if not present
       
            if status == "running":
                if gpu_utilization is not None and gpu_utilization >= 90:
                    logging.info(f"Check #{check_counter}/{max_checks}: Instance {instance_id} is up and running with GPU utilization at {gpu_utilization}%!")
                    instance_running = True
                    gpu_utilization_met = True
                    break
                else:
                    logging.info(f"Check #{check_counter}/{max_checks}: Instance {instance_id} is up and running but GPU utilization is {gpu_utilization}%. Waiting for next check...")
            else:
                logging.info(f"Check #{check_counter}/{max_checks}: Instance {instance_id} status: {status}. Waiting for next check...")
        else:
            logging.error(f"Check #{check_counter}/{max_checks}: Error fetching status for instance {instance_id}. Status code: {response.status_code}. Response: {response.text}")

        time.sleep(interval)

    # Only destroy the instance if it didn't start running or GPU utilization is less than 90%
    if not instance_running or not gpu_utilization_met:  
        logging.warning(f"Instance {instance_id} did not meet the required conditions after {check_counter} checks. Destroying this instance.")
        if destroy_instance(instance_id, machine_id, api_key):
            return False  # Indicate that the instance was destroyed

    return instance_running and gpu_utilization_met  # Return the status of the instance

def destroy_instance(instance_id, machine_id, api_key):
    global IGNORE_MACHINE_IDS, destroyed_instances_count
    url = f"https://console.vast.ai/api/v0/instances/{instance_id}/?api_key={api_key}"
    headers = {'Accept': 'application/json'}
  
    try:
        response = requests.delete(url, headers=headers)
        response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code

        if response.json().get('success') == True:
            logging.info(f"Successfully destroyed instance {instance_id}.")
            IGNORE_MACHINE_IDS.append(machine_id)
            logging.info(f"Added machine_id: {machine_id} to the ignore list.")
            destroyed_instances_count += 1  # Increment the counter
            return True
        else:
            logging.error(f"Failed to destroy instance {instance_id}. API did not return a success status. Response: {response.text}")
            return False

    except requests.HTTPError as e:
        logging.error(f"HTTP error occurred while trying to destroy instance {instance_id}: {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred while trying to destroy instance {instance_id}: {e}")
        return False

def handle_instance(instance_id, machine_id, api_key, lock):
    global successful_orders
    instance_success = monitor_instance_for_running_status(instance_id, machine_id, api_key)
    if instance_success:
        with lock:  # This acquires the lock and releases it when the block is exited
            successful_orders += 1
            logging.info(f"Successful orders count: {successful_orders}")
            if successful_orders >= MAX_ORDERS:
                logging.info("Maximum order limit reached. Exiting...")

# Test API connection first
test_api_connection()

# Main Loop
successful_orders_lock = threading.Lock()

# Add a 10-second delay before the first attempt
logging.info("Waiting for 10 seconds before the first attempt to check offers...")
time.sleep(10)

last_check_time = time.time() - CHECK_INTERVAL  # Initialize to ensure first check happens immediately

threads = []

while successful_orders < MAX_ORDERS:
    current_time = time.time()
    if current_time - last_check_time >= CHECK_INTERVAL:
        offers = search_gpu(successful_orders).get('offers', [])      
        last_check_time = current_time  # Reset the last check time
        for offer in offers:
            machine_id = offer.get('machine_id')
            gpu_model = offer.get('gpu_name')
            if machine_id not in IGNORE_MACHINE_IDS:
                response = place_order(offer["id"])
                if response.get('success'):
                    instance_id = response.get('new_contract')
                    if instance_id:
                        logging.info(f"Successfully placed order for {gpu_model} with machine_id: {machine_id} at {offer.get('dph_total')} DPH. Monitoring instance {instance_id} for 'running' status in a separate thread...")
                        thread = threading.Thread(target=handle_instance, args=(instance_id, machine_id, api_key, successful_orders_lock))
                        thread.start()  # Start the thread
                        threads.append(thread)
                    else:
                        logging.error(f"Order was successful but couldn't retrieve 'new_contract' (instance ID) for machine_id: {machine_id}")
                else:
                    logging.error(f"Failed to place order for offer ID {offer['id']} for machine_id: {machine_id}.")
            else:
                logging.info(f"Skipping machine ID {machine_id} as it is in the ignore list.")                        
    time.sleep(5)

for thread in threads:
    thread.join()  # Wait for thread to finish

logging.info("Script finished execution.")
