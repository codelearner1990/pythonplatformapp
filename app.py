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



# Function to run Ansible health check with detailed output capture
def run_ansible_healthcheck(playbook, service_config, tags):
    try:
        runner = ansible_runner.run(
            private_data_dir='healthchecks',
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

        # Capture the detailed output
        result = {
            "status": "success" if runner.status == 'successful' else "fail",
            "stdout": stdout_content,  # Properly read and stripped stdout content
            "rc": runner.rc,  # Return code
            "details": runner.stats if runner.stats else "No details available"  # Capture stats or details
        }

        return result
    except Exception as e:
        return {"status": "fail", "details": str(e)}


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
