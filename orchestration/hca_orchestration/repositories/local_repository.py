"""
Pipelines here are intended to be run in a local context on a developer's box
"""

import dagster as dg
from dagster_gcp.gcs import gcs_pickle_io_manager
from dagster_utils.resources.beam.local_beam_runner import local_beam_runner
from dagster_utils.resources.bigquery import bigquery_client
from dagster_utils.resources.data_repo.jade_data_repo import jade_data_repo_client
from dagster_utils.resources.google_storage import google_storage_client
from dagster_utils.resources.slack import console_slack_client
from hca_orchestration.config import preconfigure_resource_for_mode
from hca_orchestration.config.dcp_release.dcp_release import (
    run_config_for_dcp_release_partition,
)
from hca_orchestration.config.dev_refresh.dev_refresh import (
    run_config_for_cut_snapshot_partition,
)
from hca_orchestration.contrib.dagster import configure_partitions_for_pipeline
from hca_orchestration.pipelines.cut_snapshot import (
    cut_project_snapshot_job,
    legacy_cut_snapshot_job,
)
from hca_orchestration.pipelines.load_hca import load_hca
from hca_orchestration.pipelines.validate_ingress import (
    run_config_for_validation_ingress_partition,
    staging_area_validator,
    validate_ingress_graph,
)
from hca_orchestration.resources import bigquery_service, load_tag
from hca_orchestration.resources.config.dagit import dagit_config
from hca_orchestration.resources.config.datasets import passthrough_hca_dataset
from hca_orchestration.resources.config.scratch import scratch_config
from hca_orchestration.resources.data_repo_service import data_repo_service


@dg.job(resource_defs={
    "slack": console_slack_client,
    "staging_area_validator": staging_area_validator,
    "gcs": google_storage_client
})
def validate_ingress_job():
    validate_ingress_graph()


@dg.job(resource_defs={
    "beam_runner": local_beam_runner,
    "bigquery_client": bigquery_client,
    "data_repo_client": preconfigure_resource_for_mode(jade_data_repo_client, "dev"),
    "gcs": google_storage_client,
    "io_manager": preconfigure_resource_for_mode(gcs_pickle_io_manager, "dev"),
    "load_tag": load_tag,
    "scratch_config": scratch_config,
    "target_hca_dataset": passthrough_hca_dataset,
    "bigquery_service": bigquery_service,
    "data_repo_service": data_repo_service,
    "slack": console_slack_client,
    "dagit_config": preconfigure_resource_for_mode(dagit_config, "local")
},
    executor_def=dg.in_process_executor
)
def load_hca_job():
    load_hca()


defs = dg.Definitions(
    jobs=[cut_project_snapshot_job("dev", "dev", "monster-dev@dev.test.firecloud.org"),
          legacy_cut_snapshot_job("dev", "monster-dev@dev.test.firecloud.org"),
          load_hca_job(),
          validate_ingress_job(),
          *configure_partitions_for_pipeline("cut_snapshot", run_config_for_cut_snapshot_partition),
          *configure_partitions_for_pipeline("load_hca", run_config_for_dcp_release_partition),
          *configure_partitions_for_pipeline("validate_ingress", run_config_for_validation_ingress_partition),
          ]
)
