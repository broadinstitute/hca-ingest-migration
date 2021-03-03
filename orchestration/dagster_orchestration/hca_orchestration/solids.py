from dagster import solid, InputDefinition, Nothing, String, DagsterType
from hca_utils.utils import HcaUtils, ProblemCount

DagsterProblemCount = DagsterType(
    name="DagsterProblemCount",
    type_check_fn=lambda _, value: isinstance(value, ProblemCount),
    description="A simple named tuple to represent the different types of issues present from the post process validation.",
)


@solid(
    required_resource_keys={"storage_client"},
    config_schema={
        "staging_bucket_name": String,
        "staging_prefix_name": String,
    },
)
def clear_staging_dir(context) -> int:
    """
    Given a staging bucket + prefix, deletes all blobs present at that path
    :return: Number of deletions
    """

    staging_bucket_name = context.solid_config["staging_bucket_name"]
    staging_prefix_name = context.solid_config["staging_prefix_name"]

    blobs = context.resources.storage_client.list_blobs(staging_bucket_name, prefix=f"{staging_prefix_name}/")
    deletions_count = 0
    for blob in blobs:
        blob.delete()
        deletions_count += 1
    context.log.debug(f"--clear_staging_dir found {deletions_count} blobs to delete under {staging_prefix_name}")
    return deletions_count


@solid(
    required_resource_keys={"beam_runner"},
    config_schema={
        "input_prefix": String,
        "output_prefix": String,
    },
    input_defs=[InputDefinition("start", Nothing)],
)
def pre_process_metadata(context) -> Nothing:
    """
    Runs the Beam hca transformation pipeline flow over the given input prefix
    """
    context.log.info("--pre_process_metadata")

    context.resources.beam_runner.run(
        "pre-process-metadata",
        context.solid_config["input_prefix"],
        context.solid_config["output_prefix"],
        context
    )


@solid(
    required_resource_keys={"data_repo_client"},
    input_defs=[InputDefinition("start", Nothing)]
)
def submit_file_ingest(context) -> Nothing:
    """
    This will submit a dataset for ingestion to the data repo
    TODO This is a noop for now
    """
    datasets = context.resources.data_repo_client.enumerate_datasets()
    context.log.debug(f"Enumerate found {datasets.total} datasets in the repo")


@solid(
    config_schema={
        "gcp_env": String,
        "google_project_name": String,
        "dataset_name": String,
    }
)
def post_import_validate(context) -> DagsterProblemCount:
    """
    Checks if the target dataset has any rows with duplicate IDs or null file references.
    """
    validator = HcaUtils(
        context.solid_config["gcp_env"],
        context.solid_config["google_project_name"],
        context.solid_config["dataset_name"],
        context.resources.data_repo_client)
    return validator.check_for_all()