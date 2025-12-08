"""
IoT Device Simulator - Main Entry Point.

This module provides the CLI interface for the IoT device simulator,
allowing interactive commands to send test payloads to IoT Core.

Migration Status:
    - Uses globals for device configuration (separate context from main app).
    - This is a standalone utility - no migration needed.
"""

import globals
import transmission

def help_menu():
  print("""
    Available commands:
      send                        - Sends payload to IoT endpoint.
      help                        - Show this help menu.
      exit                        - Exit the program.
  """)

import argparse

def main():
    parser = argparse.ArgumentParser(description="IoT Device Simulator")
    parser.add_argument("--project", help="Name of the project (for integrated mode)")
    args = parser.parse_args()

    try:
        globals.initialize_config(project_name=args.project)
    except Exception as e:
        print(f"Error initializing simulator: {e}")
        return

    print("Welcome to the IoT Device Simulator. Type 'help' for commands.")

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
      args = parts[1:]

      if command == "send":
        transmission.send()
      elif command == "help":
        help_menu()
      elif command == "exit":
        print("Goodbye!")
        break
      else:
        print(f"Unknown command: {command}. Type 'help' for a list of commands.")

if __name__ == "__main__":
  main()
