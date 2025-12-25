#!/usr/bin/env python3
"""
Quick start script to help users set up and run the project.
"""
import os
import sys
import subprocess
from pathlib import Path


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")


def check_command(command):
    """Check if a command is available."""
    try:
        subprocess.run([command, "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    """Main setup function."""
    print_header("ETL Backend Service - Quick Start")
    
    # Check prerequisites
    print("Checking prerequisites...")
    
    if not check_command("docker"):
        print("❌ Docker is not installed. Please install Docker first.")
        print("   Visit: https://docs.docker.com/get-docker/")
        sys.exit(1)
    print("✓ Docker is installed")
    
    if not check_command("docker-compose"):
        print("❌ Docker Compose is not installed. Please install Docker Compose first.")
        print("   Visit: https://docs.docker.com/compose/install/")
        sys.exit(1)
    print("✓ Docker Compose is installed")
    
    # Check for .env file
    env_file = Path(".env")
    if not env_file.exists():
        print("\n⚠️  .env file not found. Creating from template...")
        env_example = Path(".env.example")
        if env_example.exists():
            env_example.read_text()
            with open(".env", "w") as f:
                f.write(env_example.read_text())
            print("✓ .env file created")
            print("\n⚠️  IMPORTANT: Please edit .env file and add your API keys!")
            print("   Required: API_KEY_SOURCE_1, API_URL_SOURCE_1, RSS_FEED_URL")
            
            response = input("\nHave you configured your .env file? (y/n): ")
            if response.lower() != 'y':
                print("\nPlease configure .env file and run this script again.")
                sys.exit(0)
        else:
            print("❌ .env.example not found. Cannot create .env file.")
            sys.exit(1)
    else:
        print("✓ .env file exists")
    
    # Start services
    print_header("Starting Services")
    print("This may take a few minutes on first run (downloading images)...\n")
    
    try:
        subprocess.run(["docker-compose", "up", "-d"], check=True)
        print("\n✓ Services started successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Failed to start services: {e}")
        sys.exit(1)
    
    # Wait for services to be ready
    print("\nWaiting for services to be ready (30 seconds)...")
    import time
    time.sleep(30)
    
    # Print access information
    print_header("Service Information")
    print("API Endpoint:      http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("Health Check:      http://localhost:8000/health")
    print("Statistics:        http://localhost:8000/stats")
    
    print("\nCommon Commands:")
    print("  make logs      - View all logs")
    print("  make logs-api  - View API logs only")
    print("  make test      - Run test suite")
    print("  make run-etl   - Manually trigger ETL")
    print("  make down      - Stop all services")
    
    print_header("Next Steps")
    print("1. Test the API: curl http://localhost:8000/health")
    print("2. View documentation: Open http://localhost:8000/docs in your browser")
    print("3. Check ETL status: curl http://localhost:8000/stats")
    print("4. Query data: curl 'http://localhost:8000/data?page=1&page_size=10'")
    
    print("\nFor more information, see README.md")
    print("\n✓ Setup complete! Your ETL Backend Service is running.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
