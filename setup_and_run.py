#!/usr/bin/env python3
import os
import subprocess
import sys
import time
import json
import signal
import atexit
import platform
import requests

# Set unbuffered output to ensure responses are displayed immediately
os.environ['PYTHONUNBUFFERED'] = '1'

# Current directory - this should work in both the parent workspace and the submodule
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Global variables to track running processes
processes = []

def test_ollama_connection(retries=3, delay=2):
    """Test if Ollama is running and accessible"""
    print("Testing Ollama connectivity...")
    url = "http://localhost:11434/api/tags"
    
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print("✅ Ollama is running and accessible")
                return True
            else:
                print(f"⚠️ Ollama returned status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Connection attempt {attempt+1}/{retries} failed: {str(e)}")
        
        if attempt < retries - 1:
            print(f"Waiting {delay} seconds before retrying...")
            time.sleep(delay)
    
    print("❌ Ollama is not accessible. Make sure the Ollama service is running.")
    return False

def read_mcp_config():
    """Read the MCP configuration from the mcp.json file"""
    config_path = os.path.join(CURRENT_DIR, 'mcp.json')
    if not os.path.exists(config_path):
        config_path = os.path.join(CURRENT_DIR, '.vscode', 'settings.json')
    
    if not os.path.exists(config_path):
        print(f"Error: Could not find MCP configuration file at {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        if config_path.endswith('settings.json'):
            # Extract MCP configuration from VS Code settings
            return json.load(f).get('mcp', {})
        else:
            # Direct MCP configuration
            return json.load(f)

def create_docker_network():
    """Create the Docker network if it doesn't exist"""
    network_name = "mcp-network-aipm"
    
    # Check if the network already exists
    result = subprocess.run(
        ["docker", "network", "ls", "--filter", f"name={network_name}", "--format", "{{.Name}}"],
        capture_output=True, text=True
    )
    
    if network_name not in result.stdout:
        print(f"Creating Docker network: {network_name}")
        subprocess.run(["docker", "network", "create", network_name], check=True)
    else:
        print(f"Docker network {network_name} already exists")

def stop_existing_containers():
    """Stop and remove existing MCP containers"""
    containers = ["mcp-filesystem-aipm", "mcp-context7-aipm", "mcp-atlassian-aipm"]
    
    for container in containers:
        # Check if container exists and stop it
        subprocess.run(
            ["docker", "stop", container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Remove container if it exists
        subprocess.run(
            ["docker", "rm", container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    
    print("Cleaned up any existing MCP containers")

def resolve_path(path):
    """Resolve path placeholders like ${workspaceFolder}"""
    if "${workspaceFolder}" in path:
        return path.replace("${workspaceFolder}", CURRENT_DIR)
    return path

def start_container_process(server_name, config):
    """Start a Docker container based on configuration"""
    if server_name not in ['filesystem', 'context7', 'atlassian']:
        return None  # Skip non-Docker servers
    
    command = config.get('command')
    args = config.get('args', [])
    env = config.get('env', {})
    
    # Resolve paths in args
    resolved_args = [resolve_path(arg) for arg in args]
    
    # Combine command and args
    full_command = [command] + resolved_args
    
    # Setup environment variables
    env_vars = os.environ.copy()
    env_vars.update(env)
    
    print(f"Starting {server_name} server...")
    process = subprocess.Popen(
        full_command,
        env=env_vars,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    return process

def start_stdio_process(server_name, config):
    """Start a stdio-based server process"""
    command = config.get('command')
    args = config.get('args', [])
    env = config.get('env', {})
    
    # Combine command and args
    full_command = [command] + args
    
    # Setup environment variables
    env_vars = os.environ.copy()
    env_vars.update(env)
    
    print(f"Starting {server_name} server...")
    process = subprocess.Popen(
        full_command,
        env=env_vars,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    return process

def cleanup():
    """Terminate all running processes"""
    print("Cleaning up and shutting down servers...")
    
    # Terminate all processes
    for process in processes:
        try:
            if platform.system() != "Windows":
                # On Unix/Linux, use SIGTERM
                process.terminate()
            else:
                # On Windows
                process.kill()
        except:
            pass
    
    # Stop Docker containers
    containers = ["mcp-filesystem-aipm", "mcp-context7-aipm", "mcp-atlassian-aipm"]
    for container in containers:
        try:
            subprocess.run(["docker", "stop", container], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL)
        except:
            pass

def signal_handler(sig, frame):
    """Handle interrupt signals"""
    print("\nInterrupt received, shutting down...")
    cleanup()
    sys.exit(0)

def main():
    print("Setting up AI Project Management System...")
    
    # Register cleanup functions
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Test Ollama connectivity
        if not test_ollama_connection():
            print("Exiting due to Ollama connectivity issues.")
            sys.exit(1)
        
        # Create Docker network
        create_docker_network()
        
        # Stop any existing MCP containers
        stop_existing_containers()
        
        # Read MCP configuration
        mcp_config = read_mcp_config()
        servers_config = mcp_config.get('servers', {})
        
        # Start Docker container processes
        for server_name, config in servers_config.items():
            if config.get('command') == 'docker':
                process = start_container_process(server_name, config)
                if process:
                    processes.append(process)
        
        print("Docker containers started. Waiting 3 seconds before starting stdio servers...")
        time.sleep(3)  # Give Docker containers time to initialize
        
        # Start stdio-based processes
        for server_name, config in servers_config.items():
            if config.get('type') == 'stdio':
                process = start_stdio_process(server_name, config)
                if process:
                    processes.append(process)
        
        print("All MCP servers started. Waiting 5 seconds before starting main application...")
        time.sleep(5)  # Wait for all servers to be ready
        
        # Run the main application
        main_py_path = os.path.join(CURRENT_DIR, 'src', 'main.py')
        if not os.path.exists(main_py_path):
            print(f"Warning: main.py not found at {main_py_path}")
            print("MCP servers are running. Press Ctrl+C to exit.")
            while True:
                time.sleep(1)
        else:
            print(f"Starting main application: {main_py_path}")
            main_process = subprocess.Popen(
                [sys.executable, main_py_path],
                stdout=sys.stdout,
                stderr=sys.stderr
            )
            processes.append(main_process)
            
            # Wait for the main process to complete
            main_process.wait()
    
    except KeyboardInterrupt:
        print("\nInterrupt received, shutting down...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
