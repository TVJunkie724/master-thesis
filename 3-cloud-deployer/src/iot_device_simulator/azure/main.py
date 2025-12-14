"""
Azure IoT Device Simulator - Main Entry Point.

This module provides the CLI interface for the Azure IoT device simulator,
allowing interactive commands to send test payloads to Azure IoT Hub.

Usage:
    Standalone mode: python main.py (with config.json in current directory)
    Integrated mode: python main.py --project <project_name>
"""

from . import globals
from . import transmission
import argparse


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
    args = parser.parse_args()

    try:
        globals.initialize_config(project_name=args.project)
    except Exception as e:
        print(f"Error initializing simulator: {e}")
        return

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
