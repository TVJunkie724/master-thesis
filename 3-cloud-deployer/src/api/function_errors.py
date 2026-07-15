"""Domain exceptions for function build and provider update boundaries."""


class FunctionProviderError(RuntimeError):
    """A provider or transport rejected an otherwise valid function update."""

