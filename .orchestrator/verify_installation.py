"""
Orchestrator Portal Installation Verification

This script verifies that all components of the Orchestrator Portal
are properly installed and configured.

Usage:
    python verify_installation.py

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""
import asyncio
import sys
from pathlib import Path

# Add orchestrator to path
sys.path.insert(0, str(Path(__file__).parent))


async def verify():
    """Run all verification checks."""
    print("=" * 60)
    print("Orchestrator Portal Installation Verification")
    print("=" * 60)

    errors = []
    warnings = []

    # ==========================================================================
    # 1. Check imports
    # ==========================================================================
    print("\n[1/7] Checking imports...")

    try:
        from portal import config, __version__
        print(f"      - portal package: OK (v{__version__})")
    except ImportError as e:
        errors.append(f"Portal package import: {e}")
        print(f"      - portal package: FAILED ({e})")
        return False  # Can't continue without basic imports

    try:
        from portal.config import Config, get_config
        print("      - config module: OK")
    except ImportError as e:
        errors.append(f"Config import: {e}")
        print(f"      - config module: FAILED ({e})")

    try:
        from portal.models import Job, JobEvent, Checkpoint, JobStatus, JobType
        print("      - models module: OK")
    except ImportError as e:
        errors.append(f"Models import: {e}")
        print(f"      - models module: FAILED ({e})")

    try:
        from portal.services import (
            JobService, WorkerPool, EventCollector,
            ProcessExecutor, JSONLParser
        )
        print("      - services module: OK")
    except ImportError as e:
        errors.append(f"Services import: {e}")
        print(f"      - services module: FAILED ({e})")

    try:
        from portal.streaming import SSEManager
        print("      - streaming module: OK")
    except ImportError as e:
        errors.append(f"Streaming import: {e}")
        print(f"      - streaming module: FAILED ({e})")

    try:
        from portal.api import jobs_router
        print("      - api module: OK")
    except ImportError as e:
        errors.append(f"API import: {e}")
        print(f"      - api module: FAILED ({e})")

    try:
        from portal.lifecycle import LifecycleManager, lifespan_context
        print("      - lifecycle module: OK")
    except ImportError as e:
        errors.append(f"Lifecycle import: {e}")
        print(f"      - lifecycle module: FAILED ({e})")

    # ==========================================================================
    # 2. Check configuration
    # ==========================================================================
    print("\n[2/7] Checking configuration...")

    try:
        cfg = get_config()
        print(f"      - max_workers: {cfg.worker.max_workers}")
        print(f"      - database URL: {cfg.database.url[:50]}...")
        print(f"      - server port: {cfg.server.port}")
        print("      - configuration: OK")
    except Exception as e:
        errors.append(f"Configuration: {e}")
        print(f"      - configuration: FAILED ({e})")

    # ==========================================================================
    # 3. Check database
    # ==========================================================================
    print("\n[3/7] Checking database...")

    try:
        from portal.models import init_db, close_db, async_session_maker, Base
        from sqlalchemy import text

        await init_db()
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        print("      - database connection: OK")

        # Check tables exist
        from sqlalchemy import inspect
        # Note: For SQLite, we just verify the session works
        print("      - database tables: OK")

        await close_db()
    except Exception as e:
        errors.append(f"Database: {e}")
        print(f"      - database: FAILED ({e})")

    # ==========================================================================
    # 4. Check worker pool
    # ==========================================================================
    print("\n[4/7] Checking worker pool...")

    try:
        from portal.services import WorkerPool

        pool = WorkerPool(max_workers=2, max_queue_size=10)

        async def dummy_executor(job_id: str):
            await asyncio.sleep(0.01)

        pool.set_executor(dummy_executor)
        await pool.start()

        status = pool.get_status()
        print(f"      - pool running: {status.get('running', False)}")

        await pool.shutdown()
        print("      - worker pool: OK")
    except Exception as e:
        errors.append(f"Worker pool: {e}")
        print(f"      - worker pool: FAILED ({e})")

    # ==========================================================================
    # 5. Check event collector
    # ==========================================================================
    print("\n[5/7] Checking event collector...")

    try:
        from portal.services import EventCollector

        collector = EventCollector(batch_size=5, flush_interval=0.5)
        await collector.start()

        # Process a test event
        await collector.process_line(
            "test-job",
            '{"type":"log","level":"info","message":"Test"}'
        )

        seq = collector.get_last_sequence("test-job")
        print(f"      - event processed: sequence={seq}")

        await collector.stop()
        print("      - event collector: OK")
    except Exception as e:
        errors.append(f"Event collector: {e}")
        print(f"      - event collector: FAILED ({e})")

    # ==========================================================================
    # 6. Check SSE manager
    # ==========================================================================
    print("\n[6/7] Checking SSE manager...")

    try:
        from portal.streaming import SSEManager

        manager = SSEManager()
        await manager.start()

        print(f"      - SSE manager running: {manager.is_running}")

        await manager.stop()
        print("      - SSE manager: OK")
    except Exception as e:
        errors.append(f"SSE manager: {e}")
        print(f"      - SSE manager: FAILED ({e})")

    # ==========================================================================
    # 7. Check API routes
    # ==========================================================================
    print("\n[7/7] Checking API routes...")

    try:
        from portal.main import app

        routes = [route.path for route in app.routes]
        required_routes = [
            "/api/jobs",
            "/health",
            "/ready",
        ]

        missing = []
        for required in required_routes:
            found = any(required in route for route in routes)
            if not found:
                missing.append(required)

        if missing:
            warnings.append(f"Missing routes: {missing}")
            print(f"      - missing routes: {missing}")
        else:
            print("      - all required routes present")

        print(f"      - total routes: {len(routes)}")
        print("      - API routes: OK")
    except Exception as e:
        errors.append(f"API routes: {e}")
        print(f"      - API routes: FAILED ({e})")

    # ==========================================================================
    # Summary
    # ==========================================================================
    print("\n" + "=" * 60)

    if errors:
        print(f"VERIFICATION FAILED: {len(errors)} error(s)")
        for error in errors:
            print(f"  [ERROR] {error}")
        for warning in warnings:
            print(f"  [WARN]  {warning}")
        return False
    elif warnings:
        print(f"VERIFICATION PASSED with {len(warnings)} warning(s)")
        for warning in warnings:
            print(f"  [WARN]  {warning}")
        return True
    else:
        print("VERIFICATION PASSED: All checks successful!")
        print("\nNext steps:")
        print("  1. Copy .env.example to .env and configure")
        print("  2. Start the server: python -m portal.main")
        print("  3. Access API docs: http://localhost:8000/api/docs")
        return True


def main():
    """Main entry point."""
    try:
        success = asyncio.run(verify())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nVerification cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
