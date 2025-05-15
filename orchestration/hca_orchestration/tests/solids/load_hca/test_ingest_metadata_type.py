from enum import Enum

from dagster import build_op_context
from dagster_utils.contrib.data_repo.typing import JobId

from hca_orchestration.solids.load_hca.ingest_metadata_type import ingest_metadata_type
from hca_orchestration.support.typing import HcaScratchDatasetName, MetadataType


class FakeEnum(Enum):
    FIRST = MetadataType("first")
    SECOND = MetadataType("second")
    THIRD = MetadataType("third")


FakeDatasetName = HcaScratchDatasetName("fake_dataset_name")


def test_fans_out_correctly():
    context = build_op_context(
        op_config={
            "metadata_types": FakeEnum,
            "prefix": "fakepath"
        }
    )

    result = ingest_metadata_type(
        context,
        scratch_dataset_name=FakeDatasetName,
        result=[JobId("abcdef")]
    )

    assert result.success

    expected = [e.value for e in FakeEnum]
    for i, res in enumerate(result.output_value("table_fanout_result")):
        assert expected[i] == res
