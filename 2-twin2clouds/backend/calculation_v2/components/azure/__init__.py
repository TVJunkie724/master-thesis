"""
Azure Components Package
========================

Azure-specific cost calculators for each service component.
"""

from .iot_hub import AzureIoTHubCalculator
from .functions import AzureFunctionsCalculator
from .logic_apps import AzureLogicAppsCalculator
from .event_grid import AzureEventGridCalculator
from .cosmos_db import AzureCosmosDBCalculator
from .blob_storage import AzureBlobCoolCalculator, AzureBlobArchiveCalculator
from .digital_twins import AzureDigitalTwinsCalculator
from .grafana import AzureGrafanaCalculator

__all__ = [
    "AzureIoTHubCalculator",
    "AzureFunctionsCalculator",
    "AzureLogicAppsCalculator",
    "AzureEventGridCalculator",
    "AzureCosmosDBCalculator",
    "AzureBlobCoolCalculator",
    "AzureBlobArchiveCalculator",
    "AzureDigitalTwinsCalculator",
    "AzureGrafanaCalculator",
]
