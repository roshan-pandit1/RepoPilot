"""Explicit independent gates; a credential alone never authorizes paid generation."""
from uuid import UUID


def _real_provider_configured(settings):
    try:
        experiment_id = str(UUID(settings.investigation_experiment_id))
    except (ValueError, TypeError, AttributeError):
        return False
    return bool(settings.investigation_provider == 'openai' and settings.investigation_real_enabled
        and settings.investigation_openai_api_key.get_secret_value()
        and experiment_id == settings.investigation_experiment_id)


def real_provider_enabled(settings):
    return bool(_real_provider_configured(settings) and settings.investigation_paid_background_enabled)


def real_executor_enabled(settings):
    """The isolated one-shot executor must not enable paid background workers."""
    return bool(_real_provider_configured(settings) and not settings.investigation_paid_background_enabled)
