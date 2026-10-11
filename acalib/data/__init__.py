"""
Data handling, schemas, and dataset accounting.
"""
from .schema import (
    validate_dataframe,
    get_independent_instance_key,
    get_pairing_key,
    get_unique_trial_key,
    count_instances_and_trials,
    ALLOWED_STATUSES,
    ALLOWED_METHODS,
    ALLOWED_ADVERSARIES,
    ALLOWED_FAMILIES,
)
