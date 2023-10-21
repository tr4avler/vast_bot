import requests
import time
import logging
import threading
import subprocess  # Import the subprocess module

# Define the number of orders to fulfill for RTX 3060 and RTX 3090 separately
orders_to_fulfill_rtx_3060 = 2  # Change this to the desired number for RTX 3060
orders_to_fulfill_rtx_3090 = 1  # Change this to the desired number for RTX 3090

# Define the machine IDs to ignore
ignore_machine_ids = [6911366, 6911362]  # Add the machine IDs you want to ignore

# Define the log file
log_file = 'vast_ai_orders.log'

# Configure logging to the 'vast_ai_orders.log' file
logging.basicConfig(
    filename='vast_ai_orders.log',  # Use 'vast_ai_orders.log' as the log file
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Specify the API key file
api_key_file = 'api_key.txt'  # The file containing your API key

# Read the API key from the file
try:
    with open(api_key_file, 'r') as file:
        api_key = file.read().strip()
except FileNotFoundError:
    print(f"API key file '{api_key_file}' not found.")
    exit(1)
except Exception as e:
    print(f"Error reading API key: {e}")
    exit(1)

# Define the maximum price for RTX 3060 listings
max_price_rtx_3060 = 0.045  # Set your desired maximum price for RTX 3060 here

# Define the maximum price for RTX 3090 listings
max_price_rtx_3090 = 0.09  # Set your desired maximum price for RTX 3090 here

# Define the API endpoints
base_url = 'https://console.vast.ai/api/v0'
balance_endpoint = '/balance'
listing_endpoint = '/listings'
order_endpoint = '/order'

# Function to get your Vast.ai balance
def get_balance(api_key):
    url = base_url + balance_endpoint
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        return None

# Function to list available GPU listings with filters and ignoring specific machine IDs
def get_listings(api_key, ignore_ids, gpu_name, max_price):
    url = base_url + listing_endpoint
    headers = {
        'Authorization': f'Bearer {api_key}'
    }

    # Add filters to the query parameters
    params = {
        'name': gpu_name,
        'min_cuda_version': 12,
        'price_usd_hourly_max': max_price
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        listings = response.json()

        # Filter out listings with ignored machine IDs
        filtered_listings = [listing for listing in listings if listing['machine_id'] not in ignore_ids]
        return filtered_listings
    else:
        return None

# Function to place an order for a GPU listing
def place_order(api_key, listing_id):
    url = base_url + order_endpoint
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    data = {
        'listing_id': listing_id
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        order_data = response.json()
        return order_data
    else:
        return None

# Function to log order placement with a highlight
def log_highlighted_order_placement(logger, message):
    logger.info(f'*** ORDER PLACED: {message} ***')

# Function to periodically log your balance
def log_balance_periodically(api_key):
    while True:
        balance = get_balance(api_key)
        logging.info(f'Your Vast.ai balance: {balance}')
        time.sleep(300)  # Log balance every 5 minutes

# Start the balance logging thread
balance_thread = threading.Thread(target=log_balance_periodically, args=(api_key,))
balance_thread.daemon = True
balance_thread.start()

# Example usage
if __name__ == '__main__':
    # Keep trying to place orders for RTX 3060 and RTX 3090 separately
    orders_fulfilled_rtx_3060 = 0
    orders_fulfilled_rtx_3090 = 0
    
    while orders_fulfilled_rtx_3060 < orders_to_fulfill_rtx_3060 or orders_fulfilled_rtx_3090 < orders_to_fulfill_rtx_3090:
        # Check for RTX 3060 orders
        if orders_fulfilled_rtx_3060 < orders_to_fulfill_rtx_3060:
            listings_rtx_3060 = get_listings(api_key, ignore_machine_ids, 'RTX 3060', max_price_rtx_3060)
            if listings_rtx_3060:
                listing_id = listings_rtx_3060[0]['id']  # Choose the first listing (or a suitable one)
                order_data = place_order(api_key, listing_id)
                if order_data:
                    log_highlighted_order_placement(logging, f'Order placed for RTX 3060: {order_data}')
                    orders_fulfilled_rtx_3060 += 1
                    instance_id = order_data.get('instance_id', '')

                    if instance_id:
                        subprocess.run(['bash', 'create_instance.sh', instance_id])

        # Check for RTX 3090 orders
        if orders_fulfilled_rtx_3090 < orders_to_fulfill_rtx_3090:
            listings_rtx_3090 = get_listings(api_key, ignore_machine_ids, 'RTX 3090', max_price_rtx_3090)
            if listings_rtx_3090:
                listing_id = listings_rtx_3090[0]['id']  # Choose the first listing (or a suitable one)
                order_data = place_order(api_key, listing_id)
                if order_data:
                    log_highlighted_order_placement(logging, f'Order placed for RTX 3090: {order_data}')
                    orders_fulfilled_rtx_3090 += 1
                    instance_id = order_data.get('instance_id', '')

                    if instance_id:
                        subprocess.run(['bash', 'create_instance.sh', instance_id])
