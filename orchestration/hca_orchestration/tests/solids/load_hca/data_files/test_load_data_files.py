from unittest.mock import Mock, MagicMock

import pytest
from dagster import build_op_context, Failure
from google.cloud.storage import Client, Blob

from data_repo_client.api import RepositoryApi
from data_repo_client.models import JobModel
from hca_orchestration.models.hca_dataset import TdrDataset
from hca_orchestration.resources.config.scratch import ScratchConfig
from hca_orchestration.solids.load_hca.data_files.load_data_files import diff_file_loads, run_bulk_file_ingest
from hca_orchestration.support.typing import HcaScratchDatasetName


@pytest.fixture
def gcs_client():
    gcs = MagicMock(spec=Client)
    gcs.list_blobs = MagicMock(
        return_value=[
            Blob(name=f'fake_blob_{i}', bucket='fake_bucket') for i in range(10)
        ]
    )
    return gcs


@pytest.fixture
def load_datafiles_test_context(gcs_client):
    return {
        "gcs": gcs_client,
        "bigquery_client": MagicMock(),
        "bigquery_service": MagicMock(),
        "target_hca_dataset": TdrDataset(
            "fake_dataset_name",
            "1234abc",
            "fake_hca_project_id",
            "fake_billing_profile_id",
            "us-fake-region"
        ),
        "scratch_config": ScratchConfig(
            "fake_bucket",
            "fake_prefix",
            "fake_bq_project",
            "fake_dataset_prefix",
            1
        ),
        "load_tag": "fake_load_tag"
    }


def test_diff_file_loads(load_datafiles_test_context):
    context = build_op_context(resources=load_datafiles_test_context)
    result = diff_file_loads(
        context,
        scratch_dataset_name=HcaScratchDatasetName("fake_bq_project.testing_dataset_prefix_fake_load_tag")
    )

    assert result.success
    assert len(result.output_values["control_file_path"]) == 10


def test_run_bulk_file_ingest_should_return_a_jade_job_id(load_datafiles_test_context):
    job_id = "fake_job_id"
    data_repo = Mock(spec=RepositoryApi)
    job_response = Mock(spec=JobModel)
    job_response.id = job_id
    data_repo.bulk_file_load = Mock(return_value=job_response)
    load_datafiles_test_context["data_repo_client"] = data_repo

    context = build_op_context(resources=load_datafiles_test_context)
    result = run_bulk_file_ingest(
        context,
        control_file_path=HcaScratchDatasetName("gs://fake/example/123.txt")
    )

    assert result.success
    assert result.output_values["result"] == job_id, f"Job ID should be {job_id}"
