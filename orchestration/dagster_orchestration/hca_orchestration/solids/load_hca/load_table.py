import logging
from typing import Iterable

from dagster import composite_solid, solid, Nothing, OutputDefinition, Output
from dagster.core.execution.context.compute import AbstractComputeExecutionContext
from dagster_utils.contrib.data_repo.typing import JobId
from data_repo_client import RepositoryApi, JobModel
from google.cloud.bigquery import DestinationFormat
from google.cloud.bigquery.client import RowIterator

from hca_orchestration.contrib.bigquery import BigQueryService
from hca_orchestration.contrib.gcs import path_has_any_data
from hca_orchestration.resources.config.hca_dataset import TargetHcaDataset
from hca_orchestration.resources.config.scratch import ScratchConfig
from hca_orchestration.solids.data_repo import wait_for_job_completion
from hca_orchestration.solids.load_hca.poll_ingest_job import check_data_ingest_job_result, \
    check_table_ingest_job_result
from hca_orchestration.support.typing import HcaScratchDatasetName, MetadataType, MetadataTypeFanoutResult


def _diff_hca_table(
        metadata_type: MetadataType,
        metadata_path: str,
        primary_key: str,
        joined_table_name: str,
        scratch_config: ScratchConfig,
        target_hca_dataset: TargetHcaDataset,
        scratch_dataset_name: HcaScratchDatasetName,
        bigquery_service: BigQueryService

) -> None:
    datarepo_key = f"{primary_key} as datarepo_{primary_key}"
    fq_dataset_id = target_hca_dataset.fully_qualified_jade_dataset_name()

    query = f"""
    SELECT J.datarepo_row_id, S.*, {datarepo_key}
    FROM {metadata_type} S FULL JOIN `{target_hca_dataset.project_id}.{fq_dataset_id}.{metadata_type}` J
    USING ({primary_key})
    """
    destination = f"{scratch_dataset_name}.{joined_table_name}"

    source_paths = [
        f"{scratch_config.scratch_area()}/{metadata_path}/{metadata_type}/*"
    ]

    bigquery_service.build_query_job_using_external_schema(
        query,
        schema=None,
        source_paths=source_paths,
        table_name=metadata_type,
        destination=destination,
        bigquery_project=scratch_config.scratch_bq_project
    ).result()


def _query_rows_to_append(
        metadata_type: str,
        primary_key: str,
        scratch_config: ScratchConfig,
        scratch_dataset_name: HcaScratchDatasetName,
        joined_table_name: str,
        bigquery_service: BigQueryService
) -> RowIterator:
    query = f"""
    SELECT * EXCEPT (datarepo_{primary_key}, datarepo_row_id)
    FROM {scratch_dataset_name}.{joined_table_name}
    WHERE datarepo_row_id IS NULL AND {primary_key} IS NOT NULL
    """

    target_table = f"{scratch_dataset_name}.{metadata_type}_values"
    return bigquery_service.build_query_job_with_destination(
        query,
        target_table,
        scratch_config.scratch_bq_project
    ).result()


def export_data(
        operation_name: str,
        table_name_extension: str,
        metadata_type: MetadataType,
        scratch_config: ScratchConfig,
        scratch_dataset_name: HcaScratchDatasetName,
        bigquery_service: BigQueryService
) -> int:
    assert table_name_extension.startswith("_"), "Export data extension must start with _"

    source_table_name = f"{metadata_type}{table_name_extension}"
    out_path = f"{scratch_config.scratch_area()}/{operation_name}/{metadata_type}/*"

    logging.info(f"Exporting data to {out_path}")
    num_rows = bigquery_service.get_num_rows_in_table(
        source_table_name,
        scratch_dataset_name
    )
    if num_rows == 0:
        return num_rows

    bigquery_service.build_extract_job(
        source_table=source_table_name,
        out_path=out_path,
        bigquery_dataset=scratch_dataset_name,
        bigquery_project=scratch_config.scratch_bq_project,
    ).result()

    return num_rows


def _ingest_table(
        data_repo_api_client: RepositoryApi,
        target_dataset: TargetHcaDataset,
        table_name: str,
        scratch_config: ScratchConfig
) -> JobId:
    source_path = f"{scratch_config.scratch_area()}/new-rows/{table_name}/*"

    payload = {
        "format": "json",
        "ignore_unknown_values": "false",
        "max_bad_records": 0,
        "path": source_path,
        "table": table_name
    }
    job_response: JobModel = data_repo_api_client.ingest_dataset(
        id=target_dataset.dataset_id,
        ingest=payload
    )

    # todo error handling
    return JobId(job_response.id)


@solid(
    required_resource_keys={"bigquery_service", "target_hca_dataset", "scratch_config", "data_repo_client", "gcs"},
    output_defs=[
        OutputDefinition(name="no_data", is_required=False),
        OutputDefinition(name="has_data", is_required=False),
    ]
)
def check_has_data(
    context: AbstractComputeExecutionContext,
    metadata_fanout_result: MetadataTypeFanoutResult
) -> Iterable[Output]:
    scratch_config = context.resources.scratch_config
    metadata_type = metadata_fanout_result.metadata_type
    metadata_path = metadata_fanout_result.path

    source_path = f"{scratch_config.scratch_prefix_name}/{metadata_path}/{metadata_type}/"
    context.log.info(f"Checking for data to load at path {source_path}")

    if path_has_any_data(scratch_config.scratch_bucket_name, source_path, context.resources.gcs):
        context.log.info(f"{metadata_type} has data to load")
        yield Output(True, "has_data")
    else:
        context.log.info(f"{metadata_type} has no data to load")
        yield Output(False, "no_data")
    return False


@solid(
    required_resource_keys={"bigquery_service", "target_hca_dataset", "scratch_config", "data_repo_client"},
    output_defs=[
        OutputDefinition(name="no_job", is_required=False),
        OutputDefinition(name="job_id", is_required=False),
    ]
)
def start_load(
        context: AbstractComputeExecutionContext,
        has_data: bool,
        metadata_fanout_result: MetadataTypeFanoutResult
) -> Iterable[Output]:
    assert has_data, "Should not attempt to load data if no data is present"

    bigquery_service = context.resources.bigquery_service
    target_hca_dataset = context.resources.target_hca_dataset
    scratch_config = context.resources.scratch_config
    metadata_type = metadata_fanout_result.metadata_type
    metadata_path = metadata_fanout_result.path
    scratch_dataset_name = metadata_fanout_result.scratch_dataset_name
    data_repo_client = context.resources.data_repo_client

    pk = f"{metadata_type}_id"
    joined_table_name = f"{metadata_type}_joined"
    _diff_hca_table(
        metadata_type=metadata_type,
        metadata_path=metadata_path,
        primary_key=pk,
        joined_table_name=joined_table_name,
        scratch_config=scratch_config,
        target_hca_dataset=target_hca_dataset,
        scratch_dataset_name=scratch_dataset_name,
        bigquery_service=bigquery_service,

    )
    _query_rows_to_append(
        metadata_type=metadata_type,
        primary_key=pk,
        scratch_config=scratch_config,
        scratch_dataset_name=scratch_dataset_name,
        joined_table_name=joined_table_name,
        bigquery_service=bigquery_service
    )

    num_new_rows = export_data(
        operation_name="new-rows",
        table_name_extension="_values",
        metadata_type=metadata_type,
        scratch_config=scratch_config,
        scratch_dataset_name=scratch_dataset_name,
        bigquery_service=bigquery_service
    )

    if num_new_rows > 0:
        context.log.info(f"{num_new_rows} for {metadata_type}")
        job_id = _ingest_table(
            data_repo_client,
            target_hca_dataset,
            metadata_type,
            scratch_config
        )
        yield Output(job_id, "job_id")

    yield Output("no_job", "no_job")


def _get_outdated_ids(
        table_name: str,
        target_hca_dataset: TargetHcaDataset,
        scratch_config: ScratchConfig,
        scratch_dataset_name: HcaScratchDatasetName,
        outdated_ids_table_name: str,
        bigquery_service: BigQueryService
) -> None:
    fq_dataset_id = target_hca_dataset.fully_qualified_jade_dataset_name()
    jade_table = f"{target_hca_dataset.project_id}.{fq_dataset_id}.{table_name}"
    destination = f"{scratch_dataset_name}.{outdated_ids_table_name}"

    query = f"""
    WITH latest_versions AS (
        SELECT {table_name}_id, MAX(version) AS latest_version
        FROM {jade_table} GROUP BY {table_name}_id
    )
    SELECT J.datarepo_row_id FROM
        {jade_table} J JOIN latest_versions L
        ON J.{table_name}_id = L.{table_name}_id
    WHERE J.version < L.latest_version
    """

    bigquery_service.build_query_job_with_destination(
        query,
        destination,
        scratch_config.scratch_bq_project
    ).result()


def _export_outdated(
        metadata_type: MetadataType,
        outdated_ids_table_name: str,
        scratch_dataset_name: HcaScratchDatasetName,
        scratch_config: ScratchConfig,
        bigquery_service: BigQueryService
) -> None:
    out_path = f"{scratch_config.scratch_area()}/outdated-ids/{metadata_type}/*"
    bigquery_service.build_extract_job(
        source_table=outdated_ids_table_name,
        out_path=out_path,
        bigquery_dataset=scratch_dataset_name,
        bigquery_project=scratch_config.scratch_bq_project,
        output_format=DestinationFormat.CSV
    ).result()


@solid(
    required_resource_keys={"bigquery_service", "target_hca_dataset", "scratch_config", "data_repo_client", "gcs"},
    output_defs=[
        OutputDefinition(name="no_outdated", is_required=False),
        OutputDefinition(name="has_outdated", is_required=False),
    ]
)
def check_has_outdated(
        context: AbstractComputeExecutionContext,
        parent_load_job_id: JobId,
        metadata_fanout_result: MetadataTypeFanoutResult
) -> Iterable[Output]:
    assert parent_load_job_id, "Should not attempt to check for outdated rows if no parent job loaded data"

    scratch_config = context.resources.scratch_config
    metadata_type = metadata_fanout_result.metadata_type
    source_path = f"{scratch_config.scratch_prefix_name}/outdated-ids/{metadata_type}/"

    if path_has_any_data(scratch_config.scratch_bucket_name, source_path, context.resources.gcs):
        yield Output(True, "has_outdated")
    else:
        yield Output(False, "no_outdated")
    return False


@solid(
    required_resource_keys={"bigquery_service", "target_hca_dataset", "scratch_config", "data_repo_client"}
)
def clear_outdated(
        context: AbstractComputeExecutionContext,
        has_outdated: bool,
        metadata_fanout_result: MetadataTypeFanoutResult
) -> JobId:
    assert has_outdated, "Should not attempt to clear outdated rows if none are present"

    metadata_type = metadata_fanout_result.metadata_type
    bigquery_service = context.resources.bigquery_service
    target_hca_dataset = context.resources.target_hca_dataset
    scratch_config = context.resources.scratch_config
    outdated_ids_table_name = f"{metadata_type}_outdated_ids"

    _get_outdated_ids(
        table_name=metadata_type,
        target_hca_dataset=target_hca_dataset,
        scratch_config=scratch_config,
        scratch_dataset_name=metadata_fanout_result.scratch_dataset_name,
        outdated_ids_table_name=outdated_ids_table_name,
        bigquery_service=bigquery_service
    )
    _export_outdated(
        metadata_type=metadata_type,
        outdated_ids_table_name=outdated_ids_table_name,
        scratch_dataset_name=metadata_fanout_result.scratch_dataset_name,
        scratch_config=scratch_config,
        bigquery_service=bigquery_service
    )
    job_id: JobId = _soft_delete_outdated(
        data_repo_api_client=context.resources.data_repo_client,
        target_dataset=target_hca_dataset,
        table_name=metadata_type,
        scratch_config=scratch_config
    )
    return job_id


def _soft_delete_outdated(
        data_repo_api_client: RepositoryApi,
        target_dataset: TargetHcaDataset,
        table_name: str,
        scratch_config: ScratchConfig
) -> JobId:
    outdated_ids_path = f"{scratch_config.scratch_area()}/outdated-ids/{table_name}/*"
    payload = {
        "deleteType": "soft",
        "specType": "gcsFile",
        "tables": [
            {
                "gcsFileSpec": {
                    "fileType": "csv",
                    "path": outdated_ids_path
                },
                "tableName": table_name
            }
        ]
    }

    job_response: JobModel = data_repo_api_client.apply_dataset_data_deletion(
        id=target_dataset.dataset_id,
        data_deletion_request=payload
    )
    return JobId(job_response.id)


@composite_solid
def load_table(metadata_fanout_result: MetadataTypeFanoutResult) -> Nothing:
    """
    Composite solid that knows how to load a metadata table
    """

    # these jobs return two values, to reflect whether data was loaded in each step
    # dagster will not dispatch downstream solids if the needed "data was loaded"
    # output is never returned, hence we have conditional branching
    no_data, has_data = check_has_data(metadata_fanout_result)
    no_job, job_id = start_load(has_data, metadata_fanout_result)

    # skip checking for outdated if a "load job id" was never returned (i.e., we loaded
    # no data, so there is no possibility of outdated rows)
    no_outdated, has_outdated = check_has_outdated(
        check_table_ingest_job_result(wait_for_job_completion(job_id)),
        metadata_fanout_result
    )
    check_data_ingest_job_result(
        wait_for_job_completion(
            clear_outdated(has_outdated, metadata_fanout_result)
        )
    )
