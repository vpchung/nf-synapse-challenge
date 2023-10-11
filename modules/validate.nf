// validate submission results
process VALIDATE {    
    secret "SYNAPSE_AUTH_TOKEN"
    container "python:3.12.0rc1"

    input:
    tuple val(submission_id), path(predictions)
    val ready
    val validation_script

    output:
    tuple val(submission_id), path(predictions), stdout, path("results.json")

    script:
    """
    ${validation_script} '${predictions}'
    """
}
