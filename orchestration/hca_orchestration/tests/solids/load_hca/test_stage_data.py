from unittest.mock import MagicMock

import pytest
from dagster import build_op_context, Failure
from dagster_utils.resources.beam.local_beam_runner import LocalBeamRunner
from google.api.resource_pb2 import resource_reference
from google.cloud.bigquery import Client

from hca_orchestration.solids.load_hca.stage_data import clear_scratch_dir, pre_process_metadata, create_scratch_dataset
from hca_orchestration.tests.support.gcs import FakeGCSClient, FakeGoogleBucket, HexBlobInfo
from hca_orchestration.models.scratch import ScratchConfig
from hca_orchestration.models.hca_dataset import TdrDataset


@pytest.fixture
def beam_runner():
    return MagicMock(LocalBeamRunner)


@pytest.fixture
def bigquery_client():
    return MagicMock(Client)


@pytest.fixture
def testing_resource_context(beam_runner, bigquery_client):
    scratch_config = ScratchConfig(
        scratch_bucket_name="fake-bucket",
        scratch_prefix_name="fake-prefix",
        scratch_bq_project="bq_project",
        scratch_dataset_prefix="dataset_prefix",
        scratch_table_expiration_ms=86400000
    )
    test_bucket = FakeGoogleBucket(
        {f"gs://{scratch_config.scratch_bucket_name}/{scratch_config.scratch_prefix_name}":
            HexBlobInfo(hex_md5="b2d6ec45472467c836f253bd170182c7", content="test content")}
    )

    return {
            "beam_runner": beam_runner,
            "gcs": FakeGCSClient(buckets={scratch_config.scratch_bucket_name: test_bucket}
            ),
            "scratch_config": scratch_config,
            "bigquery_client": bigquery_client,
            "load_tag": "fake_load_tag",
            "target_hca_dataset":TdrDataset("fake", "fake", "fake", "fake", "fake")
        }


def test_clear_scratch_dir(testing_resource_context):
    context = build_op_context(resources=testing_resource_context)
    result = clear_scratch_dir(context)

    assert result.success
    assert result == 1


def test_pre_process_metadata(testing_resource_context, beam_runner):
    context = build_op_context(
        resources=testing_resource_context,
        config={
            "input_prefix": "gs://foobar/example"
        }
    )
    result = pre_process_metadata(context)

    assert result.success
    assert beam_runner.run.called_once()


def test_pre_process_metadata_fails_with_non_gs_path(testing_resource_context):
    context = build_op_context(
        resources=testing_resource_context,
        config={
            "input_prefix": "input_prefix"
        }
    )
    with pytest.raises(Failure, match="must start with gs"):
        pre_process_metadata(context)


def test_pre_process_metadata_fails_with_trailing_slash(testing_resource_context):
    context = build_op_context(
        resources=testing_resource_context,
        config={
            "input_prefix": "gs://example/"
        }
    )
    with pytest.raises(Failure, match="must not end with trailing slash"):
        pre_process_metadata(context)


def test_create_scratch_dataset(testing_resource_context, bigquery_client):
    context = build_op_context(resources=testing_resource_context)
    result = create_scratch_dataset(context)

    assert result.success
    assert bigquery_client.create_dataset.called_once()
