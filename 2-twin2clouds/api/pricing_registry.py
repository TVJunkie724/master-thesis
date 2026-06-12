"""Read-only pricing registry API endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from backend.pricing_registry import PricingRegistryError
from backend.pricing_registry_service import (
    PricingRegistryLookupError,
    PricingRegistryService,
)
from api.error_models import ERROR_RESPONSES


router = APIRouter(prefix="/pricing-registry", tags=["Pricing Registry"])
service = PricingRegistryService()


class RegistryStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    registry_version: str
    intent_count: int
    normalization_rule_count: int
    service_model_count: int
    pricing_model_classification_count: int
    price_source_classification_count: int
    optimization_bundle_count: int
    calculation_strategy_count: int
    formula_set_count: int
    workload_contract_count: int
    provider_pricing_contract_count: int
    providers: list[str]
    provider_mapping_counts: dict[str, int]


class RegistryCollectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_version: str
    items: dict[str, dict[str, Any]]


class RegistryItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_version: str
    item: dict[str, Any]


class RegistryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_version: str
    items: list[dict[str, Any]]


class ProviderMappingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_version: str
    provider: str
    mappings: dict[str, dict[str, Any]]


class ProviderMappingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_version: str
    provider: str
    intent_id: str
    mapping: dict[str, Any]


def _registry_error(exc: PricingRegistryError) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail={
            "error_code": "PRICING_REGISTRY_INVALID",
            "message": "Pricing registry validation failed.",
            "fix_suggestion": "Fix the editable pricing_registry files and retry.",
            "http_status": 500,
            "field_errors": [{"field": "pricing_registry", "message": error} for error in exc.errors],
        },
    )


def _lookup_error(exc: PricingRegistryLookupError) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error_code": "PRICING_REGISTRY_ITEM_NOT_FOUND",
            "message": str(exc),
            "fix_suggestion": "Use the list endpoints to inspect available registry ids.",
            "http_status": 404,
        },
    )


@router.get(
    "/status",
    response_model=RegistryStatusResponse,
    operation_id="getPricingRegistryStatus",
    summary="Get pricing registry status",
    responses={500: ERROR_RESPONSES[500]},
)
def get_pricing_registry_status():
    try:
        return service.get_status()
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/intents",
    response_model=RegistryCollectionResponse,
    operation_id="listPricingRegistryIntents",
    summary="List pricing registry intents",
    responses={500: ERROR_RESPONSES[500]},
)
def list_pricing_registry_intents(metric: str | None = Query(default=None)):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "items": service.list_intents(metric=metric),
        }
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/intents/{intent_id}",
    response_model=RegistryItemResponse,
    operation_id="getPricingRegistryIntent",
    summary="Get one pricing registry intent",
    responses={404: ERROR_RESPONSES[404], 500: ERROR_RESPONSES[500]},
)
def get_pricing_registry_intent(intent_id: str):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "item": service.get_intent(intent_id),
        }
    except PricingRegistryLookupError as exc:
        raise _lookup_error(exc)
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/service-models",
    response_model=RegistryCollectionResponse,
    operation_id="listPricingRegistryServiceModels",
    summary="List pricing registry service models",
    responses={500: ERROR_RESPONSES[500]},
)
def list_pricing_registry_service_models():
    try:
        return {
            "registry_version": service.get_registry_version(),
            "items": service.list_service_models(),
        }
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/service-models/{service_model_id}",
    response_model=RegistryItemResponse,
    operation_id="getPricingRegistryServiceModel",
    summary="Get one pricing registry service model",
    responses={404: ERROR_RESPONSES[404], 500: ERROR_RESPONSES[500]},
)
def get_pricing_registry_service_model(service_model_id: str):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "item": service.get_service_model(service_model_id),
        }
    except PricingRegistryLookupError as exc:
        raise _lookup_error(exc)
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/normalization-rules",
    response_model=RegistryCollectionResponse,
    operation_id="listPricingRegistryNormalizationRules",
    summary="List pricing registry normalization rules",
    responses={500: ERROR_RESPONSES[500]},
)
def list_pricing_registry_normalization_rules():
    try:
        return {
            "registry_version": service.get_registry_version(),
            "items": service.list_normalization_rules(),
        }
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/pricing-model-classifications",
    response_model=RegistryCollectionResponse,
    operation_id="listPricingRegistryModelClassifications",
    summary="List pricing model classifications",
    responses={404: ERROR_RESPONSES[404], 500: ERROR_RESPONSES[500]},
)
def list_pricing_model_classifications(provider: str | None = Query(default=None)):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "items": service.list_pricing_model_classifications(provider=provider),
        }
    except PricingRegistryLookupError as exc:
        raise _lookup_error(exc)
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/pricing-model-classifications/{classification_id}",
    response_model=RegistryItemResponse,
    operation_id="getPricingRegistryModelClassification",
    summary="Get one pricing model classification",
    responses={404: ERROR_RESPONSES[404], 500: ERROR_RESPONSES[500]},
)
def get_pricing_model_classification(classification_id: str):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "item": service.get_pricing_model_classification(classification_id),
        }
    except PricingRegistryLookupError as exc:
        raise _lookup_error(exc)
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/price-source-classifications",
    response_model=RegistryCollectionResponse,
    operation_id="listPricingRegistrySourceClassifications",
    summary="List price source classifications",
    responses={404: ERROR_RESPONSES[404], 500: ERROR_RESPONSES[500]},
)
def list_price_source_classifications(provider: str | None = Query(default=None)):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "items": service.list_price_source_classifications(provider=provider),
        }
    except PricingRegistryLookupError as exc:
        raise _lookup_error(exc)
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/price-source-classifications/{classification_id}",
    response_model=RegistryItemResponse,
    operation_id="getPricingRegistrySourceClassification",
    summary="Get one price source classification",
    responses={404: ERROR_RESPONSES[404], 500: ERROR_RESPONSES[500]},
)
def get_price_source_classification(classification_id: str):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "item": service.get_price_source_classification(classification_id),
        }
    except PricingRegistryLookupError as exc:
        raise _lookup_error(exc)
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/field-verification-matrix",
    response_model=RegistryListResponse,
    operation_id="listPricingRegistryFieldVerificationMatrix",
    summary="List pricing field verification matrix rows",
    responses={404: ERROR_RESPONSES[404], 500: ERROR_RESPONSES[500]},
)
def list_field_verification_matrix(provider: str | None = Query(default=None)):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "items": service.build_field_verification_matrix(provider=provider),
        }
    except PricingRegistryLookupError as exc:
        raise _lookup_error(exc)
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/optimization-bundles",
    response_model=RegistryCollectionResponse,
    operation_id="listPricingRegistryOptimizationBundles",
    summary="List optimization bundles",
    responses={500: ERROR_RESPONSES[500]},
)
def list_optimization_bundles():
    try:
        return {
            "registry_version": service.get_registry_version(),
            "items": service.list_optimization_bundles(),
        }
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/optimization-bundles/{bundle_id}",
    response_model=RegistryItemResponse,
    operation_id="getPricingRegistryOptimizationBundle",
    summary="Get one optimization bundle",
    responses={404: ERROR_RESPONSES[404], 500: ERROR_RESPONSES[500]},
)
def get_optimization_bundle(bundle_id: str):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "item": service.get_optimization_bundle(bundle_id),
        }
    except PricingRegistryLookupError as exc:
        raise _lookup_error(exc)
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/provider-pricing-contracts",
    response_model=RegistryCollectionResponse,
    operation_id="listPricingRegistryProviderPricingContracts",
    summary="List provider pricing contracts",
    responses={404: ERROR_RESPONSES[404], 500: ERROR_RESPONSES[500]},
)
def list_provider_pricing_contracts(provider: str | None = Query(default=None)):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "items": service.list_provider_pricing_contracts(provider=provider),
        }
    except PricingRegistryLookupError as exc:
        raise _lookup_error(exc)
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/providers/{provider}/mappings",
    response_model=ProviderMappingsResponse,
    operation_id="listPricingRegistryProviderMappings",
    summary="List pricing registry mappings for one provider",
    responses={404: ERROR_RESPONSES[404], 500: ERROR_RESPONSES[500]},
)
def list_pricing_registry_provider_mappings(provider: str):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "provider": provider,
            "mappings": service.list_provider_mappings(provider),
        }
    except PricingRegistryLookupError as exc:
        raise _lookup_error(exc)
    except PricingRegistryError as exc:
        raise _registry_error(exc)


@router.get(
    "/providers/{provider}/mappings/{intent_id}",
    response_model=ProviderMappingResponse,
    operation_id="getPricingRegistryProviderMapping",
    summary="Get one provider mapping for one pricing intent",
    responses={404: ERROR_RESPONSES[404], 500: ERROR_RESPONSES[500]},
)
def get_pricing_registry_provider_mapping(provider: str, intent_id: str):
    try:
        return {
            "registry_version": service.get_registry_version(),
            "provider": provider,
            "intent_id": intent_id,
            "mapping": service.get_provider_mapping(provider, intent_id),
        }
    except PricingRegistryLookupError as exc:
        raise _lookup_error(exc)
    except PricingRegistryError as exc:
        raise _registry_error(exc)
