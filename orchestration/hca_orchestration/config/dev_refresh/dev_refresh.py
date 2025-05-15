"""
Defines partitioning logic for the Q3 2021 dev refresh
"""

import dagster as dg
from dagster_utils.typing import DagsterObjectConfigSchema


def run_config_for_cut_snapshot_partition(partition_key:str) -> DagsterObjectConfigSchema:  # type: ignore
    run_config = {
        "solids": {
            "add_steward": {
                "config": {
                    "snapshot_steward": "monster-dev@dev.test.firecloud.org"
                }
            }
        },
        "resources": {
            "snapshot_config": {
                "config": {
                    "source_hca_project_id": partition_key,
                    "managed_access": False,
                }
            }
        }
    }

    return run_config
