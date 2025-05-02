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

# Force tinyllama model for memory compatibility
os.environ['OLLAMA_MODEL'] = 'tinyllama'

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
    try:
        with open(os.path.join(CURRENT_DIR, 'mcp.json'), 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading MCP config: {e}")
        return {}

def create_docker_network():
    """Create the Docker network if it doesn't exist"""
    try:
        subprocess.run(
            ["docker", "network", "create", "mcp-network-aipm"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("Created Docker network: mcp-network-aipm")
    except subprocess.CalledProcessError:
        # Network might already exist, which is fine
        pass

def stop_existing_containers():
    """Stop and remove existing MCP containers"""
    containers = ["mcp-filesystem-aipm", "mcp-context7-aipm", "mcp-atlassian-aipm"]
    
    for container in containers:
        try:
            subprocess.run(["docker", "stop", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["docker", "rm", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            pass
    
    print("Cleaned up any existing MCP containers")

def build_atlassian_server():
    """Build the Atlassian MCP server Docker image"""
    try:
        print("Building Atlassian MCP server...")
        subprocess.run(
            [
                "docker", "build",
                "-t", "mcp/atlassian",
                "-f", os.path.join(CURRENT_DIR, "src/mcp_servers/Dockerfile.atlassian"),
                os.path.join(CURRENT_DIR, "src/mcp_servers")
            ],
            check=True
        )
        print("✅ Built Atlassian MCP server")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to build Atlassian MCP server: {e}")
        return False

def start_container_process(server_name, config):
    """Start a Docker container based on configuration"""
    if server_name not in ['filesystem', 'context7', 'atlassian']:
        return None
    
    # Build Atlassian server if needed
    if server_name == 'atlassian' and not build_atlassian_server():
        return None
    
    command = config.get('command')
    args = config.get('args', [])
    env = config.get('env', {})
    
    # Set up environment variables
    env_vars = os.environ.copy()
    env_vars.update(env)
    env_vars['OLLAMA_MODEL'] = 'tinyllama'  # Force tinyllama model
    
    print(f"Starting {server_name} server...")
    try:
        process = subprocess.Popen(
            [command] + args,
            env=env_vars,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"✅ Started {server_name} server")
        return process
    except Exception as e:
        print(f"❌ Failed to start {server_name} server: {e}")
        return None

def cleanup():
    """Clean up resources on exit"""
    print("\nCleaning up...")
    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            pass
    stop_existing_containers()

def signal_handler(signum, frame):
    """Handle termination signals"""
    print("\nReceived termination signal. Cleaning up...")
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
        servers_config = mcp_config.get('mcpServers', {})
        
        # Start Docker container processes
        for server_name, config in servers_config.items():
            if config.get('command') == 'docker':
                process = start_container_process(server_name, config)
                if process:
                    processes.append(process)
        
        print("All MCP servers started successfully.")
        
        # Start the main application
        print("\nStarting main application...")
        main_process = subprocess.Popen(
            [sys.executable, os.path.join(CURRENT_DIR, "src", "main.py")],
            env=dict(os.environ, OLLAMA_MODEL='tinyllama'),
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        processes.append(main_process)
        
        # Wait for the main process
        main_process.wait()
        
    except KeyboardInterrupt:
        print("\nInterrupted by user. Cleaning up...")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
