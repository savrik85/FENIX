#!/usr/bin/env python3
"""
Deployment verification script for FENIX monitoring system
"""

import json
import subprocess
from datetime import datetime

import requests


def run_command(cmd: str, timeout: int = 30) -> tuple[bool, str]:
    """Run shell command and return success status and output"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout} seconds"
    except Exception as e:
        return False, str(e)


def check_container_status():
    """Check if all required containers are running"""
    print("\n🔍 Checking container status...")

    success, output = run_command("docker compose ps --format json")
    if not success:
        print("❌ Failed to get container status")
        return False

    try:
        containers = [json.loads(line) for line in output.strip().split("\n") if line]

        required_services = [
            "fenix-postgres",
            "fenix-redis",
            "fenix-eagle",
            "fenix-celery-worker",
            "fenix-celery-beat",
        ]

        running_services = []
        for container in containers:
            name = container.get("Name", "")
            state = container.get("State", "")
            if state == "running":
                running_services.append(name)
                print(f"✅ {name}: {state}")
            else:
                print(f"❌ {name}: {state}")

        missing = set(required_services) - set(running_services)
        if missing:
            print(f"❌ Missing services: {', '.join(missing)}")
            return False

        print("✅ All required containers are running")
        return True

    except Exception as e:
        print(f"❌ Error parsing container status: {e}")
        return False


def check_service_health():
    """Check health endpoints of services"""
    print("\n🏥 Checking service health...")

    services = {
        "Eagle Service": "http://localhost:8001/health",
        # Add Gateway when available
        # 'Gateway Service': 'http://localhost:8000/health',
    }

    all_healthy = True
    for service_name, health_url in services.items():
        try:
            response = requests.get(health_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                print(f"✅ {service_name}: {status}")
            else:
                print(f"❌ {service_name}: HTTP {response.status_code}")
                all_healthy = False
        except Exception as e:
            print(f"❌ {service_name}: {e}")
            all_healthy = False

    return all_healthy


def check_database_connection():
    """Check database connectivity"""
    print("\n🗄️ Checking database connection...")

    success, output = run_command(
        "docker compose exec postgres pg_isready -h localhost -p 5432 -U fenix"
    )

    if success:
        print("✅ Database is ready")
        return True
    else:
        print(f"❌ Database not ready: {output}")
        return False


def check_redis_connection():
    """Check Redis connectivity"""
    print("\n🔴 Checking Redis connection...")

    success, output = run_command("docker compose exec redis redis-cli ping")

    if success and "PONG" in output:
        print("✅ Redis is responding")
        return True
    else:
        print(f"❌ Redis not responding: {output}")
        return False


def check_celery_workers():
    """Check Celery worker status"""
    print("\n👷 Checking Celery workers...")

    # Check if worker is responding
    success, output = run_command(
        "docker compose exec celery-worker celery -A src.services.scheduler inspect ping",
        timeout=15,
    )

    if success and "pong" in output.lower():
        print("✅ Celery worker is responding")
        worker_healthy = True
    else:
        print(f"❌ Celery worker not responding: {output}")
        worker_healthy = False

    # Check if beat scheduler is running
    success, output = run_command(
        "docker compose exec celery-beat celery -A src.services.scheduler inspect ping",
        timeout=15,
    )

    if success and "pong" in output.lower():
        print("✅ Celery beat scheduler is responding")
        beat_healthy = True
    else:
        print(f"❌ Celery beat scheduler not responding: {output}")
        beat_healthy = False

    return worker_healthy and beat_healthy


def check_logs_for_errors():
    """Check recent logs for critical errors"""
    print("\n📋 Checking recent logs for errors...")

    services = ["eagle", "celery-worker", "celery-beat"]

    for service in services:
        success, output = run_command(
            f"docker compose logs --tail=50 {service}", timeout=10
        )

        if success:
            # Look for error patterns
            error_patterns = ["ERROR", "CRITICAL", "Exception", "Traceback"]
            recent_errors = []

            for line in output.split("\n")[-20:]:  # Check last 20 lines
                if any(pattern in line for pattern in error_patterns):
                    recent_errors.append(line.strip())

            if recent_errors:
                print(f"⚠️ {service} has recent errors:")
                for error in recent_errors[-3:]:  # Show last 3 errors
                    print(f"    {error}")
            else:
                print(f"✅ {service}: No recent errors")
        else:
            print(f"❌ Failed to get logs for {service}")


def test_monitoring_api():
    """Test monitoring API endpoints"""
    print("\n🧪 Testing monitoring API...")

    try:
        # Test basic scraping endpoint
        response = requests.get("http://localhost:8001/scrape/sources", timeout=10)
        if response.status_code == 200:
            print("✅ Scraping sources endpoint working")
        else:
            print(f"❌ Scraping sources endpoint: HTTP {response.status_code}")
            return False

        # Test monitoring stats endpoint
        response = requests.get("http://localhost:8001/monitoring/stats", timeout=10)
        if response.status_code == 200:
            print("✅ Monitoring stats endpoint working")
        else:
            print(f"❌ Monitoring stats endpoint: HTTP {response.status_code}")
            return False

        print("✅ Core monitoring APIs are functional")
        return True

    except Exception as e:
        print(f"❌ Monitoring API test failed: {e}")
        return False


def main():
    """Main verification function"""
    print("🚀 FENIX Deployment Verification")
    print("=" * 50)
    print(f"Verification started at: {datetime.now().isoformat()}")

    checks = [
        ("Container Status", check_container_status),
        ("Service Health", check_service_health),
        ("Database Connection", check_database_connection),
        ("Redis Connection", check_redis_connection),
        ("Celery Workers", check_celery_workers),
        ("Monitoring API", test_monitoring_api),
        (
            "Recent Logs",
            lambda: (check_logs_for_errors(), True)[1],
        ),  # Always return True for logs
    ]

    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} check failed with exception: {e}")
            results.append((check_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 50)

    passed = 0
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
        if result:
            passed += 1

    total = len(results)
    success_rate = (passed / total) * 100

    print(f"\nResults: {passed}/{total} checks passed ({success_rate:.1f}%)")

    if passed == total:
        print("\n🎉 Deployment verification successful!")
        print("Your FENIX monitoring system is ready to use.")
        print("\nNext steps:")
        print("- Run 'python test_monitoring_flow.py' for end-to-end testing")
        print("- Check monitoring configs at http://localhost:8001/monitoring/configs")
        print("- View MailHog at http://localhost:8025 for email testing")
    else:
        print("\n⚠️ Some checks failed. Please review the output above.")
        print("Common fixes:")
        print("- Run 'docker compose up -d' to start missing containers")
        print("- Check 'docker compose logs <service-name>' for error details")
        print("- Ensure all required environment variables are set in .env")

    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
