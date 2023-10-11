// validate submission results
process SCORE {
    secret "SYNAPSE_AUTH_TOKEN"
    container "python:3.12.0rc1"

    input:
    tuple val(submission_id), path(predictions), val(status), path(results)
    val status_ready
    val annotate_ready
    val scoring_script

    output:
    tuple val(submission_id), path(predictions), stdout, path("results.json")

    script:
    """
    ${scoring_script} '${predictions}' '${results}' '${status}'
    """
}
