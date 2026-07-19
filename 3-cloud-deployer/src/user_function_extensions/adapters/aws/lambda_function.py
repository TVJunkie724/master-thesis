"""AWS trigger adapter for the canonical user-function runtime envelope."""

from _platform_runtime import invoke


def lambda_handler(event, context):
    return invoke(event)
