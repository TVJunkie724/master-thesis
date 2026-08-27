"""Canonical cleanup evidence fixtures shared by Management tests."""


def complete_cleanup_evidence(provider: str = "aws") -> dict:
    return {
        "schema_version": "cleanup-evidence.v1",
        "status": "complete",
        "terraform": {
            "destroy_status": "completed",
            "observed_before_resource_count": 9,
            "post_destroy_inventory": "empty",
            "residual_resource_count": 0,
        },
        "providers": [
            {
                "provider": provider,
                "cleanup_status": "completed",
                "discovered_during_cleanup_count": 4,
                "discovered_resource_kinds": ["Cloud Functions"],
                "post_destroy_inventory": "empty",
                "residual_resource_count": 0,
            }
        ],
        "retained_shared_prerequisites": [],
        "residual_failures": [],
    }


def incomplete_cleanup_evidence(provider: str = "aws") -> dict:
    evidence = complete_cleanup_evidence(provider)
    evidence["status"] = "incomplete"
    evidence["providers"][0]["post_destroy_inventory"] = "residual"
    evidence["providers"][0]["residual_resource_count"] = 1
    evidence["residual_failures"] = [
        {
            "scope": "provider_inventory",
            "provider": provider,
            "reason": "resources_remain",
        }
    ]
    return evidence
