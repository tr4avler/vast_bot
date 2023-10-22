import requests
import logging
import time
from datetime import datetime

# Configure the logging
logging.basicConfig(filename='vast_ai_script.log', level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

# Read the API key from a file
api_key_file = 'api_key.txt'

try:
    with open(api_key_file, 'r') as file:
        api_key = file.read().strip()
except FileNotFoundError:
    logging.error(f"API key file '{api_key_file}' not found.")
    exit(1)
except Exception as e:
    logging.error(f"Error reading API key: {e}")
    exit(1)

# Define your conditions
desired_gpu_name = 'RTX_3060'
desired_verified = 'any'  # Any value (including True and other non-False values) for the 'verified' field
desired_max_dph = 0.045  # Maximum DPH desired
desired_min_cuda_version = 12  # Minimum CUDA version desired

# Define the image and disk size you want for the instance
desired_image = 'nvidia/cuda:12.0.1-devel-ubuntu20.04'
desired_disk_size = 3

# Define the balance check interval (in seconds)
balance_check_interval = 3600  # Set to check every hour

# Define the interval for checking offers (in seconds)
check_offers_interval = 300  # Set to check every 5 minutes

# List of machine IDs to ignore
ignore_machine_ids = [123, 456, 789]

# Define the maximum number of successful orders before stopping the script
max_successful_orders = 5  # Set to 5 for example

successful_orders = 0

while successful_orders < max_successful_orders:
    try:
        # Make a request to the Vast.ai API to get your account balance
        balance_response = requests.get('https://console.vast.ai/api/v0/user', headers={'Authorization': f'Bearer {api_key}'})
        if balance_response.status_code == 200:
            balance_data = balance_response.json()
            balance = balance_data.get('balance', 'N/A')
            logging.info(f'Account Balance: {balance} VST')

        # Make a request to the Vast.ai API to search for offers
        query = f"gpu_name={desired_gpu_name} verified={desired_verified} dph <= {desired_max_dph} type.cudaver >= {desired_min_cuda_version}"
        response = requests.get(f'https://console.vast.ai/api/v0/searchoffers?q={query}')
        
        if response.status_code == 200:
            offers = response.json()

            for offer in offers:
                # Check if the offer meets your conditions
                gpu_name = offer['type']['gpu_name']
                verified = offer['type']['verified']
                dph = offer['dph']
                machine_id = offer['id']

                if (
                    gpu_name == desired_gpu_name and 
                    (desired_verified == 'any' or verified) and  # Updated condition for 'verified'
                    dph <= desired_max_dph and 
                    machine_id not in ignore_machine_ids
                ):
                    # If conditions are met and the machine ID is not in the ignore list, place an order
                    order_data = {
                        'api_key': api_key,
                        'id': machine_id,
                        'count': 1
                    }
                    response = requests.post('https://console.vast.ai/api/v0/order', data=order_data)

                    if response.status_code == 200:
                        logging.info('Order placed successfully!')

                        # Create an instance based on the order
                        instance_data = {
                            'api_key': api_key,
                            'order_id': response.json()['id'],
                            'image': desired_image,
                            'disk': desired_disk_size
                        }
                        response = requests.post('https://console.vast.ai/api/v0/createinstance', data=instance_data)

                        if response.status_code == 200:
                            logging.info('Instance created successfully!')
                            successful_orders += 1
                            logging.info(f'Successful Orders: {successful_orders}/{max_successful_orders}')
                        else:
                            logging.error('Failed to create an instance:', response.status_code)
                    else:
                        logging.error('Failed to place an order:', response.status_code)
        
        if successful_orders >= max_successful_orders:
            logging.info(f'Stopping script after {max_successful_orders} successful orders.')
            break

        # Sleep for a while before checking offers and balance again
        time.sleep(check_offers_interval)
    except Exception as e:
        logging.error('An error occurred: ' + str(e))
