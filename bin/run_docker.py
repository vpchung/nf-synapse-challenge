#!/usr/bin/env python3
"""
This module runs the docker container and outputs relevant log messages into a log file
which then gets stored on Synapse under its corresponding log folder.

This module recycles functionality seen here:
https://github.com/Sage-Bionetworks-Challenges/model-to-data-challenge-workflow/blob/82ff3dc0ea8b83d727a7fbecf9550efdc010eadd/run_docker.py
"""

import os
import sys
from typing import Optional, Union

import docker
import synapseclient

from create_folders import create_folders


def get_submission_image(syn: synapseclient.Synapse, submission_id: str) -> str:
    """
    Retrieves Docker Image ID from submission

    Arguments:
        submission_id: Submission ID to be queried

    Returns:
        image_id: Docker image identifier in the format: '<image_name>@<sha_code>'

    Raises:
        ValueError: If submission has no associated Docker image

    """
    submission = syn.getSubmission(submission_id)
    docker_repository = submission.get("dockerRepositoryName", None)
    docker_digest = submission.get("dockerDigest", None)
    if not docker_digest or not docker_repository:
        raise ValueError(f"Submission {submission_id} has no associated Docker image.")
    image_id = f"{docker_repository}@{docker_digest}"

    return image_id


def create_log_file(
    log_filename: str, log_text: Optional[Union[str, bytes]] = None
) -> None:
    """
    Creates the Docker submission execution log file.

    This function creates a log file with the given name and writes the given text to it.
    If no text is given, it writes "No Logs" to the file.

    Arguments:
        log_filename: The name of the log file to create
        log_text: The text to write to the log file. If given as a byte string,
                  it will be decoded as UTF-8 before being written.
    """
    with open(log_filename, "w", encoding="ascii", errors="ignore") as log_file:
        if log_text is not None:
            if isinstance(log_text, bytes):
                log_text = log_text.decode("utf-8")
            log_file.write(log_text)
        else:
            log_file.write("No Logs")


def store_log_file(
    syn: Union[None, synapseclient.Synapse],
    project: str,
    log_filename: str,
    submission_id: str,
) -> None:
    """
    Store the Docker submission execution log file on Synapse.

    This function stores the given log file on Synapse under the corresponding log folder
    for the given submission.

    Arguments:
        project: The name of the Synapse project to store the log file in
        log_filename: The name of the log file to store
        submission_id: The ID of the submission to store the log file for
    """
    statinfo = os.stat(log_filename)
    if statinfo.st_size > 0:
        create_folders(
            project_name=project,
            submission_id=submission_id,
            create_or_update="update",
            predictions_file=None,
            log_file=log_filename,
            syn=syn,
        )


def store_predictions_file(
    syn: Union[None, synapseclient.Synapse],
    project: str,
    predictions_filename: str,
    submission_id: str,
) -> None:
    """
    Store predictions file on Synapse

    This function stores the given predictions file on Synapse under the
    corresponding predictions folder for the given submission.

    Arguments:
        project: The name of the Synapse project to store the predictions file in
        predictions_filename: The name of the predictions file to store
        submission_id: The ID of the submission to store the predictions file for
    """
    statinfo = os.stat(predictions_filename)
    if statinfo.st_size > 0:
        create_folders(
            project_name=project,
            submission_id=submission_id,
            create_or_update="update",
            predictions_file=predictions_filename,
            log_file=None,
            syn=syn,
        )


def mount_volumes() -> dict:
    """
    Mount volumes onto a docker container.

    This function returns a dictionary of volumes to mount on a docker
    container, in the format required by the Docker Python API. The
    dictionary keys are the paths on the host machine, and the values are
    dictionaries with the following keys:

    - bind: The path on the container where the volume will be mounted
    - mode: The permissions on the mounted volume ("ro" for read-only or
      "rw" for read-write)

    The volumes mounted are:

    - The current working directory's output/ directory, mounted as read-write
    - The current working directory's input/ directory, mounted as read-only
    """
    output_dir = os.path.join(os.getcwd(), "output")
    input_dir = os.path.join(os.getcwd(), "input")

    mounted_volumes = {
        output_dir: {"bind": "/output", "mode": "rw"},
        input_dir: {"bind": "/input", "mode": "ro"},
    }

    volumes = {}
    for vol in mounted_volumes.keys():
        volumes[vol] = mounted_volumes[vol]

    return volumes


def run_docker(project: str, submission_id: str, log_filename: str = "docker.log") -> None:
    """
    A function to run a Docker container with the specified image and handle any exceptions that may occur.

    This function will run a Docker container using the image specified by the
    ``submission_id`` argument, and will mount the input/ and output/ directories
    in the current working directory to the corresponding locations in the
    container. If the container runs successfully, the function will copy any
    generated predictions file in the /output directory to Synapse. If the
    container fails, the function will store the error message in a log file on
    Synapse.

    Args:
        project: The Synapse project ID where the submission is located.
        submission_id: The ID of the submission to run.

    Returns:
        None
    """
    # Get the Synapse authentication token from the environment variable
    synapse_auth_token: str = os.environ["SYNAPSE_AUTH_TOKEN"]

    # Communication with the Docker client
    client = docker.from_env()

    # Log into Synapse
    syn = synapseclient.login(silent=True)

    # Login to the Docker registry using SYNAPSE_AUTH_TOKEN
    client.login(
        username="foo",
        password=synapse_auth_token,
        registry="https://docker.synapse.org",
    )

    # Mount the input/ and output/ volumes that will exist in the submission container
    volumes = mount_volumes()

    # Get the Docker image ID from the submission
    docker_image = get_submission_image(syn, submission_id)

    # Run the docker image using the client:
    # We use ``detach=False`` and ``stderr=True``
    # to catch for and log possible errors in the logfile.
    try:
        container = client.containers.run(
            docker_image,
            detach=False,
            volumes=volumes,
            network_disabled=True,
            mem_limit="6g",
            stderr=True,
        )

        log_text = container

        # Assuming the predictions file is generated in the /output directory
        predictions_csv_path = os.path.join(os.getcwd(), "output", "predictions.csv")
        predictions_zip_path = os.path.join(os.getcwd(), "output", "predictions.zip")

        # Retrieve the output CSV or ZIP predictions file and store it on Synapse
        if os.path.exists(predictions_csv_path):
            store_predictions_file(
                syn=syn,
                project=project,
                predictions_filename=predictions_csv_path,
                submission_id=submission_id,
            )
        elif os.path.exists(predictions_zip_path):
            store_predictions_file(
                syn=syn,
                project=project,
                predictions_filename=predictions_zip_path,
                submission_id=submission_id,
            )

    except Exception as e:
        log_text = str(e).replace("\\n", "\n")
        create_log_file(log_filename=log_filename, log_text=log_text)
        store_log_file(
            syn=syn,
            project=project,
            log_filename=f"docker.log",
            submission_id=submission_id,
        )
        raise

    # Create log file and store the log message (``log_text``) inside
    create_log_file(log_filename=log_filename, log_text=log_text)

    # Store the log file on Synapse under its corresponding folder
    store_log_file(
        syn=syn,
        project=project,
        log_filename=f"docker.log",
        submission_id=submission_id,
    )


if __name__ == "__main__":
    project = sys.argv[1]
    submission_id = sys.argv[2]

    run_docker(project, submission_id)
