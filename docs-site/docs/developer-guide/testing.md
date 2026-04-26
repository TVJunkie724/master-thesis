# Testing

The original Twin2Clouds documentation grouped tests by the part of the cost engine they verify. That structure is still useful for understanding the optimizer and for thesis evaluation.

![Testing categories](../references/diagrams/testing_categories.png)

## Optimizer Test Categories

| Category | Purpose |
|----------|---------|
| Formula tests | Verify AWS, Azure, and GCP cost formulas in isolation. |
| Optimization tests | Verify graph construction and cheapest-path behavior. |
| Data transfer tests | Verify bandwidth and cross-region transfer calculations. |
| Pricing fetcher tests | Verify cloud pricing API parsing and fallback behavior. |
| API tests | Verify FastAPI endpoints and response shapes. |

## Safe Commands

Unit and integration tests are safe to run locally:

```bash
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -v
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 python -m pytest tests/ -v
```

E2E tests are different: they can deploy real cloud resources and should only be run intentionally.
