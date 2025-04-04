import os

from dagster import Partition, file_relative_path
from dagster.utils import load_yaml_from_path
from dagster_utils.typing import DagsterObjectConfigSchema


def run_config_per_project_snapshot_job(partition: Partition[str]) -> DagsterObjectConfigSchema:
    path = file_relative_path(
        __file__, os.path.join("./run_config", "per_project_snapshot.yaml")
    )
    # jsdcp:ignore-start
    run_config: DagsterObjectConfigSchema = load_yaml_from_path(path)  # type: ignore

    # we bake the release tag into the uploaded partitions csv (i.e, <uuid>,<release tag>)
    project_id, release_tag = partition.value.split(',')
    run_config["resources"]["snapshot_config"]["config"]["source_hca_project_id"] = project_id
    run_config["resources"]["snapshot_config"]["config"]["qualifier"] = release_tag
    # jscpd:ignore-end
    return run_config


# for dev releases - uses dev config
# Definitely hacky and very not dry - but this is all going away, and it's how it was done before
def run_config_per_project_snapshot_job_dev(partition: Partition) -> DagsterObjectConfigSchema:
    path = file_relative_path(
        __file__, os.path.join("./run_config", "per_project_snapshot_dev.yaml")
    )
    # jscpd:ignore-start
    run_config: DagsterObjectConfigSchema = load_yaml_from_path(path)

    # we bake the release tag into the uploaded partitions csv (i.e, <uuid>,<release tag>)
    project_id, release_tag = partition.value.split(',')
    run_config["resources"]["snapshot_config"]["config"]["source_hca_project_id"] = project_id
    run_config["resources"]["snapshot_config"]["config"]["qualifier"] = release_tag
    # jscpd:ignore-end

    return run_config
