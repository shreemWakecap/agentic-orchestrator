"""
Unit tests for JobService.
"""
import pytest
from datetime import datetime


@pytest.mark.asyncio
class TestJobService:
    """Tests for JobService operations."""

    async def test_create_job(self, job_service):
        """Test job creation."""
        from portal.models import JobType, JobStatus

        job = await job_service.create_job(
            job_type=JobType.PLAN,
            parameters={"spec_id": "test-001"},
            priority=2,
        )

        assert job.id is not None
        assert len(job.id) == 32
        assert job.job_type == JobType.PLAN
        assert job.status == JobStatus.PENDING
        assert job.parameters["spec_id"] == "test-001"
        assert job.priority == 2

    async def test_get_job(self, job_service, job_factory):
        """Test job retrieval."""
        created = await job_factory()

        fetched = await job_service.get_job(created.id)

        assert fetched is not None
        assert fetched.id == created.id

    async def test_get_job_not_found(self, job_service):
        """Test getting non-existent job."""
        result = await job_service.get_job("nonexistent")
        assert result is None

    async def test_get_job_or_raise(self, job_service):
        """Test get_job_or_raise raises for missing job."""
        from portal.services import JobNotFoundError

        with pytest.raises(JobNotFoundError):
            await job_service.get_job_or_raise("nonexistent")

    async def test_update_job_status_queued(self, job_service, job_factory):
        """Test PENDING -> QUEUED transition."""
        from portal.models import JobStatus

        job = await job_factory(status=JobStatus.PENDING)

        updated = await job_service.mark_job_queued(job.id)
        assert updated.status == JobStatus.QUEUED
        assert updated.queued_at is not None

    async def test_update_job_status_running(self, job_service, job_factory):
        """Test QUEUED -> RUNNING transition."""
        from portal.models import JobStatus

        job = await job_factory(status=JobStatus.QUEUED)

        updated = await job_service.mark_job_running(job.id)
        assert updated.status == JobStatus.RUNNING
        assert updated.started_at is not None

    async def test_update_job_status_succeeded(self, job_service, job_factory):
        """Test RUNNING -> SUCCEEDED transition."""
        from portal.models import JobStatus

        job = await job_factory(status=JobStatus.RUNNING)

        updated = await job_service.mark_job_succeeded(job.id, exit_code=0)
        assert updated.status == JobStatus.SUCCEEDED
        assert updated.completed_at is not None
        assert updated.exit_code == 0

    async def test_update_job_status_failed(self, job_service, job_factory):
        """Test RUNNING -> FAILED transition."""
        from portal.models import JobStatus

        job = await job_factory(status=JobStatus.RUNNING)

        updated = await job_service.mark_job_failed(
            job.id,
            exit_code=1,
            error_message="Something went wrong"
        )
        assert updated.status == JobStatus.FAILED
        assert updated.completed_at is not None
        assert updated.exit_code == 1
        assert updated.error_message == "Something went wrong"

    async def test_invalid_state_transition(self, job_service, job_factory):
        """Test that invalid transitions raise errors."""
        from portal.models import JobStatus
        from portal.services import InvalidJobStateError

        job = await job_factory(status=JobStatus.SUCCEEDED)

        with pytest.raises(InvalidJobStateError):
            await job_service.mark_job_running(job.id)

    async def test_list_jobs_no_filter(self, job_service, job_factory):
        """Test job listing without filters."""
        from portal.models import JobStatus

        await job_factory(status=JobStatus.RUNNING)
        await job_factory(status=JobStatus.SUCCEEDED)
        await job_factory(status=JobStatus.FAILED)

        jobs, total = await job_service.list_jobs()
        assert total == 3
        assert len(jobs) == 3

    async def test_list_jobs_filter_by_status(self, job_service, job_factory):
        """Test job listing with status filter."""
        from portal.models import JobStatus, JobType

        await job_factory(status=JobStatus.RUNNING, job_type=JobType.PLAN)
        await job_factory(status=JobStatus.SUCCEEDED, job_type=JobType.PLAN)
        await job_factory(status=JobStatus.RUNNING, job_type=JobType.BUILD)

        jobs, total = await job_service.list_jobs(status=JobStatus.RUNNING)
        assert total == 2
        assert all(j.status == JobStatus.RUNNING for j in jobs)

    async def test_list_jobs_filter_by_type(self, job_service, job_factory):
        """Test job listing with type filter."""
        from portal.models import JobStatus, JobType

        await job_factory(status=JobStatus.RUNNING, job_type=JobType.PLAN)
        await job_factory(status=JobStatus.SUCCEEDED, job_type=JobType.PLAN)
        await job_factory(status=JobStatus.RUNNING, job_type=JobType.BUILD)

        jobs, total = await job_service.list_jobs(job_type=JobType.PLAN)
        assert total == 2
        assert all(j.job_type == JobType.PLAN for j in jobs)

    async def test_update_progress(self, job_service, job_factory):
        """Test progress updates."""
        from portal.models import JobStatus

        job = await job_factory(status=JobStatus.RUNNING)

        updated = await job_service.update_progress(
            job.id,
            phase="analyzing",
            percent=50,
            message="Halfway done"
        )

        assert updated.progress_phase == "analyzing"
        assert updated.progress_percent == 50
        assert updated.progress_message == "Halfway done"

    async def test_cancel_pending_job(self, job_service, job_factory):
        """Test cancelling a pending job."""
        from portal.models import JobStatus

        job = await job_factory(status=JobStatus.PENDING)

        updated = await job_service.cancel_job(job.id, reason="User requested")
        assert updated.status == JobStatus.CANCELLED
        assert "User requested" in (updated.error_message or "")

    async def test_cancel_running_job(self, job_service, job_factory):
        """Test cancelling a running job."""
        from portal.models import JobStatus

        job = await job_factory(status=JobStatus.RUNNING)

        updated = await job_service.cancel_job(job.id)
        assert updated.status == JobStatus.CANCELLED

    async def test_retry_job(self, job_service, job_factory):
        """Test job retry creates new job."""
        from portal.models import JobStatus

        original = await job_factory(status=JobStatus.FAILED)

        new_job = await job_service.retry_job(original.id)

        assert new_job.id != original.id
        assert new_job.parent_job_id == original.id
        assert new_job.status == JobStatus.PENDING
        assert new_job.retry_count == 1

    async def test_retry_limit(self, job_service, job_factory):
        """Test retry limit is enforced."""
        from portal.models import JobStatus
        from portal.services import InvalidJobStateError

        job = await job_factory(
            status=JobStatus.FAILED,
            retry_count=3,
            max_retries=3
        )

        with pytest.raises(InvalidJobStateError, match="exceeded max retries"):
            await job_service.retry_job(job.id)

    async def test_mark_orphaned_jobs(self, job_service, job_factory):
        """Test marking orphaned jobs."""
        from portal.models import JobStatus

        # Create some running jobs (simulating orphans)
        await job_factory(status=JobStatus.RUNNING)
        await job_factory(status=JobStatus.RUNNING)
        await job_factory(status=JobStatus.PENDING)

        count = await job_service.mark_orphaned_jobs()
        assert count == 2

    async def test_get_queued_jobs(self, job_service, job_factory):
        """Test getting pending jobs in priority order (jobs waiting to be picked up)."""
        from portal.models import JobStatus

        # Note: get_queued_jobs returns PENDING jobs (waiting to enter queue)
        await job_factory(status=JobStatus.PENDING, priority=3)
        await job_factory(status=JobStatus.PENDING, priority=1)
        await job_factory(status=JobStatus.PENDING, priority=2)
        await job_factory(status=JobStatus.RUNNING)

        jobs = await job_service.get_queued_jobs(limit=10)
        assert len(jobs) == 3
        # Should be sorted by priority (lower number = higher priority)
        assert jobs[0].priority <= jobs[1].priority <= jobs[2].priority
