"""
Azure IoT Device Simulator - Main Entry Point.

This module provides the CLI interface for the Azure IoT device simulator,
allowing interactive commands to send test payloads to Azure IoT Hub.

Usage:
    Interactive mode: python main.py --project <project_name>
    Single-shot mode: python main.py --project <project_name> --payload '{"key": "value"}'
"""

if __package__:
    from . import globals, transmission
else:  # Standalone package executes this file directly.
    import globals
    import transmission
import argparse
import json
import sys
from datetime import datetime, timezone


def help_menu():
    """Display available commands."""
    print("""
    Available commands:
      send                        - Sends payload to Azure IoT Hub.
      help                        - Show this help menu.
      exit                        - Exit the program.
    """)


def main():
    """Main entry point for the Azure IoT device simulator."""
    parser = argparse.ArgumentParser(description="Azure IoT Device Simulator")
    parser.add_argument("--project", help="Name of the project (for integrated mode)")
    parser.add_argument("--config", help="Explicit simulator config path")
    parser.add_argument("--payload", help="Custom payload JSON (single-shot mode for log tracing)")
    parser.add_argument("--payload-stdin", action="store_true", help="Read one payload from stdin")
    parser.add_argument("--device", help="Device ID for device-specific config (used with --project)")
    args = parser.parse_args()

    try:
        globals.initialize_config(
            project_name=args.project,
            device_id=args.device,
            config_path=args.config,
        )
    except Exception as e:
        print(f"Error initializing simulator: {e}")
        sys.exit(1)

    # Single-shot mode: send custom payload and exit
    payload_text = sys.stdin.read() if args.payload_stdin else args.payload
    if payload_text:
        try:
            payload = json.loads(payload_text)
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
    print("Welcome to the Azure IoT Device Simulator. Type 'help' for commands.")

    while True:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue

        parts = user_input.split()
        command = parts[0]

        if command == "send":
            try:
                transmission.send()
            except Exception as e:
                print(f"Error sending message: {e}")
        elif command == "help":
            help_menu()
        elif command == "exit":
            print("Goodbye!")
            break
        else:
            print(f"Unknown command: {command}. Type 'help' for a list of commands.")


if __name__ == "__main__":
    main()
