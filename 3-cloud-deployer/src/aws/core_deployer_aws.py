"""
Core Deployer AWS (Facade)

This module acts as a facade for the AWS deployment logic, which has been refactored 
into modular layers located in `src/providers/aws/layers/`.

DEPRECATION NOTICE:
This file and the old deployers/core_deployer.py are deprecated.
Use `src/providers/deployer.py` with DeploymentContext instead.

For legacy CLI compatibility, this facade imports from the new location.
"""

import warnings
warnings.warn(
    "core_deployer_aws module is deprecated. "
    "Use providers/aws/layers/ or providers/deployer.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import all functions from the new layer modules for backward compatibility
from providers.aws.layers.layer_1_iot import *
from providers.aws.layers.layer_2_compute import *
from providers.aws.layers.layer_3_storage import *
from providers.aws.layers.layer_4_twinmaker import *
from providers.aws.layers.layer_5_grafana import *
