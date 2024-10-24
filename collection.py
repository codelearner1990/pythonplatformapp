import json

def postman_to_python(collection_path, output_script):
    # Load the Postman collection JSON
    with open(collection_path, 'r') as f:
        collection = json.load(f)

    # Open the output script file
    with open(output_script, 'w') as out_file:
        # Write import statement for requests library
        out_file.write("import requests\n\n")
        
        # Iterate through each item (API request) in the collection
        for item in collection['item']:
            # Extract the request details
            request_name = item['name'].replace(' ', '_').lower()  # Create a valid function name
            request_data = item['request']
            url = request_data['url']['raw']
            method = request_data['method']
            headers = {header['key']: header['value'] for header in request_data.get('header', [])}
            
            # Write the function definition
            out_file.write(f"def {request_name}():\n")
            out_file.write(f"    url = '{url}'\n")
            out_file.write(f"    method = '{method}'\n")
            
            # Write headers if they exist
            if headers:
                out_file.write(f"    headers = {headers}\n")
            else:
                out_file.write(f"    headers = {{}}\n")
            
            # Write body if it exists
            if 'body' in request_data and 'raw' in request_data['body']:
                body = request_data['body']['raw']
                out_file.write(f"    data = '''{body}'''\n")
            else:
                out_file.write(f"    data = None\n")
            
            # Generate the requests function
            out_file.write(f"    response = requests.request(method, url, headers=headers, data=data)\n")
            out_file.write(f"    print(f'Response from {request_name}: {{response.status_code}}')\n")
            out_file.write(f"    print(response.text)\n\n")
            
    print(f"Python script has been generated at {output_script}")

# Example usage
collection_path = "path/to/your/postman_collection.json"
output_script = "output_generated_script.py"
postman_to_python(collection_path, output_script)
