from .prod import *  # noqa

# Staging-specific: allow anonymised data imports, verbose logging
LOGGING['root']['level'] = 'DEBUG'  # noqa
