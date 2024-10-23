import os
import yaml
import re
from flask import Flask, render_template, request, redirect, url_for
import ansible_runner
import webbrowser
import fnmatch

app = Flask(__name__)



# Function to list all YAML files in the healthchecks folder
def list_healthcheck_files():
    folder = 'healthchecks'
    return [f for f in os.listdir(folder) if f.endswith('.yaml')]

# Function to strip ANSI codes
def strip_ansi_codes(text):
    ansi_escape = re.compile(r'(?:\x1B[@-_][0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


import re

def run_ansible_healthcheck(playbook, service_config, tags):
    try:
        runner = ansible_runner.run(
            private_data_dir='.',
            playbook=playbook,
            extravars=service_config,
            tags=tags
        )

        # Read the stdout file to capture output
        stdout_content = ""
        if runner.stdout:
            with open(runner.stdout.name, 'r') as f:
                stdout_content = f.read()

        # Strip ANSI codes from the stdout
        stdout_content = strip_ansi_codes(stdout_content)

        # Parse stdout to extract required information
        services_results = []
        current_service = ""
        failure_reason = ""
        current_url_name = "N/A"
        current_url = "N/A"
        status = "ok"

        for line in stdout_content.splitlines():
            # Capture the service task
            if line.startswith("TASK ["):
                current_service = line.split('[')[1].split(']')[0].strip()  # Extract the task name (service)
                current_url_name = "N/A"
                current_url = "N/A"
                failure_reason = ""  # Reset failure reason for each task

            # Handle both success (ok) and failure (failed) statuses
            if "ok:" in line or "failed:" in line:
                task_parts = line.split("=>")
                if len(task_parts) > 1:
                    try:
                        task_info_str = task_parts[1].strip()

                        # Use regex to extract 'key' (URL name) and 'value' (URL)
                        key_match = re.search(r"'key':\s*'([^']*)'", task_info_str)
                        value_match = re.search(r"'value':\s*'([^']*)'", task_info_str)

                        # Update for both success and failure
                        if "ok:" in line:
                            current_url_name = key_match.group(1) if key_match else "N/A"
                            current_url = value_match.group(1) if value_match else "N/A"
                            status = "ok"
                        # For failed ones, capture URL from a fallback method if regex doesn't find it
                        elif "failed:" in line:
                            status = "failed"
                            failure_reason = extract_failure_reason(stdout_content, line)

                            # Fallback logic to extract URL name and URL in failure case
                            current_url_name = key_match.group(1) if key_match else "N/A"  # URL name might still be present
                            current_url = value_match.group(1) if value_match else find_failed_url(line)

                            # DEBUG: Print the failure reason and the full failed output for inspection
                            print("DEBUG: Failed Output\n", line)
                            print("DEBUG: Full Failure Reason\n", failure_reason)
                            
                    except Exception as ex:
                        failure_reason = "Parsing Error: Unable to extract URL info"

                    # Append the results for both successful and failed cases
                    services_results.append({
                        "service": current_service,
                        "url_name": current_url_name,
                        "url": current_url,
                        "status": status,
                        "failure_reason": failure_reason if status == "failed" else "N/A"  # Only add failure reason if failed
                    })

        # Debugging output to print what services_results contains
        print(f"Service results: {services_results}")

        # Capture the detailed output
        result = {
            "status": "success" if runner.status == 'successful' else "fail",
            "stdout": services_results,  # Pass the structured service results
            "rc": runner.rc,  # Return code
            "details": runner.stats if runner.stats else "No details available"  # Capture stats or details
        }

        return result
    except Exception as e:
        return {"status": "fail", "details": str(e)}

def extract_failure_reason(stdout_content, failed_line):
    """Extract a meaningful failure reason from the stdout content after a failed task."""
    failure_reason_lines = []
    capture = False
    for line in stdout_content.splitlines():
        if line == failed_line:
            capture = True  # Start capturing failure reason lines after the failed task line
        elif capture:
            if line.startswith("TASK [") or line.startswith("ok:") or line.startswith("failed:"):
                break  # Stop capturing if a new task starts
            failure_reason_lines.append(line.strip())  # Add failure reason lines

    # Join the captured lines into a single failure reason message
    return " ".join(failure_reason_lines).strip() if failure_reason_lines else "Failed for unknown reason"

def find_failed_url(line):
    """Fallback function to find URL in failed cases."""
    # Here we attempt to match a URL pattern in the failure line
    url_match = re.search(r'(https?://[^\s]+)', line)
    return url_match.group(1) if url_match else "N/A"




# Function to load a YAML file
def load_yaml(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

# Load product, environment, and tag configurations
product_config = load_yaml('config/products.yaml')
environment_config = load_yaml('config/environments.yaml')
tag_config = load_yaml('config/tags.yaml')  # Load tags per product

# Function to load all YAML files for a product
def load_service_config(product, environment=None):
    product_path = f'env/{product}/'
    
    # Dictionary to hold combined service/environment configurations
    combined_data = {}
    
    # Iterate over all YAML files in the product's directory
    if os.path.exists(product_path):
        for file in os.listdir(product_path):
            if file.endswith('.yaml'):
                file_path = os.path.join(product_path, file)
                service_data = load_yaml(file_path)
                
                # If the product has environment-based files, only load the selected environment
                if environment:
                    combined_data.update(service_data.get(environment, {}))
                else:
                    combined_data.update(service_data)
                    
    return combined_data


# Main page
@app.route('/')
def index():
    return render_template('index.html')

# Healthcheck page with dynamic product and environment loading
@app.route('/healthcheck')
def healthcheck():
    products = product_config['products']
    environments = environment_config['environments']
    healthcheck_files = list_healthcheck_files()  # List all available health check files
    return render_template('healthcheck.html', products=products, environments=environments, healthcheck_files=healthcheck_files, tag_config=tag_config)

@app.route('/get_tags')
def get_tags():
    selected_product = request.args.get('product')
    tags= tag_config.get(selected_product, [])
    return {"tags": tags}

# Route to display results after running health checks
@app.route('/display_results', methods=['POST'])
def display_results():
    results = request.form.get('results')
    return render_template('results.html', results=results)

@app.route('/run_check', methods=['POST'])
def run_check():
    selected_product = request.form.get('product')  # Get selected product
    selected_environment = request.form.get('environment')  # Get selected environment (optional)
    selected_tags = request.form.getlist('tags')

    # Get the correct healthcheck playbook for the product
    selected_playbook = get_healthcheck_playbook(selected_product)

    if not selected_playbook:
        return render_template('results.html', results=[{
            "status": "fail",
            "details": f"ERROR: the playbook for product {selected_product} could not be found",
            "stdout": "",
            "rc": 1
        }])

    # Load the service configuration for the selected product/environment
    service_config = load_service_config(selected_product, selected_environment)
    
    # Convert selected tags to comma-separated string
    tags = ','.join(selected_tags)
    
    # Run the Ansible playbook with the service configuration
    result = run_ansible_healthcheck(selected_playbook, service_config, tags)
    
    # After running the check, redirect to results page
    return render_template('results.html', results=[result])

# Open results in a new tab for all products
@app.route('/run_all_checks')
def run_all_checks():
    webbrowser.open_new_tab(url_for('display_results', _external=True))
    return '', 204  # Empty response as it only triggers a new tab opening

if __name__ == '__main__':
    app.run(debug=True)
