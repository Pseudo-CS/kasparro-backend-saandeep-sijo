#!/usr/bin/env python3
"""
Pre-Submission Verification Script
Checks all requirements before evaluation submission.
"""
import os
import sys
import subprocess
import json
from pathlib import Path

def check_mark():
    return "✅"

def cross_mark():
    return "❌"

def warning_mark():
    return "⚠️"

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def check_file_exists(filepath, description):
    """Check if a required file exists."""
    if Path(filepath).exists():
        print(f"{check_mark()} {description}: {filepath}")
        return True
    else:
        print(f"{cross_mark()} MISSING {description}: {filepath}")
        return False

def check_no_hardcoded_secrets():
    """Verify no hardcoded API keys in Python files."""
    print_header("SECURITY CHECK: No Hardcoded Secrets")
    
    issues_found = []
    patterns = [
        "api_key = \"",
        "api_key='",
        "API_KEY = \"",
        "API_KEY='",
        "password = \"",
        "password='",
    ]
    
    for py_file in Path(".").rglob("*.py"):
        if "venv" in str(py_file) or "__pycache__" in str(py_file):
            continue
        
        with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            for pattern in patterns:
                if pattern in content and "example" not in content.lower():
                    # Check if it's loading from environment
                    if "os.getenv" not in content and "settings." not in content:
                        issues_found.append(f"{py_file}: Contains '{pattern}'")
    
    if not issues_found:
        print(f"{check_mark()} No hardcoded secrets found in Python files")
        return True
    else:
        print(f"{cross_mark()} Found potential hardcoded secrets:")
        for issue in issues_found:
            print(f"  - {issue}")
        return False

def check_docker_files():
    """Verify Docker configuration."""
    print_header("DOCKER CONFIGURATION")
    
    checks = [
        ("Dockerfile", "Docker image definition"),
        ("docker-compose.yml", "Service orchestration"),
        (".dockerignore", "Docker ignore file"),
    ]
    
    results = [check_file_exists(file, desc) for file, desc in checks]
    
    # Check docker-compose has health checks
    if Path("docker-compose.yml").exists():
        with open("docker-compose.yml") as f:
            content = f.read()
            if "healthcheck" in content:
                print(f"{check_mark()} Docker Compose includes health checks")
            else:
                print(f"{warning_mark()} Docker Compose missing health checks")
    
    return all(results)

def check_test_files():
    """Verify test suite exists."""
    print_header("TEST SUITE")
    
    test_dir = Path("tests")
    if not test_dir.exists():
        print(f"{cross_mark()} tests/ directory not found")
        return False
    
    test_files = list(test_dir.glob("test_*.py"))
    print(f"{check_mark()} Found {len(test_files)} test files:")
    for test_file in test_files:
        print(f"  - {test_file}")
    
    return len(test_files) > 0

def check_documentation():
    """Verify documentation exists."""
    print_header("DOCUMENTATION")
    
    docs = [
        ("README.md", "Main documentation"),
        ("EVALUATION_GUIDE.md", "Evaluation guide"),
        ("CLOUD_DEPLOYMENT.md", "Cloud deployment guide"),
        (".env.example", "Environment variable template"),
    ]
    
    results = [check_file_exists(file, desc) for file, desc in docs]
    return all(results)

def check_cicd_pipeline():
    """Verify CI/CD configuration."""
    print_header("CI/CD PIPELINE")
    
    github_dir = Path(".github/workflows")
    if not github_dir.exists():
        print(f"{cross_mark()} .github/workflows/ directory not found")
        return False
    
    workflow_files = list(github_dir.glob("*.yml"))
    if not workflow_files:
        print(f"{cross_mark()} No workflow files found")
        return False
    
    print(f"{check_mark()} Found {len(workflow_files)} workflow files:")
    for workflow in workflow_files:
        print(f"  - {workflow}")
    
    return True

def check_environment_variables():
    """Verify .env.example has all required variables."""
    print_header("ENVIRONMENT VARIABLES")
    
    if not Path(".env.example").exists():
        print(f"{cross_mark()} .env.example not found")
        return False
    
    required_vars = [
        "DATABASE_URL",
        "API_KEY_SOURCE_1",
        "API_URL_SOURCE_1",
        "ENVIRONMENT",
    ]
    
    with open(".env.example") as f:
        content = f.read()
        
        missing = []
        for var in required_vars:
            if var in content:
                print(f"{check_mark()} {var}")
            else:
                print(f"{cross_mark()} MISSING: {var}")
                missing.append(var)
        
        return len(missing) == 0

def check_gitignore():
    """Verify .gitignore protects secrets."""
    print_header("GITIGNORE SECURITY")
    
    if not Path(".gitignore").exists():
        print(f"{cross_mark()} .gitignore not found")
        return False
    
    required_ignores = [".env", "*.key", "*.pem", "__pycache__"]
    
    with open(".gitignore") as f:
        content = f.read()
        
        missing = []
        for pattern in required_ignores:
            if pattern in content:
                print(f"{check_mark()} Ignoring {pattern}")
            else:
                print(f"{warning_mark()} Not ignoring {pattern}")
                missing.append(pattern)
        
        return len(missing) == 0

def check_python_dependencies():
    """Verify requirements.txt exists."""
    print_header("PYTHON DEPENDENCIES")
    
    if not check_file_exists("requirements.txt", "Python dependencies"):
        return False
    
    # Count dependencies
    with open("requirements.txt") as f:
        deps = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        print(f"{check_mark()} {len(deps)} dependencies listed")
        
        # Check for key dependencies
        key_deps = ["fastapi", "sqlalchemy", "pytest", "httpx", "prometheus-client"]
        for dep in key_deps:
            if any(dep in line.lower() for line in deps):
                print(f"  ✓ {dep}")
            else:
                print(f"  ✗ {dep} (missing)")
    
    return True

def check_smoke_test():
    """Verify smoke test script exists."""
    print_header("SMOKE TEST SCRIPT")
    
    return check_file_exists("smoke_test.py", "Smoke test script")

def run_quick_tests():
    """Try to run quick tests if Docker is available."""
    print_header("QUICK DOCKER TEST (Optional)")
    
    try:
        # Check if Docker is running
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print(f"{check_mark()} Docker is running")
            
            # Check if containers are up
            if "etl_service" in result.stdout:
                print(f"{check_mark()} ETL service container is running")
            else:
                print(f"{warning_mark()} ETL service container not running")
                print("  Run: docker-compose up -d")
            
            return True
        else:
            print(f"{warning_mark()} Docker not running")
            return True  # Not critical for verification
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print(f"{warning_mark()} Docker not available")
        return True  # Not critical

def main():
    """Run all verification checks."""
    print("\n" + "="*80)
    print("  KASPARRO ETL SYSTEM - PRE-SUBMISSION VERIFICATION")
    print("="*80)
    
    checks = [
        ("Security (No Hardcoded Secrets)", check_no_hardcoded_secrets),
        ("Docker Configuration", check_docker_files),
        ("Test Suite", check_test_files),
        ("Documentation", check_documentation),
        ("CI/CD Pipeline", check_cicd_pipeline),
        ("Environment Variables", check_environment_variables),
        ("Gitignore Security", check_gitignore),
        ("Python Dependencies", check_python_dependencies),
        ("Smoke Test Script", check_smoke_test),
        ("Docker Runtime (Optional)", run_quick_tests),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"{cross_mark()} Error in {name}: {e}")
            results[name] = False
    
    # Summary
    print_header("VERIFICATION SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check_name, passed_check in results.items():
        status = check_mark() if passed_check else cross_mark()
        print(f"{status} {check_name}")
    
    print(f"\n{'='*80}")
    print(f"Results: {passed}/{total} checks passed ({(passed/total)*100:.0f}%)")
    print(f"{'='*80}\n")
    
    if passed == total:
        print("🎉 ALL CHECKS PASSED! System is ready for submission.")
        print("\nNext steps:")
        print("1. Commit all changes: git add . && git commit -m 'Final submission'")
        print("2. Push to repository: git push origin main")
        print("3. Build Docker image: docker-compose build")
        print("4. Test locally: python smoke_test.py")
        print("5. Deploy to cloud: See CLOUD_DEPLOYMENT.md")
        return 0
    else:
        print(f"⚠️  {total - passed} check(s) failed. Review output above.")
        print("\nFix issues before submission!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
