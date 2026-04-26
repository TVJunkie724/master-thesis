"""Shared validation calls for cloud credential payloads."""

import asyncio

import httpx

from src.config import settings


async def perform_dual_validation(
    provider: str,
    optimizer_creds: dict,
    deployer_creds: dict,
) -> dict:
    """Validate credentials against Optimizer and Deployer without persisting secrets."""

    async def call_optimizer():
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.OPTIMIZER_URL}/permissions/verify/{provider}",
                    json=optimizer_creds,
                    timeout=30.0,
                )
                if response.status_code == 200:
                    result = response.json()
                    is_valid = result.get("valid", False) or result.get("status") == "valid"
                    return {
                        "valid": is_valid,
                        "message": result.get("message", "Validation complete"),
                    }
                return {
                    "valid": False,
                    "message": f"Optimizer API error: {response.status_code}",
                }
        except httpx.ConnectError:
            return {
                "valid": False,
                "message": "Cannot connect to Optimizer API (port 5003)",
            }
        except Exception as exc:
            return {
                "valid": False,
                "message": f"Optimizer error: {exc}",
            }

    async def call_deployer():
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.DEPLOYER_URL}/permissions/verify/{provider}",
                    json=deployer_creds,
                    timeout=30.0,
                )
                if response.status_code == 200:
                    result = response.json()
                    is_valid = result.get("valid", False) or result.get("status") == "valid"
                    return {
                        "valid": is_valid,
                        "message": result.get("message", "Validation complete"),
                        "permissions": result.get("missing_permissions"),
                    }
                return {
                    "valid": False,
                    "message": f"Deployer API error: {response.status_code}",
                }
        except httpx.ConnectError:
            return {
                "valid": False,
                "message": "Cannot connect to Deployer API (port 5004)",
            }
        except Exception as exc:
            return {
                "valid": False,
                "message": f"Deployer error: {exc}",
            }

    optimizer_result, deployer_result = await asyncio.gather(call_optimizer(), call_deployer())

    return {
        "provider": provider,
        "valid": optimizer_result.get("valid", False) and deployer_result.get("valid", False),
        "optimizer": optimizer_result,
        "deployer": deployer_result,
    }
