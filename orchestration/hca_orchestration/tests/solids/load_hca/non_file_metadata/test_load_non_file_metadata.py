from unittest.mock import MagicMock

import pytest
from dagster import build_op_context
from dagster_utils.contrib.data_repo.typing import JobId

from hca_orchestration.solids.load_hca.non_file_metadata.load_non_file_metadata import non_file_metadata_fanout
from hca_orchestration.support.typing import HcaScratchDatasetName
from hca_orchestration.models.hca_dataset import TdrDataset
from hca_orchestration.models.scratch import ScratchConfig


@pytest.fixture
def testing_resource_context():
    return {
        "scratch_config": ScratchConfig(
            scratch_bucket_name="bucket_name",
            scratch_bq_project="bq_project",
            scratch_dataset_prefix="dataset_prefix",
            scratch_table_expiration_ms=86400000
        ),
        "gcs": MagicMock(),
        "target_hca_dataset": TdrDataset("fake", "dataset_id", "fake", "fake", "fake"),
        "bigquery_service": MagicMock(),
        "data_repo_service": MagicMock(),
    }


def test_non_file_metadata_fanout(testing_resource_context):
    context = build_op_context(resources=testing_resource_context)
    result = non_file_metadata_fanout(
        context,
        result=[JobId("abcdef")],
        scratch_dataset_name=HcaScratchDatasetName("dataset")
    )

    assert result.success
