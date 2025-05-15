import logging
import os
import uuid
import dagster as dg
from typing import Callable, Optional
from dagster_utils.typing import DagsterObjectConfigSchema
from google.cloud.storage import Client

# T = TypeVar("T") # TODO - remove this ?

def get_partition_keys_from_gcs(gs_partitions_bucket_name: str, pipeline_name: str, gs_client: Client,
                                run_config_fn_for_partition: Callable[[str], DagsterObjectConfigSchema]) -> list[str]:
    """
    Reads partition keys from CSV files in a GCS bucket, interpreting each line as a separate partition.

    Files must end with a ".csv" extension; the filename prefix becomes the name of the partition.
    For example:

    foo_partitions.csv

    will create a partition named "foo_partitions"
    :param gs_partitions_bucket_name: path to the GCS bucket with the partition files
    :param pipeline_name: name of the pipeline to which the partitions belong
    :param gs_client: Google Cloud Storage client
    :param run_config_fn_for_partition: function to generate run config for each partition
    :return: list of partition keys
    """
    blobs = gs_client.list_blobs(gs_partitions_bucket_name, prefix=pipeline_name)
    partition_keys = []

    for blob in blobs:
        if not blob.name.endswith(".csv"):
            logging.info(f"Blob at {blob.name} is not a CSV, ignoring.")
            continue

        with blob.open("r") as partition_file_handle:
            keys = [line.strip() for line in partition_file_handle.readlines()]
            partition_keys.extend(keys)

    return partition_keys


def configure_partitions_for_pipeline(pipeline_name: str, config_fn: Callable[[str], DagsterObjectConfigSchema]) -> dg.StaticPartitionsDefinition:
    """
    Configures partitions for a pipeline using dg.DynamicPartitionsDefinition.
    """
    dynamic_partitions = dg.DynamicPartitionsDefinition(name=f"{pipeline_name}_dynamic_partitions")
    partitions_path = os.environ.get("PARTITIONS_BUCKET", "")
    if not partitions_path:
        logging.warning(f"PARTITIONS_BUCKET not set, skipping partitioning for pipeline {pipeline_name}")
        return dg.StaticPartitionsDefinition(partition_keys=[])

    gs_client = Client()
    partition_keys = get_partition_keys_from_gcs(partitions_path, pipeline_name, gs_client, config_fn)
    logging.warning(f"Found partitions for pipeline {pipeline_name}: {partition_keys}")

    # Dynamically add partition keys (partition keys replace partition sets from pre Dagster 1.0
    dynamic_partitions.add_partitions(partition_keys)
    return dynamic_partitions

# TODO - this probably shouldn't be in here
def short_run_id(run_id: Optional[str]) -> str:
    if not run_id:
        run_id = uuid.uuid4().hex
    tag = f"{run_id[0:8]}"
    return tag
