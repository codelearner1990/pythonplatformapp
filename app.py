import os
import yaml
from flask import Flask, render_template, request, redirect, url_for
import ansible_runner
import webbrowser

app = Flask(__name__)

# Function to list all YAML files in the healthchecks folder
def list_healthcheck_files():
    folder = 'healthchecks'
    return [f for f in os.listdir(folder) if f.endswith('.yaml')]

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

# Function to load a YAML file
def load_yaml(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

# Load product, environment, and tag configurations
product_config = load_yaml('config/products.yaml')
environment_config = load_yaml('config/environments.yaml')
tag_config = load_yaml('config/tags.yaml')  # Load tags per product

# Function to run Ansible health check with detailed output capture
def run_ansible_healthcheck(playbook, service_config, tags):
    try:
        runner = ansible_runner.run(
            private_data_dir='healthchecks',
            playbook=playbook,
            extravars=service_config,
            tags=tags
        )
        
        # Capture the detailed output
        result = {
            "status": "success" if runner.status == 'successful' else "fail",
            "stdout": runner.stdout,  # Capture stdout
            "rc": runner.rc,  # Return code
            "details": runner.stats if runner.stats else "No details available"  # Capture stats or details
        }
        
        return result
    except Exception as e:
        return {"status": "fail", "details": str(e)}

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

# Route to display results after running health checks
@app.route('/display_results', methods=['POST'])
def display_results():
    results = request.form.get('results')
    return render_template('results.html', results=results)

# Run health check for selected product and environment
@app.route('/run_check', methods=['POST'])
def run_check():
    selected_product = request.form.get('product')  # Get selected product
    selected_environment = request.form.get('environment')  # Get selected environment (optional)
    selected_playbook = request.form.get('playbook')  # Get selected playbook
    selected_tags = request.form.getlist('tags')  # Get list of selected tags

    # Load the service configuration for the selected product/environment
    service_config = load_service_config(selected_product, selected_environment)
    
    # Convert selected tags to comma-separated string
    tags = ','.join(selected_tags) if selected_tags else None  # Avoid passing empty tags
    
    # Run the Ansible playbook with the selected playbook and tags
    result = run_ansible_healthcheck(selected_playbook, service_config, tags)
    
    # Pass the result to the display_results route
    return render_template('results.html', results=[result])

# Open results in a new tab for all products
@app.route('/run_all_checks')
def run_all_checks():
    webbrowser.open_new_tab(url_for('display_results', _external=True))
    return '', 204  # Empty response as it only triggers a new tab opening

if __name__ == '__main__':
    app.run(debug=True)
