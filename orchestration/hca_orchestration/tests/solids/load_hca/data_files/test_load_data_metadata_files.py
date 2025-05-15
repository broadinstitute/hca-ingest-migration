from unittest.mock import MagicMock

import pytest
from dagster import build_op_context, Failure
from dagster_utils.contrib.data_repo.typing import JobId
from data_repo_client import RepositoryApi
from google.cloud.storage import Client

from hca_orchestration.contrib.bigquery import BigQueryService
from hca_orchestration.contrib.data_repo.data_repo_service import DataRepoService
from hca_orchestration.models.hca_dataset import TdrDataset
from hca_orchestration.models.scratch import ScratchConfig
from hca_orchestration.solids.load_hca.data_files.load_data_metadata_files import inject_file_ids_solid, \
    file_metadata_fanout
from hca_orchestration.support.typing import HcaScratchDatasetName, MetadataType, MetadataTypeFanoutResult


@pytest.fixture
def testing_resource_context():
    return {
        "scratch_config": ScratchConfig("fake", "fake", "fake", "fake", 123),
        "bigquery_service": MagicMock(spec=BigQueryService),
        "data_repo_client": MagicMock(spec=RepositoryApi),
        "target_hca_dataset": TdrDataset("fake", "fake", "fake", "fake", "fake"),
        "data_repo_service": MagicMock(spec=DataRepoService),
        "gcs": MagicMock(spec=Client)
    }


def test_ingest_metadata_for_file_type(testing_resource_context):
    metadata_fanout_result = MetadataTypeFanoutResult(
        scratch_dataset_name=HcaScratchDatasetName("dataset"),
        metadata_type=MetadataType("metadata"),
        path="path"
    )

    context = build_op_context(resources=testing_resource_context)
    result = inject_file_ids_solid(
        context,
        file_metadata_fanout_result=metadata_fanout_result
    )

    assert result.success


def test_file_metadata_fanout(testing_resource_context):
    context = build_op_context(resources=testing_resource_context)
    result = file_metadata_fanout(
        context,
        result=[JobId("abcdef")],
        scratch_dataset_name=HcaScratchDatasetName("dataset")
    )

    assert result.success
