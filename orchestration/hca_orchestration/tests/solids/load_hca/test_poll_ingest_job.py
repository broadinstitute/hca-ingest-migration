import unittest
from unittest.mock import Mock
from dagster import build_op_context, Failure
from data_repo_client import RepositoryApi, ApiException

from hca_manage.common import JobId
from hca_orchestration.solids.load_hca.poll_ingest_job import check_data_ingest_job_result, \
    base_check_data_ingest_job_result


class PollIngestJobTestCase(unittest.TestCase):
    def test_check_data_ingest_job_result_should_poll_jade(self):
        data_repo = Mock(spec=RepositoryApi)
        job_response = {
            "failedFiles": 0
        }
        data_repo.retrieve_job_result = Mock(return_value=job_response)

        context = build_op_context(
            resources={"data_repo_client": data_repo},
            config={}
        )

        result = check_data_ingest_job_result(context, job_id=JobId('fake_job_id'))
        self.assertTrue(result.success)

    def test_check_data_ingest_job_result_failed_files(self):
        data_repo = Mock(spec=RepositoryApi)
        job_response = {
            "failedFiles": 1
        }
        data_repo.retrieve_job_result = Mock(return_value=job_response)
        context = build_op_context(
            resources={"data_repo_client": data_repo},
            config={}
        )

        with self.assertRaises(
                Failure, msg="Bulk ingest should fail if a file fails to ingest"
        ):
            check_data_ingest_job_result(context, job_id=JobId('fake_job_id'))

    def test_check_data_ingest_job_retries_on_5xx(self):
        data_repo = Mock(spec=RepositoryApi)
        api_responses = [ApiException(status=502), {'failedFiles': 0}]
        data_repo.retrieve_job_result = Mock(side_effect=api_responses)
        context = build_op_context(
            resources={"data_repo_client": data_repo},
            config={
                'max_wait_time_seconds': 3,
                'poll_interval_seconds': 1
            }
        )

        result = base_check_data_ingest_job_result(context, job_id=JobId('fake_job_id'))
        self.assertTrue(result.success, "Poll ingest should not raise after a single 5xx")
