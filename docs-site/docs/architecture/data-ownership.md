# Responsibilities And Data Ownership

## Ownership Matrix

| Concern | System of record | Consumers |
|---|---|---|
| users and identities | Management API database | Flutter, audit workflows |
| twin identity and lifecycle | Management API database | Flutter, orchestration |
| reusable cloud credentials | encrypted Management API `cloud_connections` | validation, pricing, deployment |
| wizard/configuration state | Management API configuration tables and file versions | Flutter, Optimizer, Deployer |
| pricing intent and mappings | Optimizer `pricing_registry/*.yaml` | fetch, review, calculation |
| price-free transfer route policy | Optimizer `pricing_registry/transfer_routes.yaml` | route classification and exact immutable-catalog resolution |
| immutable public pricing catalogs | Optimizer regional catalog store | Management API exact-reference verification, calculations, authenticated diagnostics |
| pricing refresh/review history | Management API database | Flutter pricing workspace |
| cost calculation history and exact catalog reference sets | Management API database | Flutter twin/configuration views, deployment selection |
| deployment package definition | Management API generated archive and manifest | Deployer operation-package store |
| Terraform/runtime state | Deployer runtime project storage | destroy, status, simulator, verification |
| deployment operation history and logs | Management API database | Flutter via REST/SSE |
| user/developer documentation | `docs-site/docs` | users, operators, developers |
| research notes | `docs/research` | research reasoning and later thesis synthesis |
| final thesis | `twin2multicloud-latex` | submitted academic document |

## State Boundaries

```text
editable source                  generated/durable state
---------------                  -----------------------
pricing_registry/*.yaml  ----->  immutable regional pricing catalogs
deployer template        ----->  deployment archive + manifest
Management API config    ----->  staged package -> ephemeral workspace
                                        |
                                        +-> allowlisted runtime outputs
```

Generated pricing evidence may be inspected but must not become editable pricing
truth. The Management API stores exact catalog references, not duplicated pricing
payloads. A Deployer workspace may be mutated during an operation, but only
allowlisted outputs are synchronized back to durable runtime storage.

## Twin Lifecycle

```text
 draft --validated configuration--> configured --deploy--> deploying
   ^                                      ^                    |
   | config changed                       | retry              v
   +--------------------------------------+---- error <---- deployed
                                                  |             |
                                                  | destroy     | destroy
                                                  v             v
                                             destroying ----> destroyed

 any non-removed workflow state --soft delete--> inactive
```

`TwinLifecycleService` owns transitions. Routes and Flutter may request actions but
must not invent state changes. `deploying` and `destroying` are transient operation
states; deployment history is recorded separately.
