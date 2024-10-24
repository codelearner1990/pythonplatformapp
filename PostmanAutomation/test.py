import json
import requests

def load_json(file_path):
    """Load JSON data from a file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def make_api_call(api_name):
    """Make an API call based on the request data and headers."""
    
    # Load common headers from headers.json
    headers = load_json('requests/headers.json')
    
    # Map API names to URLs and request body files
    api_config = {
        "samsungEligibility": {
            "url": "https://grws-ws.ihs.discoverfinancial.com/nws/mwp/hce/v2/account/eligibility",
            "method": "POST",
            "body_file": "requests/eligibility_request.json"
        },
        "samsungProvision": {
            "url": "https://grws-ws.ihs.discoverfinancial.com/nws/mwp/hce/v2/account/provision",
            "method": "POST",
            "body_file": "requests/provision_request.json"
        }
    }
    
    if api_name not in api_config:
        raise ValueError(f"API '{api_name}' is not configured.")
    
    # Get the API configuration (URL, method, and body file)
    api = api_config[api_name]
    url = api['url']
    method = api['method']
    body = load_json(api['body_file'])
    
    # Make the API request
    response = requests.request(method, url, headers=headers, json=body)
    
    print(f"Response from {api_name}: {response.status_code}")
    print(response.text)

if __name__ == '__main__':
    # Example: Call samsungEligibility API
    make_api_call("samsungEligibility")
    
    # Example: Call samsungProvision API
    # make_api_call("samsungProvision")
