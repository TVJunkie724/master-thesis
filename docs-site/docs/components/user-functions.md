# User Function Patterns

The Deployer supports user-defined processor functions, but each cloud provider needs a different invocation and packaging pattern.

## AWS: Decoupled Invoke Pattern

AWS uses Lambda-to-Lambda invocation. The infrastructure wrapper invokes the user processor through the AWS Lambda SDK.

```text
L0 Ingestion
  -> L1 Dispatcher
    -> L2 Processor Wrapper
      -> User Processor Lambda
      -> L2 Persister
        -> L3 Hot Storage
```

The wrapper discovers the target processor name from the device ID and invokes `{twin}-{device}-processor`.

## Azure: Decoupled HTTP Pattern

Azure separates infrastructure functions and user functions into different Function Apps. The wrapper calls the user processor over HTTP.

```text
L0 Ingestion
  -> L1 Dispatcher
    -> L2 Processor Wrapper
      -> User Function App /api/{twin}-{device}-processor
      -> L2 Persister
        -> Cosmos DB
```

Azure user functions are bundled into one generated Function App package using Python Blueprints.

## GCP: HTTP Function Pattern

GCP user processors use HTTP-triggered Cloud Functions.

```text
Dispatcher / connector / ingestion
  -> L2 Processor Wrapper Cloud Function
    -> User Processor Cloud Function Gen 2
    -> Persister Cloud Function
      -> Firestore
```

## Why This Matters

This is one of the important implementation differences from the original projects: the current Deployer does not just deploy a fixed function. It packages and wires user code differently per provider while exposing one conceptual processor layer to the Management API and UI.
