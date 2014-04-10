

try:
    # Initially import local configs and then the overrides
    from configs.config_local import *

    from configs.config_override import *

except ImportError:

    pass