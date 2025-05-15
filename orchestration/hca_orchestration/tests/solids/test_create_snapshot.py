from unittest.mock import Mock, patch
from dagster import build_op_context
from dagster_utils.resources.sam import Sam
from data_repo_client import RepositoryApi
from hca_manage.common import JobId
from hca_orchestration.contrib.data_repo.data_repo_service import DataRepoService
from hca_orchestration.resources.config.data_repo import (
    HcaManageConfig,
    SnapshotCreationConfig,
)
from hca_orchestration.solids.create_snapshot import (
    make_snapshot_public,
    submit_snapshot_job,
)


def test_submit_snapshot_job_calls_submit_snapshot_job_in_hca_manage():
    with patch('hca_manage.snapshot.SnapshotManager.submit_snapshot_request_with_name',
               return_value=JobId("abcde")) as submit_snap:
        context = build_op_context(
            resources={
                "data_repo_client": Mock(spec=RepositoryApi),
                "data_repo_service": Mock(spec=DataRepoService),
                "sam_client": Mock(spec=Sam),
                "snapshot_config": SnapshotCreationConfig("fake", "fake", "fake", False),
                "hca_manage_config": HcaManageConfig("dev", "fake"),
            },
            op_config={
                'billing_profile_id': "fake_billing_profile_id"
            }
        )
        result = submit_snapshot_job(context)
        assert result.success
        assert result.output_value() == JobId('abcde')
        submit_snap.assert_called_once_with('fake', False, True)


def test_make_snapshot_public_hits_correct_sam_path():
    sam_client = Mock(Sam)
    context = build_op_context(
        resources= {"sam_client": sam_client},
    )
    result = make_snapshot_public(context, snapshot_id='steve')
    assert result.success
    # assert result is None # TODO - cleanup note: The function does actually return the snapshot id...
    sam_client.set_public_flag.assert_called_once_with('steve', True)
