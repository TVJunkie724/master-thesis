# Project background

Twin2MultiCloud integrates two predecessor research artifacts: a layer-based
cloud-cost model and a cloud deployment implementation. The thesis contribution
is the method that makes their assumptions explicit and connects typed intent,
functional admissibility, cost evidence, deployment and verification across
AWS, Azure and Google Cloud.

The current PoC adds a Management API and Flutter workflow, a standalone
Six-layer Eventing contract, frozen pricing evidence, deterministic deployment
resolution and a supervised evaluation design. It does not claim that the
predecessor systems or the resulting prototype are production-ready.

Five-layer v1 is retained only as an offline comparison baseline. The evaluated
runtime uses `six-layer-eventing@1` because Eventing has independent placement,
delivery behavior, trust, verification and cost consequences that must be
observable in the research evidence.

Primary research sources are stored under `docs/research/`; the EDTconf paper
artifact and predecessor references are listed under References. Historical
implementation evolution remains available through Git rather than in the
active user documentation.
