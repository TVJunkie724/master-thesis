#!/usr/bin/env python3
"""
GCP IoT Device Simulator - Main entry point.

Usage:
    python main.py --project <project_name>
    python main.py --project <project_name> --payload '{"key": "value"}'

Features:
    - Interactive menu for manual testing
    - Single-payload mode via --payload argument (for log tracing)
    - Configurable via config_generated.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from . import globals
from . import transmission


def get_config_path(project_name: str, device_id: str = None) -> str:
    """Construct path to config_generated.json for a project/device."""
    # When running inside container
    base = "/app/upload" if os.path.exists("/app/upload") else "upload"
    google_sim_dir = f"{base}/{project_name}/iot_device_simulator/google"
    
    if device_id:
        # Device-specific config path
        return f"{google_sim_dir}/{device_id}/config_generated.json"
    else:
        # Fallback: find first device subdirectory
        if os.path.exists(google_sim_dir):
            device_dirs = [d for d in os.listdir(google_sim_dir) 
                          if os.path.isdir(os.path.join(google_sim_dir, d))]
            if device_dirs:
                return f"{google_sim_dir}/{device_dirs[0]}/config_generated.json"
        raise ValueError(f"No device configs found in {google_sim_dir}")


def print_menu():
    """Display the interactive menu."""
    print("\n" + "=" * 50)
    print("GCP IoT Device Simulator")
    print("=" * 50)
    print("1. Send next payload from payloads.json")
    print("2. Send all payloads")
    print("3. Show current configuration")
    print("4. Exit")
    print("=" * 50)


def show_config():
    """Display current configuration."""
    print("\nCurrent Configuration:")
    print(f"  Project ID: {globals.config.project_id}")
    print(f"  Topic Name: {globals.config.topic_name}")
    print(f"  Device ID: {globals.config.device_id}")
    print(f"  Service Account Key: {globals.config.service_account_key_path}")
    print(f"  Payload Path: {globals.config.payload_path}")


def send_all_payloads():
    """Send all payloads from the payloads file."""
    with open(globals.config.payload_path, "r", encoding="utf-8") as f:
        payloads = json.load(f)
    
    print(f"\nSending {len(payloads)} payloads...")
    for i, payload in enumerate(payloads):
        if "time" not in payload or payload["time"] == "":
            payload["time"] = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        transmission.send_mqtt(payload)
        print(f"  [{i+1}/{len(payloads)}] Sent")


def interactive_mode():
    """Run the simulator in interactive mode."""
    while True:
        print_menu()
        choice = input("Select option: ").strip()
        
        if choice == "1":
            transmission.send()
        elif choice == "2":
            send_all_payloads()
        elif choice == "3":
            show_config()
        elif choice == "4" or choice.lower() == "exit":
            print("Exiting...")
            break
        else:
            print("Invalid option. Please try again.")


def main():
    parser = argparse.ArgumentParser(description="GCP IoT Device Simulator")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--payload", help="Custom payload JSON (single-shot mode for log tracing)")
    parser.add_argument("--device", help="Device ID for device-specific config")
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config_path = get_config_path(args.project, args.device)
    except ValueError as e:
        print(f"ERROR: {e}")
        print("Deploy L1 first to generate simulator configuration.")
        sys.exit(1)
    
    if not os.path.exists(config_path):
        print(f"ERROR: Config not found at {config_path}")
        print("Deploy L1 first to generate simulator configuration.")
        sys.exit(1)
    
    globals.load_config(config_path)
    
    # Single-shot mode: send custom payload and exit
    if args.payload:
        try:
            payload = json.loads(args.payload)
            # Add timestamp if missing
            if "time" not in payload or payload["time"] == "":
                payload["time"] = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            transmission.send_mqtt(payload)
            sys.exit(0)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON payload: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Failed to send payload: {e}")
            sys.exit(1)
    
    # Interactive mode
    print(f"Loaded configuration from: {config_path}")
    interactive_mode()


if __name__ == "__main__":
    main()
