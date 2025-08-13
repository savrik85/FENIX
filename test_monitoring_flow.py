#!/usr/bin/env python3
"""
Test script for FENIX monitoring system end-to-end flow
"""

import asyncio
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fenix-eagle", "src"))

from services.http_client_service import EagleServiceClient
from services.scheduler import _daily_tender_scan_async


async def test_eagle_service_connection():
    """Test basic connectivity to Eagle service"""
    print("🔍 Testing Eagle service connectivity...")

    async with EagleServiceClient() as client:
        is_healthy = await client.health_check()
        if is_healthy:
            print("✅ Eagle service is healthy")
            return True
        else:
            print("❌ Eagle service is not healthy")
            return False


async def test_single_scraping_job():
    """Test creating a single scraping job via HTTP client"""
    print("🔍 Testing single scraping job...")

    async with EagleServiceClient() as client:
        # Create a simple job
        job_response = await client.create_scraping_job(source="sam.gov", keywords=["windows"], max_results=1)

        if not job_response:
            print("❌ Failed to create scraping job")
            return False

        job_id = job_response.get("job_id")
        print(f"✅ Created job: {job_id}")

        # Wait for completion
        print("⏳ Waiting for job completion...")
        job_status = await client.wait_for_job_completion(job_id, timeout=60)

        if not job_status:
            print("❌ Job did not complete within timeout")
            return False

        if job_status.get("status") == "completed":
            results_count = job_status.get("results_count", 0)
            print(f"✅ Job completed successfully with {results_count} results")
            return True
        else:
            print(f"❌ Job failed: {job_status.get('error_message', 'Unknown error')}")
            return False


async def test_full_monitoring_scan():
    """Test complete monitoring scan flow"""
    print("🔍 Testing full monitoring scan...")

    try:
        result = await _daily_tender_scan_async()

        if result.get("status") == "completed":
            total_tenders = result.get("total_new_tenders", 0)
            configs_processed = result.get("configs_processed", 0)
            print("✅ Monitoring scan completed successfully!")
            print(f"   - Configs processed: {configs_processed}")
            print(f"   - Total new tenders: {total_tenders}")

            # Show scan results details
            scan_results = result.get("scan_results", [])
            for scan_result in scan_results:
                config_name = scan_result.get("config")
                new_tenders = scan_result.get("new_tenders", 0)
                print(f"   - {config_name}: {new_tenders} new tenders")

            return True
        else:
            error = result.get("error", "Unknown error")
            print(f"❌ Monitoring scan failed: {error}")
            return False

    except Exception as e:
        print(f"❌ Monitoring scan crashed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("🚀 Starting FENIX monitoring system tests...\n")

    # Test 1: Eagle service connectivity
    connectivity_ok = await test_eagle_service_connection()
    print()

    if not connectivity_ok:
        print("💥 Eagle service is not available. Make sure services are running:")
        print("   docker compose up -d")
        return False

    # Test 2: Single scraping job
    single_job_ok = await test_single_scraping_job()
    print()

    if not single_job_ok:
        print("💥 Single scraping job test failed")
        return False

    # Test 3: Full monitoring scan
    full_scan_ok = await test_full_monitoring_scan()
    print()

    if full_scan_ok:
        print("🎉 ALL TESTS PASSED! Monitoring system is working correctly.")
        print("\n📧 If monitoring found new tenders, emails should be sent to:")
        print("   - petr.pechousek@gmail.com")
        print("   - savrikk@gmail.com")
        return True
    else:
        print("💥 Full monitoring scan test failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
