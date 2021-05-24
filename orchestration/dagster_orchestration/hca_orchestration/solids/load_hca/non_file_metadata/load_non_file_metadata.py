from enum import Enum

from dagster import composite_solid, configured, Nothing

from hca_orchestration.solids.load_hca.load_table import load_table
from hca_orchestration.solids.load_hca.ingest_metadata_type import ingest_metadata_type
from hca_orchestration.support.typing import HcaScratchDatasetName, MetadataType


class NonFileMetadataTypes(Enum):
    """
    This Enum captures MetadataTypes that are not directly describing a file type in the HCA
    """
    AGGREGATE_GENERATION_PROTOCOL = MetadataType("aggregate_generation_protocol")
    ANALYSIS_PROCESS = MetadataType("analysis_process")
    ANALYSIS_PROTOCOL = MetadataType("analysis_protocol")
    CELL_LINE = MetadataType("cell_line")
    CELL_SUSPENSION = MetadataType("cell_suspension")
    COLLECTION_PROTOCOL = MetadataType("collection_protocol")
    DIFFERENTIATION_PROTOCOL = MetadataType("differentiation_protocol")
    DISSOCIATION_PROTOCOL = MetadataType("dissociation_protocol")
    DONOR_ORGANISM = MetadataType("donor_organism")
    ENRICHMENT_PROTOCOL = MetadataType("enrichment_protocol")
    IMAGED_SPECIMEN = MetadataType("imaged_specimen")
    IMAGING_PREPARATION_PROTOCOL = MetadataType("imaging_preparation_protocol")
    IMAGING_PROTOCOL = MetadataType("imaging_protocol")
    IPSC_INDUCTION_PROTOCOL = MetadataType("ipsc_induction_protocol")
    LIBRARY_PREPARATION_PROTOCOL = MetadataType("library_preparation_protocol")
    ORGANOID = MetadataType("organoid")
    PROCESS = MetadataType("process")
    PROJECT = MetadataType("project")
    PROTOCOL = MetadataType("protocol")
    SEQUENCING_PROTOCOL = MetadataType("sequencing_protocol")
    SPECIMEN_FROM_ORGANISM = MetadataType("specimen_from_organism")
    LINKS = MetadataType("links")


ingest_non_file_metadata_type = configured(ingest_metadata_type, name="ingest_non_file_metadata_type")(
    {"metadata_types": NonFileMetadataTypes})


@composite_solid
def non_file_metadata_fanout(scratch_dataset_name: HcaScratchDatasetName) -> Nothing:
    ingest_non_file_metadata_type(scratch_dataset_name).map(load_table)