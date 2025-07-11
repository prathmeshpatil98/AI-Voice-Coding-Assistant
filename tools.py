import os
import subprocess
from pathlib import Path

# Global variables for process management
running_processes = []


def run_command(cmd, timeout=60):
    """Run command with timeout to prevent hanging"""
    try:
        # Handle cd commands specially
        if cmd.strip().startswith('cd '):
            path = cmd.strip()[3:].strip()
            try:
                os.chdir(path)
                return f"Changed directory to: {os.getcwd()}"
            except Exception as e:
                return f"Failed to change directory: {e}"
        
        # Check for server commands that should use run_server instead
        server_commands = ['npm start', 'npm run dev', 'yarn start', 'yarn dev', 
                          'flask run', 'python -m flask run', 'python app.py',
                          'node server.js', 'nodemon', 'serve', 'http-server']
        
        if any(server_cmd in cmd.lower() for server_cmd in server_commands):
            return f"⚠️ This looks like a server command. Use 'run_server' tool instead of 'run_command' for: {cmd}"
        
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            cwd=os.getcwd()
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds: {cmd}"
    except Exception as e:
        return f"Command failed: {e}"

def create_folder(path):
    """Create folder with better error handling"""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return f"Folder created: {os.path.abspath(path)}"
    except Exception as e:
        return f"Error creating folder: {e}"

def write_file(data):
    """Write file with backup and validation"""
    try:
        if isinstance(data, dict):
            path = data.get("path")
            content = data.get("content")
            if not path or content is None:
                return "Invalid input: 'path' and 'content' are required."
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Backup existing file if it exists
            if os.path.exists(path):
                backup_path = f"{path}.backup"
                os.rename(path, backup_path)
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"File written: {os.path.abspath(path)}"
        else:
            return "Input must be a dictionary with 'path' and 'content'."
    except Exception as e:
        return f"Error writing file: {e}"

def read_file(path):
    """Read file contents"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"File content ({path}):\n{content}"
    except Exception as e:
        return f"Error reading file: {e}"

def list_files(path="."):
    """List files and directories with details"""
    try:
        items = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                items.append(f" {item}/")
            else:
                size = os.path.getsize(item_path)
                items.append(f" {item} ({size} bytes)")
        return f"Contents of {os.path.abspath(path)}:\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing files: {e}"

def run_server(cmd):
    """Start server in background with process tracking"""
    try:
        process = subprocess.Popen(
            cmd, 
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        running_processes.append(process)
        return f"Server started (PID: {process.pid}): {cmd}"
    except Exception as e:
        return f"Error starting server: {e}"

def stop_servers():
    """Stop all running servers"""
    stopped = 0
    for process in running_processes:
        try:
            process.terminate()
            process.wait(timeout=5)
            stopped += 1
        except:
            try:
                process.kill()
                stopped += 1
            except:
                pass
    running_processes.clear()
    return f"Stopped {stopped} running processes"

def get_current_directory():
    """Get current working directory"""
    return f"Current directory: {os.getcwd()}"

def find_files(pattern, path="."):
    """Find files matching pattern"""
    try:
        import glob
        matches = glob.glob(os.path.join(path, pattern), recursive=True)
        if matches:
            return f"Found files matching '{pattern}':\n" + "\n".join(matches)
        else:
            return f"No files found matching '{pattern}'"
    except Exception as e:
        return f"Error finding files: {e}"

def check_port(port):
    """Check if port is in use"""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('localhost', int(port)))
            if result == 0:
                return f"Port {port} is in use"
            else:
                return f"Port {port} is available"
    except Exception as e:
        return f"Error checking port: {e}"

