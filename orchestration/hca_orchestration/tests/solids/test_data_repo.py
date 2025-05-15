import unittest
from unittest.mock import Mock

from dagster import build_op_context, Failure
from data_repo_client import RepositoryApi
from hca_manage.common import JobId
from hca_orchestration.solids.data_repo import base_wait_for_job_completion


def mock_job_status(completed: bool, successful: bool = True) -> Mock:
    fake_job_status = Mock()
    if completed:
        fake_job_status.completed = "2001-01-01 00:00:00"
        fake_job_status.job_status = "succeeded" if successful else "failed"
    else:
        fake_job_status.completed = None
        fake_job_status.job_status = "running"

    return fake_job_status


data_repo = Mock(spec=RepositoryApi)


class WaitForJobCompletionTestCase(unittest.TestCase):
    def test_polls_repeatedly_until_complete(self):
        job_status_sequence = [
            mock_job_status(False),
            mock_job_status(False),
            mock_job_status(True)
        ]

        data_repo.retrieve_job = Mock(side_effect=job_status_sequence)

        context = build_op_context(
            resources={"data_repo_client": data_repo},
            op_config={
                'poll_interval_seconds': 0,
                'max_wait_time_seconds': 10,
            }
        )

        result = base_wait_for_job_completion(context, job_id=JobId('steve-was-here'))
        self.assertTrue(result.success)
        self.assertEqual(data_repo.retrieve_job.call_count, 3)

    def test_fails_if_job_failed(self):
        data_repo.retrieve_job = Mock(return_value=mock_job_status(completed=True, successful=False))

        context = build_op_context(
            resources={"data_repo_client": data_repo},
            op_config={
                'poll_interval_seconds': 0,
                'max_wait_time_seconds': 10,
            }
        )

        with self.assertRaisesRegex(Failure, f"job_id test_job did not complete successfully."):
            base_wait_for_job_completion(context, job_id=JobId('test_job'))

    def test_fails_if_max_time_exceeded(self):
        data_repo.retrieve_job = Mock(return_value=mock_job_status(False))

        context = build_op_context(
            resources={"data_repo_client": data_repo},
            op_config={
                'poll_interval_seconds': 0,
                'max_wait_time_seconds': 1,
            }
        )

        with self.assertRaisesRegex(Failure, "Exceeded max wait time"):
            base_wait_for_job_completion(context, job_id=JobId('steve-was-here'))
