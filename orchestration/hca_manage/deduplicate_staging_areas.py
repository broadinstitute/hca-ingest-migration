"""Outputs contents of up to two GCS paths, comparing if multiple paths are specified. 

Usage:
    > python3 deduplicate_staging_areas.py -s STAGING_AREA_PATH [--print_files] [--skip_deletion]"""

# Imports
import os
import re
import argparse
from google.cloud import storage
import pandas as pd

# Function to return the objects in a staging area bucket
def get_staging_area_objects(bucket_name, prefix, delimiter=None):
    record_list = []
    try:
        # List blobs in specified bucket/prefix
        storage_client = storage.Client()
        blobs = storage_client.list_blobs(bucket_name, prefix=prefix, delimiter=delimiter)

        # Parse blobs and return a list of records
        for blob in blobs:
            if prefix + "data/" not in blob.name:
                obj = blob.name
                path = os.path.split(blob.name)[0]
                entity = os.path.split(blob.name)[1].split("_")[0]
                version = os.path.split(blob.name)[1].split("_")[1]
                record = [obj, path, entity, version]
                record_list.append(record)
        return record_list
    except Exception as e:
        print(f"Error retrieving objects from staging area: {str(e)}")
        return record_list

# Function to identify outdated entity files
def identify_outdated_files(record_list):
    delete_list = []
    if record_list:  
        # Load records into dataframe, group by path and entity, and order by version descending
        df = pd.DataFrame(record_list, columns = ["blob", "path", "entity", "version"])
        df["rn"] = df.groupby(["path", "entity"])["version"].rank(method="first", ascending=False)

        # Identify outdated records and return as a list
        df_outdated = df[df["rn"] != 1]
        for index, row in df_outdated.iterrows():
            delete_list.append(row["blob"])
    return delete_list

# Function to batch delete files
def batch_delete_files(delete_list, bucket_name, prefix, delimiter=None):
    if delete_list:
        try:
            # Loop through and submit batch deletion requests (max 1000)
            deleted_list = []
            while True:

                # List blobs in specified bucket/prefix
                storage_client = storage.Client()
                blobs = storage_client.list_blobs(bucket_name, prefix=prefix, delimiter=delimiter)

                # Loop through blobs and delete those found on the delete list
                iterator = 0
                with storage_client.batch():
                    for blob in blobs:
                        if blob.name in delete_list and blob.name not in deleted_list and iterator < 1000:
                            iterator += 1
                            deleted_list.append(blob.name)
                            blob.delete()

                # If all objects deleted, exit loop
                if len(deleted_list) == len(delete_list):
                    break
            print("Objects deleted successfully.")
        except Exception as e:
            print(f"Error deleting objects: {str(e)}")

#  Main function
if __name__ == "__main__":

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Remove outdated entity files from HCA staging area.")
    parser.add_argument("-s", "--staging_area", required=True, type=str, help="Full GCS path to the staging area of interest.")
    parser.add_argument("-p", "--print_files", required=False, action="store_true", help="Add argument to print files to be removed.", default=False)
    parser.add_argument("-n", "--skip_deletion", required=False, action="store_true", help="Add argument to skip file deltion.", default=False)
    args = parser.parse_args()

    # Initialize variables
    bucket_name = re.match("gs:\/\/([a-z0-9\-_]+)\/", args.staging_area).group(1)
    prefix = re.match("gs:\/\/[a-z0-9\-_]+\/([A-Za-z0-9\-_\/\.]+)", args.staging_area).group(1)
    if prefix[-1] != "/":
        prefix += "/"

    # Call functions to identify and remove outdated entity files
    print(f"Evaluating outdated files in staging area: {args.staging_area}")
    objects_list = get_staging_area_objects(bucket_name, prefix)
    print(f"\t- Total objects found: {len(objects_list)}")
    delete_list = identify_outdated_files(objects_list)
    print(f"\t- Outdated objects found: {len(delete_list)}")
    if args.print_files:
        print("\t- Outdated object list: \n\t\t- " + "\n\t\t- ".join(delete_list))
    if not args.skip_deletion:
        batch_delete_files(delete_list, bucket_name, prefix)