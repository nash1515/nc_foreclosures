"""Wake County Real Estate enrichment module."""

# Delayed import to avoid circular dependencies
# enrich_case will be available after enricher.py is created
def enrich_case(*args, **kwargs):
    from enrichments.wake_re.enricher import enrich_case as _enrich_case
    return _enrich_case(*args, **kwargs)

__all__ = ['enrich_case']
