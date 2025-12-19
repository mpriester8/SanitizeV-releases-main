"""
FiveM server favorites management system.
"""

import os
import json
import subprocess
import platform
from typing import List, Dict, Optional
from logic import STATE_DIR


SERVERS_FILE = os.path.join(STATE_DIR, "fivem_servers.json")


def load_servers() -> List[Dict]:
    """Load saved FiveM servers."""
    if os.path.exists(SERVERS_FILE):
        try:
            with open(SERVERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("servers", [])
        except (IOError, json.JSONDecodeError):
            return []
    return []


def save_servers(servers: List[Dict]):
    """Save FiveM servers list."""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(SERVERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"servers": servers}, f, indent=2)
    except IOError as e:
        print(f"Error saving servers: {e}")


def add_server(name: str, ip: str, profile_id: Optional[str] = None) -> bool:
    """
    Add a new FiveM server favorite.
    
    Args:
        name: Server display name
        ip: Server IP address (e.g., "connect cfx.re/join/abc123")
        profile_id: Optional profile ID to auto-load with this server
    
    Returns:
        True if successful
    """
    try:
        servers = load_servers()
        
        # Check for duplicate
        if any(s["ip"] == ip for s in servers):
            return False
        
        servers.append({
            "name": name,
            "ip": ip,
            "profile_id": profile_id,
            "last_used": None
        })
        
        save_servers(servers)
        return True
    except Exception as e:
        print(f"Error adding server: {e}")
        return False


def update_server(old_ip: str, name: str, ip: str, profile_id: Optional[str] = None) -> bool:
    """Update an existing server."""
    try:
        servers = load_servers()
        
        for server in servers:
            if server["ip"] == old_ip:
                server["name"] = name
                server["ip"] = ip
                server["profile_id"] = profile_id
                save_servers(servers)
                return True
        
        return False
    except Exception as e:
        print(f"Error updating server: {e}")
        return False


def delete_server(ip: str) -> bool:
    """Delete a server by IP."""
    try:
        servers = load_servers()
        servers = [s for s in servers if s["ip"] != ip]
        save_servers(servers)
        return True
    except Exception as e:
        print(f"Error deleting server: {e}")
        return False


def launch_fivem(server_ip: str) -> bool:
    """
    Launch FiveM with the specified server.
    
    Args:
        server_ip: Server connection string (e.g., "cfx.re/join/abc123")
    
    Returns:
        True if launch was successful
    """
    try:
        # Update last used timestamp
        servers = load_servers()
        from datetime import datetime
        for server in servers:
            if server["ip"] == server_ip:
                server["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_servers(servers)
                break
        
        # Construct FiveM launch URL
        if not server_ip.startswith("fivem://"):
            # Support both "cfx.re/join/abc123" and direct "connect abc123"
            if "cfx.re" in server_ip or "connect" in server_ip:
                # Clean up the connect string
                connect_code = server_ip.replace("connect ", "").replace("cfx.re/join/", "").strip()
                launch_url = f"fivem://connect/cfx.re/join/{connect_code}"
            else:
                # Assume it's a direct IP
                launch_url = f"fivem://connect/{server_ip}"
        else:
            launch_url = server_ip
        
        # Launch FiveM using the protocol handler
        if platform.system() == 'Windows':
            os.startfile(launch_url)  # pylint: disable=no-member
        elif platform.system() == 'Darwin':  # macOS
            subprocess.Popen(['open', launch_url])
        else:  # Linux
            subprocess.Popen(['xdg-open', launch_url])
        
        return True
    except Exception as e:
        print(f"Error launching FiveM: {e}")
        return False
