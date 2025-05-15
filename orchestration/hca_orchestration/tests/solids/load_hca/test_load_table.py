import pytest
from unittest.mock import Mock
from dagster import build_op_context
from dagster_utils.contrib.data_repo.typing import JobId
from google.cloud.storage import Client, Blob

from hca_orchestration.contrib.bigquery import BigQueryService
from hca_orchestration.contrib.data_repo.data_repo_service import DataRepoService
from hca_orchestration.models.hca_dataset import TdrDataset
from hca_orchestration.models.scratch import ScratchConfig
from hca_orchestration.solids.load_hca.load_table import load_table_op, clear_outdated
from hca_orchestration.support.typing import HcaScratchDatasetName, MetadataType, MetadataTypeFanoutResult
from hca_orchestration.tests.support.gcs import FakeGCSClient, FakeGoogleBucket, HexBlobInfo


@pytest.fixture
def scratch_config():
    return ScratchConfig("my-fake-bucket", "fake_prefix", "fake", "fake", 123)


@pytest.fixture
def target_dataset():
    return TdrDataset("fake", "fake", "fake", "fake", "fake")

@pytest.fixture
def data_repo_service():
    return Mock(spec=DataRepoService)

@pytest.fixture
def metadata_fanout_result():
    return MetadataTypeFanoutResult(
        scratch_dataset_name=HcaScratchDatasetName("dataset"),
        metadata_type=MetadataType("metadata"),
        path="path"
    )

@pytest.fixture
def bigquery_service():
    service = Mock(spec=BigQueryService)
    service.get_num_rows_in_table = Mock(return_value=0)
    return service


@pytest.fixture
def context_factory(scratch_config, target_dataset):
    def _create_context(bigquery_service, run_config, data_repo_service):
        return build_op_context(
            resources={
                "bigquery_service": bigquery_service,
                "scratch_config": scratch_config,
                "target_hca_dataset": target_dataset,
                "data_repo_service": data_repo_service,
            },
            config=run_config,
        )
    return _create_context

def test_load_table(metadata_fanout_result, run_config, data_repo_service, context_factory):
    context = context_factory(bigquery_service, run_config, data_repo_service)
    result = load_table_op(context, metadata_fanout_result=metadata_fanout_result)

    assert result.success


def test_clear_outdated(data_repo_service):
    scratch_config_to_clear = ScratchConfig(
        "fake_scratch_bucket",
        "fake_scratch_prefix",
        "fake_bq_project",
        "fake_scratch_dataset_prefix",
        0
    )
    target_hca_dataset_to_clear = TdrDataset(
        "fake_target_dataset_name",
        "1234abc",
        "fake_target_bq_project_id",
        "fake_billing_profile_id",
        "fake_location"
    )

    gcs = Mock(spec=Client)
    blob = Mock(spec=Blob)
    blob.size = 1
    gcs.list_blobs = Mock(return_value=[blob])

    job_id = clear_outdated(
        scratch_config_to_clear,
        target_hca_dataset_to_clear,
        MetadataType("sequence_file"),
        Mock(spec=BigQueryService),
        data_repo_service,
        gcs
    )

    assert job_id == "fake_delete_job_id"


def test_load_table_yes_new_rows(metadata_fanout_result, run_config, data_repo_service, context_factory):
    def _mock_bq_service():
        svc = Mock(spec=BigQueryService)
        svc.get_num_rows_in_table = Mock(return_value=1)
        return svc

    bigquery_service = _mock_bq_service()
    context = context_factory(bigquery_service, run_config, data_repo_service)

    result = load_table_op(context, metadata_fanout_result=metadata_fanout_result)
    assert result.success
    assert result.output_value("result") == "fake_delete_job_id"


def test_load_table_no_new_rows(metadata_fanout_result, run_config, data_repo_service, context_factory):
    context = context_factory(bigquery_service, run_config, data_repo_service)
    result = load_table_op(context, metadata_fanout_result=metadata_fanout_result)
    assert result.success
    assert result.output_value("result") is None
