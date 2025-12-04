
import json
import math
from backend.calculation import aws, azure, gcp, transfer, decision
from backend.config_loader import load_json_file, load_combined_pricing
import backend.constants as CONSTANTS
from backend.pricing_utils import validate_pricing_schema
from backend.logger import logger

def calculate_aws_costs(params, pricing):
    """
    Calculates monthly costs for all AWS layers (1-5) and associated transfer costs.
    Returns a dictionary containing cost breakdowns for each layer and transfer path.
    """
    aws_result_data_acquisition = aws.calculate_aws_cost_data_acquisition(
        params["numberOfDevices"],
        params["deviceSendingIntervalInMinutes"],
        params["averageSizeOfMessageInKb"],
        pricing
    )

    aws_result_data_processing = aws.calculate_aws_cost_data_processing(
        params["numberOfDevices"],
        params["deviceSendingIntervalInMinutes"],
        params["averageSizeOfMessageInKb"],
        pricing,
        use_event_checking=params.get("useEventChecking", False),
        trigger_notification_workflow=params.get("triggerNotificationWorkflow", False),
        return_feedback_to_device=params.get("returnFeedbackToDevice", False),
        integrate_error_handling=params.get("integrateErrorHandling", False),
        orchestration_actions_per_message=params.get("orchestrationActionsPerMessage", 3),
        events_per_message=params.get("eventsPerMessage", 1)
    )

    transfer_cost_from_l2_aws_to_aws_hot = transfer.calculate_transfer_cost_from_l2_aws_to_aws_hot(
        aws_result_data_processing["dataSizeInGB"]
    )
    
    transfer_cost_from_l2_aws_to_azure_hot = transfer.calculate_transfer_cost_from_l2_aws_to_azure_hot(
        aws_result_data_processing["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_l2_aws_to_gcp_hot = transfer.calculate_transfer_cost_from_l2_aws_to_gcp_hot(
        aws_result_data_processing["dataSizeInGB"],
        pricing
    )

    aws_result_hot_dynamodb = aws.calculate_dynamodb_cost(
        aws_result_data_processing["dataSizeInGB"],
        aws_result_data_processing["totalMessagesPerMonth"],
        params["averageSizeOfMessageInKb"],
        params["hotStorageDurationInMonths"],
        pricing
    )

    transfer_cost_from_aws_hot_to_aws_cool = transfer.calculate_transfer_cost_from_aws_hot_to_aws_cool(
        aws_result_hot_dynamodb["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_aws_hot_to_azure_cool = transfer.calculate_transfer_cost_from_aws_hot_to_azure_cool(
        aws_result_hot_dynamodb["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_aws_hot_to_gcp_cool = transfer.calculate_transfer_cost_from_aws_hot_to_gcp_cool(
        aws_result_hot_dynamodb["dataSizeInGB"],
        pricing
    )

    aws_result_l3_cool = aws.calculate_s3_infrequent_access_cost(
        aws_result_hot_dynamodb["dataSizeInGB"],
        params["coolStorageDurationInMonths"],
        pricing
    )

    transfer_cost_from_aws_cool_to_aws_archive = transfer.calculate_transfer_cost_from_aws_cool_to_aws_archive(
        aws_result_l3_cool["dataSizeInGB"]
    )
    
    transfer_cost_from_aws_cool_to_azure_archive = transfer.calculate_transfer_cost_from_aws_cool_to_azure_archive(
        aws_result_l3_cool["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_aws_cool_to_gcp_archive = transfer.calculate_transfer_cost_from_aws_cool_to_gcp_archive(
        aws_result_l3_cool["dataSizeInGB"],
        pricing
    )

    aws_result_l3_archive = aws.calculate_s3_glacier_deep_archive_cost(
        aws_result_l3_cool["dataSizeInGB"],
        params["archiveStorageDurationInMonths"],
        pricing
    )

    aws_result_layer4 = aws.calculate_aws_iot_twin_maker_cost(
        params["entityCount"],
        params["numberOfDevices"],
        params["deviceSendingIntervalInMinutes"],
        params["dashboardRefreshesPerHour"],
        params["dashboardActiveHoursPerDay"],
        params["average3DModelSizeInMB"],
        pricing
    )

    aws_result_layer5 = aws.calculate_amazon_managed_grafana_cost(
        params["amountOfActiveEditors"],
        params["amountOfActiveViewers"],
        pricing
    )

    return {
        "dataAquisition": aws_result_data_acquisition,
        "dataProcessing": aws_result_data_processing,
        "resultHot": aws_result_hot_dynamodb,
        "resultL3Cool": aws_result_l3_cool,
        "resultL3Archive": aws_result_l3_archive,
        "resultL4": aws_result_layer4,
        "resultL5": aws_result_layer5,
        "transferCostL2ToHotAWS": transfer_cost_from_l2_aws_to_aws_hot,
        "transferCostL2ToHotAzure": transfer_cost_from_l2_aws_to_azure_hot,
        "transferCostL2ToHotGCP": transfer_cost_from_l2_aws_to_gcp_hot,
        "transferCostHotToCoolAWS": transfer_cost_from_aws_hot_to_aws_cool,
        "transferCostHotToCoolAzure": transfer_cost_from_aws_hot_to_azure_cool,
        "transferCostHotToCoolGCP": transfer_cost_from_aws_hot_to_gcp_cool,
        "transferCostCoolToArchiveAWS": transfer_cost_from_aws_cool_to_aws_archive,
        "transferCostCoolToArchiveAzure": transfer_cost_from_aws_cool_to_azure_archive,
        "transferCostCoolToArchiveGCP": transfer_cost_from_aws_cool_to_gcp_archive,
    }

def calculate_azure_costs(params, pricing):
    """
    Calculates monthly costs for all Azure layers (1-5) and associated transfer costs.
    Returns a dictionary containing cost breakdowns for each layer and transfer path.
    """
    azure_result_data_acquisition = azure.calculate_azure_cost_data_acquisition(
        params["numberOfDevices"],
        params["deviceSendingIntervalInMinutes"],
        params["averageSizeOfMessageInKb"],
        pricing
    )

    azure_result_data_processing = azure.calculate_azure_cost_data_processing(
        params["numberOfDevices"],
        params["deviceSendingIntervalInMinutes"],
        params["averageSizeOfMessageInKb"],
        pricing,
        use_event_checking=params.get("useEventChecking", False),
        trigger_notification_workflow=params.get("triggerNotificationWorkflow", False),
        return_feedback_to_device=params.get("returnFeedbackToDevice", False),
        integrate_error_handling=params.get("integrateErrorHandling", False),
        orchestration_actions_per_message=params.get("orchestrationActionsPerMessage", 3),
        events_per_message=params.get("eventsPerMessage", 1)
    )

    transfer_cost_from_l2_azure_to_aws_hot = transfer.calculate_transfer_cost_from_l2_azure_to_aws_hot(
        azure_result_data_processing["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_l2_azure_to_azure_hot = transfer.calculate_transfer_cost_from_l2_azure_to_azure_hot(
        azure_result_data_processing["dataSizeInGB"]
    )

    transfer_cost_from_l2_azure_to_gcp_hot = transfer.calculate_transfer_cost_from_l2_azure_to_gcp_hot(
        azure_result_data_processing["dataSizeInGB"],
        pricing
    )

    azure_result_hot = azure.calculate_cosmos_db_cost(
        azure_result_data_processing["dataSizeInGB"],
        azure_result_data_processing["totalMessagesPerMonth"],
        params["averageSizeOfMessageInKb"],
        params["hotStorageDurationInMonths"],
        pricing
    )

    transfer_cost_from_azure_hot_to_aws_cool = transfer.calculate_transfer_costs_from_azure_hot_to_aws_cool(
        azure_result_hot["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_azure_hot_to_azure_cool = transfer.calculate_transfer_cost_from_azure_hot_to_azure_cool(
        azure_result_hot["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_azure_hot_to_gcp_cool = transfer.calculate_transfer_cost_from_azure_hot_to_gcp_cool(
        azure_result_hot["dataSizeInGB"],
        pricing
    )

    azure_result_layer3_cool_blob_storage = azure.calculate_azure_blob_storage_cost(
        azure_result_hot["dataSizeInGB"],
        params["coolStorageDurationInMonths"],
        pricing
    )

    transfer_cost_from_azure_cool_to_aws_archive = transfer.calculate_transfer_cost_from_azure_cool_to_aws_archive(
        azure_result_layer3_cool_blob_storage["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_azure_cool_to_azure_archive = transfer.calculate_transfer_cost_from_azure_cool_to_azure_archive(
        azure_result_layer3_cool_blob_storage["dataSizeInGB"]
    )

    transfer_cost_from_azure_cool_to_gcp_archive = transfer.calculate_transfer_cost_from_azure_cool_to_gcp_archive(
        azure_result_layer3_cool_blob_storage["dataSizeInGB"],
        pricing
    )

    azure_result_layer3_archive = azure.calculate_azure_blob_storage_archive_cost(
        azure_result_layer3_cool_blob_storage["dataSizeInGB"],
        params["archiveStorageDurationInMonths"],
        pricing
    )

    azure_result_layer4 = azure.calculate_azure_digital_twins_cost(
        params["numberOfDevices"],
        params["deviceSendingIntervalInMinutes"],
        params["averageSizeOfMessageInKb"],
        params["dashboardRefreshesPerHour"],
        params["dashboardActiveHoursPerDay"],
        params["entityCount"],
        params["average3DModelSizeInMB"],
        pricing
    )

    azure_result_layer5 = azure.calculate_azure_managed_grafana_cost(
        params["amountOfActiveEditors"] + params["amountOfActiveViewers"],
        pricing
    )

    return {
        "dataAquisition": azure_result_data_acquisition,
        "dataProcessing": azure_result_data_processing,
        "resultHot": azure_result_hot,
        "resultL3Cool": azure_result_layer3_cool_blob_storage,
        "resultL3Archive": azure_result_layer3_archive,
        "resultL4": azure_result_layer4,
        "resultL5": azure_result_layer5,
        "transferCostL2ToHotAWS": transfer_cost_from_l2_azure_to_aws_hot,
        "transferCostL2ToHotAzure": transfer_cost_from_l2_azure_to_azure_hot,
        "transferCostL2ToHotGCP": transfer_cost_from_l2_azure_to_gcp_hot,
        "transferCostHotToCoolAWS": transfer_cost_from_azure_hot_to_aws_cool,
        "transferCostHotToCoolAzure": transfer_cost_from_azure_hot_to_azure_cool,
        "transferCostHotToCoolGCP": transfer_cost_from_azure_hot_to_gcp_cool,
        "transferCostCoolToArchiveAWS": transfer_cost_from_azure_cool_to_aws_archive,
        "transferCostCoolToArchiveAzure": transfer_cost_from_azure_cool_to_azure_archive,
        "transferCostCoolToArchiveGCP": transfer_cost_from_azure_cool_to_gcp_archive,
    }

def calculate_gcp_costs(params, pricing):
    """
    Calculates monthly costs for all GCP layers (1-5) and associated transfer costs.
    Returns a dictionary containing cost breakdowns for each layer and transfer path.
    """
    gcp_result_data_acquisition = gcp.calculate_gcp_cost_data_acquisition(
        params["numberOfDevices"],
        params["deviceSendingIntervalInMinutes"],
        params["averageSizeOfMessageInKb"],
        pricing
    )

    gcp_result_data_processing = gcp.calculate_gcp_cost_data_processing(
        params["numberOfDevices"],
        params["deviceSendingIntervalInMinutes"],
        params["averageSizeOfMessageInKb"],
        pricing,
        use_event_checking=params.get("useEventChecking", False),
        trigger_notification_workflow=params.get("triggerNotificationWorkflow", False),
        return_feedback_to_device=params.get("returnFeedbackToDevice", False),
        integrate_error_handling=params.get("integrateErrorHandling", False),
        orchestration_actions_per_message=params.get("orchestrationActionsPerMessage", 3),
        events_per_message=params.get("eventsPerMessage", 1)
    )

    transfer_cost_from_l2_gcp_to_aws_hot = transfer.calculate_transfer_cost_from_l2_gcp_to_aws_hot(
        gcp_result_data_processing["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_l2_gcp_to_azure_hot = transfer.calculate_transfer_cost_from_l2_gcp_to_azure_hot(
        gcp_result_data_processing["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_l2_gcp_to_gcp_hot = transfer.calculate_transfer_cost_from_l2_gcp_to_gcp_hot(
        gcp_result_data_processing["dataSizeInGB"]
    )

    gcp_result_hot = gcp.calculate_firestore_cost(
        gcp_result_data_processing["dataSizeInGB"],
        gcp_result_data_processing["totalMessagesPerMonth"],
        params["averageSizeOfMessageInKb"],
        params["hotStorageDurationInMonths"],
        pricing
    )

    transfer_cost_from_gcp_hot_to_aws_cool = transfer.calculate_transfer_cost_from_gcp_hot_to_aws_cool(
        gcp_result_hot["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_gcp_hot_to_azure_cool = transfer.calculate_transfer_cost_from_gcp_hot_to_azure_cool(
        gcp_result_hot["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_gcp_hot_to_gcp_cool = transfer.calculate_transfer_cost_from_gcp_hot_to_gcp_cool(
        gcp_result_hot["dataSizeInGB"],
        pricing
    )

    gcp_result_l3_cool = gcp.calculate_gcp_storage_cool_cost(
        gcp_result_hot["dataSizeInGB"],
        params["coolStorageDurationInMonths"],
        pricing
    )

    transfer_cost_from_gcp_cool_to_aws_archive = transfer.calculate_transfer_cost_from_gcp_cool_to_aws_archive(
        gcp_result_l3_cool["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_gcp_cool_to_azure_archive = transfer.calculate_transfer_cost_from_gcp_cool_to_azure_archive(
        gcp_result_l3_cool["dataSizeInGB"],
        pricing
    )

    transfer_cost_from_gcp_cool_to_gcp_archive = transfer.calculate_transfer_cost_from_gcp_cool_to_gcp_archive(
        gcp_result_l3_cool["dataSizeInGB"]
    )

    gcp_result_l3_archive = gcp.calculate_gcp_storage_archive_cost(
        gcp_result_l3_cool["dataSizeInGB"],
        params["archiveStorageDurationInMonths"],
        pricing
    )

    gcp_result_layer4 = gcp.calculate_gcp_twin_maker_cost(
        params["entityCount"],
        params["numberOfDevices"],
        params["deviceSendingIntervalInMinutes"],
        params["dashboardRefreshesPerHour"],
        params["dashboardActiveHoursPerDay"],
        params["average3DModelSizeInMB"],
        pricing
    )

    gcp_result_layer5 = gcp.calculate_gcp_managed_grafana_cost(
        params["amountOfActiveEditors"] + params["amountOfActiveViewers"],
        pricing
    )

    return {
        "dataAquisition": gcp_result_data_acquisition,
        "dataProcessing": gcp_result_data_processing,
        "resultHot": gcp_result_hot,
        "resultL3Cool": gcp_result_l3_cool,
        "resultL3Archive": gcp_result_l3_archive,
        "resultL4": gcp_result_layer4,
        "resultL5": gcp_result_layer5,
        "transferCostL2ToHotAWS": transfer_cost_from_l2_gcp_to_aws_hot,
        "transferCostL2ToHotAzure": transfer_cost_from_l2_gcp_to_azure_hot,
        "transferCostL2ToHotGCP": transfer_cost_from_l2_gcp_to_gcp_hot,
        "transferCostHotToCoolAWS": transfer_cost_from_gcp_hot_to_aws_cool,
        "transferCostHotToCoolAzure": transfer_cost_from_gcp_hot_to_azure_cool,
        "transferCostHotToCoolGCP": transfer_cost_from_gcp_hot_to_gcp_cool,
        "transferCostCoolToArchiveAWS": transfer_cost_from_gcp_cool_to_aws_archive,
        "transferCostCoolToArchiveAzure": transfer_cost_from_gcp_cool_to_azure_archive,
        "transferCostCoolToArchiveGCP": transfer_cost_from_gcp_cool_to_gcp_archive,
    }

def calculate_cheapest_costs(params, pricing=None):
    """
    Orchestrates the cost calculation for all providers and determines the optimal (cheapest)
    architecture path across layers.
    """
    if pricing is None:
        pricing = load_combined_pricing()

    # Validate pricing data
    for provider in ["aws", "azure", "gcp"]:
        if provider in pricing:
            validation = validate_pricing_schema(provider, pricing[provider])
            if validation["status"] != "valid":
                logger.error(f"❌ Invalid pricing data for {provider}: {validation['missing_keys']}")
                raise ValueError(f"Invalid pricing data for {provider}. Missing keys: {validation['missing_keys']}. Please fetch new pricing data.")

    aws_costs = calculate_aws_costs(params, pricing) if pricing.get("aws") else {}
    azure_costs = calculate_azure_costs(params, pricing) if pricing.get("azure") else {}
    gcp_costs = calculate_gcp_costs(params, pricing) if pricing.get("gcp") else {}

    transfer_costs = {
        "L1_AWS_to_AWS_Hot": aws_costs["transferCostL2ToHotAWS"],
        "L1_AWS_to_Azure_Hot": aws_costs["transferCostL2ToHotAzure"],
        "L1_AWS_to_GCP_Hot": aws_costs["transferCostL2ToHotGCP"],
        "L1_Azure_to_AWS_Hot": azure_costs["transferCostL2ToHotAWS"],
        "L1_Azure_to_Azure_Hot": azure_costs["transferCostL2ToHotAzure"],
        "L1_Azure_to_GCP_Hot": azure_costs["transferCostL2ToHotGCP"],
        "L1_GCP_to_AWS_Hot": gcp_costs["transferCostL2ToHotAWS"],
        "L1_GCP_to_Azure_Hot": gcp_costs["transferCostL2ToHotAzure"],
        "L1_GCP_to_GCP_Hot": gcp_costs["transferCostL2ToHotGCP"],

        "AWS_Hot_to_AWS_Cool": aws_costs["transferCostHotToCoolAWS"],
        "AWS_Hot_to_Azure_Cool": aws_costs["transferCostHotToCoolAzure"],
        "AWS_Hot_to_GCP_Cool": aws_costs["transferCostHotToCoolGCP"],
        "Azure_Hot_to_AWS_Cool": azure_costs["transferCostHotToCoolAWS"],
        "Azure_Hot_to_Azure_Cool": azure_costs["transferCostHotToCoolAzure"],
        "Azure_Hot_to_GCP_Cool": azure_costs["transferCostHotToCoolGCP"],
        "GCP_Hot_to_AWS_Cool": gcp_costs["transferCostHotToCoolAWS"],
        "GCP_Hot_to_Azure_Cool": gcp_costs["transferCostHotToCoolAzure"],
        "GCP_Hot_to_GCP_Cool": gcp_costs["transferCostHotToCoolGCP"],

        "AWS_Cool_to_AWS_Archive": aws_costs["transferCostCoolToArchiveAWS"],
        "AWS_Cool_to_Azure_Archive": aws_costs["transferCostCoolToArchiveAzure"],
        "AWS_Cool_to_GCP_Archive": aws_costs["transferCostCoolToArchiveGCP"],
        "Azure_Cool_to_AWS_Archive": azure_costs["transferCostCoolToArchiveAWS"],
        "Azure_Cool_to_Azure_Archive": azure_costs["transferCostCoolToArchiveAzure"],
        "Azure_Cool_to_GCP_Archive": azure_costs["transferCostCoolToArchiveGCP"],
        "GCP_Cool_to_AWS_Archive": gcp_costs["transferCostCoolToArchiveAWS"],
        "GCP_Cool_to_Azure_Archive": gcp_costs["transferCostCoolToArchiveAzure"],
        "GCP_Cool_to_GCP_Archive": gcp_costs["transferCostCoolToArchiveGCP"],
    }

    graph = decision.build_graph_for_storage(
        aws_costs["resultHot"],
        azure_costs["resultHot"],
        gcp_costs["resultHot"],
        aws_costs["resultL3Cool"],
        azure_costs["resultL3Cool"],
        gcp_costs["resultL3Cool"],
        aws_costs["resultL3Archive"],
        azure_costs["resultL3Archive"],
        gcp_costs["resultL3Archive"],
        transfer_costs
    )

    # -------------------------------------------------------------------------
    # COMBINED L2 (HOT STORAGE) + L3 (DATA PROCESSING) OPTIMIZATION
    # -------------------------------------------------------------------------
    # Rationale: "Data Gravity" & Total System Cost
    #
    # We optimize the selection of the "Hot Path" (L2 Hot Storage + L3 Data Processing)
    # by considering the COMBINED cost of both layers rather than selecting L2 in isolation.
    #
    # The Problem:
    # - Storage (L2) might be cheapest on Provider A (e.g., Azure).
    # - Processing (L3) might be cheapest on Provider B (e.g., AWS).
    #
    # If we strictly picked the cheapest L2 (Provider A), we would be forced to either:
    # 1. Run L3 on Provider A (which might be very expensive for processing).
    # 2. Run L3 on Provider B (cheaper processing), BUT pay massive "Egress" (Data Transfer)
    #    costs to move data from A to B, plus "Ingestion" costs at B.
    #
    # The Solution:
    # We calculate `Cost(L2) + Cost(L3)` for each provider and pick the minimum sum.
    # This ensures we find the "Global Minimum" for the hot path, avoiding scenarios where
    # saving $10 on storage leads to paying $1000 extra in processing or transfer fees.
    # -------------------------------------------------------------------------

    # 1. Calculate combined costs (Unlocked Optimization)
    # We evaluate all 9 combinations of L2 Hot + L3 to find the global minimum.
    
    # Helper to get costs and data
    l2_candidates = [
        {"provider": "AWS", "key": "AWS_Hot", "cost": aws_costs["resultHot"]["totalMonthlyCost"], "data_gb": aws_costs["resultHot"]["dataSizeInGB"]},
        {"provider": "Azure", "key": "Azure_Hot", "cost": azure_costs["resultHot"]["totalMonthlyCost"], "data_gb": azure_costs["resultHot"]["dataSizeInGB"]},
        {"provider": "GCP", "key": "GCP_Hot", "cost": gcp_costs["resultHot"]["totalMonthlyCost"], "data_gb": gcp_costs["resultHot"]["dataSizeInGB"]}
    ]
    
    l3_candidates = [
        {"provider": "AWS", "key": "L3_AWS", "cost": aws_costs["dataProcessing"]["totalMonthlyCost"]},
        {"provider": "Azure", "key": "L3_Azure", "cost": azure_costs["dataProcessing"]["totalMonthlyCost"]},
        {"provider": "GCP", "key": "L3_GCP", "cost": gcp_costs["dataProcessing"]["totalMonthlyCost"]}
    ]
    
    combinations = []
    messages_per_month = params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730

    for l2 in l2_candidates:
        for l3 in l3_candidates:
            base_cost = l2["cost"] + l3["cost"]
            transfer_fee = 0
            glue_cost = 0
            
            if l2["provider"] != l3["provider"]:
                # Cross-Cloud Transfer (Egress from L2)
                # Note: Using simplified egress pricing or specific transfer keys
                if l2["provider"] == "AWS":
                    egress_price = pricing["aws"]["transfer"].get("egressPrice", 0.09)
                elif l2["provider"] == "Azure":
                    # Use Tier 1 as safe estimate
                    try:
                        egress_price = pricing["azure"]["transfer"]["pricing_tiers"]["tier1"]["price"]
                    except KeyError:
                        egress_price = 0.087
                elif l2["provider"] == "GCP":
                    egress_price = pricing["gcp"]["transfer"].get("egressPrice", 0.12)
                
                transfer_fee = l2["data_gb"] * egress_price
                
                # Glue Code (Reader Function at L3)
                if l3["provider"] == "AWS":
                    glue_cost = aws.calculate_aws_connector_function_cost(messages_per_month, pricing)
                elif l3["provider"] == "Azure":
                    glue_cost = azure.calculate_azure_connector_function_cost(messages_per_month, pricing)
                elif l3["provider"] == "GCP":
                    glue_cost = gcp.calculate_gcp_connector_function_cost(messages_per_month, pricing)

            total_cost = base_cost + transfer_fee + glue_cost
            combinations.append({
                "l2_key": l2["key"],
                "l3_key": l3["key"],
                "l2_provider": l2["provider"],
                "l3_provider": l3["provider"],
                "total_cost": total_cost,
                "base_cost": base_cost,
                "l2_cost": l2["cost"], # New: Breakdown
                "l3_cost": l3["cost"], # New: Breakdown
                "transfer_cost": transfer_fee,
                "glue_cost": glue_cost
            })

    # Sort by total cost
    combinations.sort(key=lambda x: x["total_cost"])
    l2_l3_combinations = combinations
    best_combination = combinations[0]
    
    best_hot_provider = best_combination["l2_key"]
    best_l3_provider_key = best_combination["l3_key"] # e.g. "L3_AWS"
    


    # 3. Check for Overrides (Warnings)
    
    # L2 Override Check
    l2_only_options = sorted(l2_candidates, key=lambda x: x["cost"])
    cheapest_l2_provider = l2_only_options[0]["key"]
    
    l2_optimization_override = None
    if best_hot_provider != cheapest_l2_provider:
        l2_optimization_override = {
            "selectedProvider": best_hot_provider.split("_")[0],
            "cheapestL2Provider": cheapest_l2_provider.split("_")[0],
            "savings": l2_only_options[0]["cost"] - [x["cost"] for x in l2_only_options if x["key"] == best_hot_provider][0]
        }

    # L3 Override Check
    l3_only_options = sorted(l3_candidates, key=lambda x: x["cost"])
    cheapest_l3_provider = l3_only_options[0]["key"]
    
    l3_optimization_override = None
    if best_l3_provider_key != cheapest_l3_provider:
         l3_optimization_override = {
            "selectedProvider": best_l3_provider_key.split("_")[1], # AWS from L3_AWS
            "cheapestL3Provider": cheapest_l3_provider.split("_")[1],
            "savings": l3_only_options[0]["cost"] - [x["cost"] for x in l3_only_options if x["key"] == best_l3_provider_key][0]
        }
    
    # Cross-Cloud Warning (New)
    # If we selected a cross-cloud path, we might want to flag it if it's interesting
    # For now, the existing override warnings will handle "Why didn't you pick cheapest L2?"
    # We might need to adjust the text in UI to explain "Global Optimization" vs "Locking"

    # 5. Find cheapest storage path STARTING from our optimized provider
    # We force the start node to be our chosen provider to respect Data Gravity
    cheapest_storage = decision.find_cheapest_storage_path(
        graph,
        [best_hot_provider], 
        ["AWS_Archive", "Azure_Archive", "GCP_Archive"]
    )


    aws_costs_after_layer1 = aws_costs["dataAquisition"]["totalMonthlyCost"]
    azure_costs_after_layer1 = azure_costs["dataAquisition"]["totalMonthlyCost"]
    gcp_costs_after_layer1 = gcp_costs["dataAquisition"]["totalMonthlyCost"]

    cheaper_provider_for_layer1 = ""
    cheaper_provider_for_layer3 = ""
    
    # Determine L1 and L3 based on Hot Storage start
    # Logic: Minimize (L1 cost + Transfer to Hot)
    # L3 is coupled to Hot Storage provider (as per original logic)
    
    hot_storage_provider = cheapest_storage["path"][0]
    

    
    # Add Cross-Cloud Glue Costs (L1 -> L2)
    # If L1 != L2 (Hot Storage Provider), add Connector + Ingestion costs
    # Note: L2 is coupled to Hot Storage Provider in this model for simplicity of "Hot Path"
    
    # AWS L1
    l1_aws_base = aws_costs_after_layer1
    l1_aws_transfer = transfer_costs.get(f"L1_AWS_to_{hot_storage_provider}", 0)
    l1_aws_glue = 0
    if hot_storage_provider != "AWS_Hot":
        l1_aws_glue += aws.calculate_aws_connector_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        if hot_storage_provider == "Azure_Hot":
            l1_aws_glue += azure.calculate_azure_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        elif hot_storage_provider == "GCP_Hot":
            l1_aws_glue += gcp.calculate_gcp_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
    l1_aws_total = l1_aws_base + l1_aws_transfer + l1_aws_glue

    # Azure L1
    l1_azure_base = azure_costs_after_layer1
    l1_azure_transfer = transfer_costs.get(f"L1_Azure_to_{hot_storage_provider}", 0)
    l1_azure_glue = 0
    if hot_storage_provider != "Azure_Hot":
        l1_azure_glue += azure.calculate_azure_connector_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        if hot_storage_provider == "AWS_Hot":
            l1_azure_glue += aws.calculate_aws_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        elif hot_storage_provider == "GCP_Hot":
            l1_azure_glue += gcp.calculate_gcp_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
    l1_azure_total = l1_azure_base + l1_azure_transfer + l1_azure_glue

    # GCP L1
    l1_gcp_base = gcp_costs_after_layer1
    l1_gcp_transfer = transfer_costs.get(f"L1_GCP_to_{hot_storage_provider}", 0)
    l1_gcp_glue = 0
    if hot_storage_provider != "GCP_Hot":
        l1_gcp_glue += gcp.calculate_gcp_connector_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        if hot_storage_provider == "AWS_Hot":
            l1_gcp_glue += aws.calculate_aws_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        elif hot_storage_provider == "Azure_Hot":
            l1_gcp_glue += azure.calculate_azure_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
    l1_gcp_total = l1_gcp_base + l1_gcp_transfer + l1_gcp_glue

    l1_detailed_options = [
        {"provider": "AWS", "base_cost": l1_aws_base, "transfer_cost": l1_aws_transfer, "glue_cost": l1_aws_glue, "total_cost": l1_aws_total},
        {"provider": "Azure", "base_cost": l1_azure_base, "transfer_cost": l1_azure_transfer, "glue_cost": l1_azure_glue, "total_cost": l1_azure_total},
        {"provider": "GCP", "base_cost": l1_gcp_base, "transfer_cost": l1_gcp_transfer, "glue_cost": l1_gcp_glue, "total_cost": l1_gcp_total}
    ]
    
    # Sort by total cost
    l1_detailed_options.sort(key=lambda x: x["total_cost"])
    cheaper_provider_for_layer1 = "L1_" + l1_detailed_options[0]["provider"]
    # Use the optimized L3 provider we found earlier (Unlocked Optimization)
    cheaper_provider_for_layer3 = best_l3_provider_key

    # Layer 5
    l5_options = [
        ("L5_AWS", aws_costs["resultL5"]["totalMonthlyCost"]),
        ("L5_Azure", azure_costs["resultL5"]["totalMonthlyCost"]),
        ("L5_GCP", gcp_costs["resultL5"]["totalMonthlyCost"])
    ]
    l5_options.sort(key=lambda x: x[1])
    cheaper_provider_layer5 = l5_options[0][0]

    cheapest_path = []
    cheapest_path.append(cheaper_provider_for_layer1)
    for x in cheapest_storage["path"]:
        cheapest_path.append("L2_" + x)
    cheapest_path.append(cheaper_provider_for_layer3)

    # Layer 4
    l4_options = []
    if aws_costs["resultL4"]:
        l4_options.append({"key": "L4_AWS", "base_cost": aws_costs["resultL4"]["totalMonthlyCost"]})
    if azure_costs["resultL4"]:
        l4_options.append({"key": "L4_Azure", "base_cost": azure_costs["resultL4"]["totalMonthlyCost"]})
    if gcp_costs["resultL4"]:
        l4_options.append({"key": "L4_GCP", "base_cost": gcp_costs["resultL4"]["totalMonthlyCost"]})
    
    # Add Cross-Cloud Glue Costs (L3 -> L4)
    # If L3 != L4, add L3 API Gateway + L3 Hot Reader
    # L3 Provider is derived from the OPTIMAL L3 provider found in step 2
    l3_provider_name = best_l3_provider_key.split("_")[1] # AWS, Azure, GCP
    
    # Calculate common glue costs for L3
    l3_api_gateway_cost = 0
    l3_reader_cost = 0
    
    # Number of dashboard queries
    num_queries = params["dashboardActiveHoursPerDay"] * params["dashboardRefreshesPerHour"] * 30
    
    if l3_provider_name == "AWS":
        l3_api_gateway_cost = aws.calculate_aws_api_gateway_cost(num_queries, pricing)
        l3_reader_cost = aws.calculate_aws_reader_function_cost(num_queries, pricing)
    elif l3_provider_name == "Azure":
        l3_api_gateway_cost = azure.calculate_azure_api_management_cost(num_queries, pricing)
        l3_reader_cost = azure.calculate_azure_reader_function_cost(num_queries, pricing)
    elif l3_provider_name == "GCP":
        l3_api_gateway_cost = gcp.calculate_gcp_api_gateway_cost(num_queries, pricing)
        l3_reader_cost = gcp.calculate_gcp_reader_function_cost(num_queries, pricing)

    # Update L4 options with glue costs AND update the main result objects
    updated_l4_options = []
    for opt in l4_options:
        l4_provider_name = opt["key"].split("_")[1] # AWS, Azure, GCP
        
        glue_cost = 0
        if l4_provider_name != l3_provider_name:
            glue_cost = l3_api_gateway_cost + l3_reader_cost
            
        opt["glue_cost"] = glue_cost
        opt["total_cost"] = opt["base_cost"] + glue_cost
        updated_l4_options.append(opt)

        # Update the main cost dictionary for this provider so the UI receives the full cost
        if l4_provider_name == "AWS" and aws_costs.get("resultL4"):
             aws_costs["resultL4"]["glueCodeCost"] = glue_cost
             aws_costs["resultL4"]["totalMonthlyCost"] += glue_cost
        elif l4_provider_name == "Azure" and azure_costs.get("resultL4"):
             azure_costs["resultL4"]["glueCodeCost"] = glue_cost
             azure_costs["resultL4"]["totalMonthlyCost"] += glue_cost
        elif l4_provider_name == "GCP" and gcp_costs.get("resultL4"):
             gcp_costs["resultL4"]["glueCodeCost"] = glue_cost
             gcp_costs["resultL4"]["totalMonthlyCost"] += glue_cost
    
    l4_detailed_options = updated_l4_options
    
    if l4_detailed_options:
        l4_detailed_options.sort(key=lambda x: x["total_cost"])
        cheaper_provider_layer4 = l4_detailed_options[0]["key"]
    else:
        cheaper_provider_layer4 = "L4_None"

    cheapest_path.append(cheaper_provider_layer4)
    cheapest_path.append(cheaper_provider_layer5)

    # 6. Check for L1 Optimization Override
    l1_only_options = sorted(l1_detailed_options, key=lambda x: x["base_cost"])
    cheapest_l1_provider = l1_only_options[0]["provider"]
    selected_l1_provider = cheaper_provider_for_layer1.split("_")[1]

    l1_optimization_override = None
    if selected_l1_provider != cheapest_l1_provider:
        l1_optimization_override = {
            "selectedProvider": selected_l1_provider,
            "cheapestProvider": cheapest_l1_provider,
            "savings": l1_only_options[0]["base_cost"] - [x["base_cost"] for x in l1_detailed_options if x["provider"] == selected_l1_provider][0],
            "candidates": l1_detailed_options
        }

    # 7. Check for L4 Optimization Override
    l4_optimization_override = None
    
    # Filter out None/0 costs
    l4_valid_options = [x for x in l4_detailed_options if x["base_cost"] > 0]
    
    if l4_valid_options:
        # Sort by BASE cost for override check
        l4_valid_options_by_base = sorted(l4_valid_options, key=lambda x: x["base_cost"])
        cheapest_l4_provider = l4_valid_options_by_base[0]["key"].split("_")[1]
        
        selected_l4_provider = cheaper_provider_layer4.split("_")[1] if cheaper_provider_layer4 != "L4_None" else "None"
        
        if selected_l4_provider != "None" and selected_l4_provider != cheapest_l4_provider:
            l4_optimization_override = {
                "selectedProvider": selected_l4_provider,
                "cheapestProvider": cheapest_l4_provider,
                "savings": l4_valid_options_by_base[0]["base_cost"] - [x["base_cost"] for x in l4_valid_options if x["key"] == f"L4_{selected_l4_provider}"][0],
                "candidates": l4_detailed_options
            }

    # 8. Check for L2 Cool Optimization Override
    # Extract selected Cool provider from cheapest_storage path
    # Path format: ['AWS_Hot', 'GCP_Cool', 'GCP_Archive']
    selected_cool_provider = "None"
    for segment in cheapest_storage["path"]:
        if "Cool" in segment:
            selected_cool_provider = segment.split("_")[0] # AWS
            break
            
    l2_cool_only_options = [
        ("AWS", aws_costs["resultL3Cool"]["totalMonthlyCost"]),
        ("Azure", azure_costs["resultL3Cool"]["totalMonthlyCost"]),
        ("GCP", gcp_costs["resultL3Cool"]["totalMonthlyCost"])
    ]
    l2_cool_only_options.sort(key=lambda x: x[1])
    cheapest_cool_provider = l2_cool_only_options[0][0]
    
    # Calculate Cool Storage Combinations for UI Table (Full Path: Hot -> Cool -> Archive)
    cool_combinations = []
    hot_provider = best_hot_provider.split("_")[0] # e.g. "Azure"
    
    # Get Data Volume (using Hot provider's data size as proxy for transfer)
    data_vol = 0
    if hot_provider == "AWS": data_vol = aws_costs["resultHot"]["dataSizeInGB"]
    elif hot_provider == "Azure": data_vol = azure_costs["resultHot"]["dataSizeInGB"]
    elif hot_provider == "GCP": data_vol = gcp_costs["resultHot"]["dataSizeInGB"]

    archive_options_map = {
        "AWS": aws_costs["resultL3Archive"]["totalMonthlyCost"],
        "Azure": azure_costs["resultL3Archive"]["totalMonthlyCost"],
        "GCP": gcp_costs["resultL3Archive"]["totalMonthlyCost"]
    }

    for opt in l2_cool_only_options:
        cool_prov = opt[0]
        cool_cost = opt[1]
        
        # 1. Transfer Hot -> Cool
        # Use pre-calculated transfer costs from the main dictionary to ensure consistency
        # Key format: "{HotProvider}_Hot_to_{CoolProvider}_Cool"
        transfer_key = f"{hot_provider}_Hot_to_{cool_prov}_Cool"
        trans_h_c = transfer_costs.get(transfer_key, 0)

        # 2. Find Best Archive for this Cool Provider
        best_archive_for_cool = None
        min_path_cost = float('inf')

        for arch_prov, arch_cost in archive_options_map.items():
            # Transfer Cool -> Archive
            # Use pre-calculated transfer costs
            # Key format: "{CoolProvider}_Cool_to_{ArchiveProvider}_Archive"
            transfer_key_ca = f"{cool_prov}_Cool_to_{arch_prov}_Archive"
            trans_c_a = transfer_costs.get(transfer_key_ca, 0)
            
            total_path_cost = cool_cost + trans_h_c + arch_cost + trans_c_a
            
            if total_path_cost < min_path_cost:
                min_path_cost = total_path_cost
                best_archive_for_cool = {
                    "archive_provider": arch_prov,
                    "archive_cost": arch_cost,
                    "trans_c_a": trans_c_a,
                    "total_path_cost": total_path_cost
                }

        if best_archive_for_cool:
            cool_combinations.append({
                "path": f"{hot_provider} -> {cool_prov} -> {best_archive_for_cool['archive_provider']}",
                "trans_h_c": trans_h_c,
                "cool_cost": cool_cost,
                "trans_c_a": best_archive_for_cool['trans_c_a'],
                "archive_cost": best_archive_for_cool['archive_cost'],
                "total_cost": best_archive_for_cool['total_path_cost']
            })

    cool_combinations.sort(key=lambda x: x["total_cost"])

    l2_cool_optimization_override = None
    if selected_cool_provider != "None" and selected_cool_provider != cheapest_cool_provider:
         l2_cool_optimization_override = {
            "selectedProvider": selected_cool_provider,
            "cheapestProvider": cheapest_cool_provider,
            "savings": 0 # Savings are complex in full path, leaving 0 or calculating diff
        }

    # 9. Check for L2 Archive Optimization Override
    selected_archive_provider = "None"
    for segment in cheapest_storage["path"]:
        if "Archive" in segment:
            selected_archive_provider = segment.split("_")[0]
            break
            
    l2_archive_only_options = [
        ("AWS", aws_costs["resultL3Archive"]["totalMonthlyCost"]),
        ("Azure", azure_costs["resultL3Archive"]["totalMonthlyCost"]),
        ("GCP", gcp_costs["resultL3Archive"]["totalMonthlyCost"])
    ]
    l2_archive_only_options.sort(key=lambda x: x[1])
    cheapest_archive_provider = l2_archive_only_options[0][0]

    # Calculate Archive Combinations (Cool -> Archive)
    archive_combinations = []
    # We need the SELECTED Cool provider for this context
    current_cool_provider = selected_cool_provider if selected_cool_provider != "None" else hot_provider # Fallback

    for opt in l2_archive_only_options:
        arch_prov = opt[0]
        arch_cost = opt[1]
        trans_c_a = 0
        
        # Use pre-calculated transfer costs
        # Key format: "{CoolProvider}_Cool_to_{ArchiveProvider}_Archive"
        transfer_key = f"{current_cool_provider}_Cool_to_{arch_prov}_Archive"
        trans_c_a = transfer_costs.get(transfer_key, 0)

        archive_combinations.append({
            "path": f"... -> {current_cool_provider} -> {arch_prov}",
            "trans_c_a": trans_c_a,
            "archive_cost": arch_cost,
            "total_cost": arch_cost + trans_c_a
        })
    
    archive_combinations.sort(key=lambda x: x["total_cost"])

    l2_archive_optimization_override = None
    if selected_archive_provider != "None" and selected_archive_provider != cheapest_archive_provider:
        l2_archive_optimization_override = {
            "selectedProvider": selected_archive_provider,
            "cheapestProvider": cheapest_archive_provider,
            "savings": l2_archive_only_options[0][1] - [x[1] for x in l2_archive_only_options if x[0] == selected_archive_provider][0]
        }

    calculation_result_obj = {}
    calculation_result_obj["L1"] = cheaper_provider_for_layer1.split("_")[1]

    calculation_result_l2_list = [x.split("_")[0] for x in cheapest_storage["path"]]
    
    calculation_result_obj["L2"] = {}
    calculation_result_obj["L2"]["Hot"] = calculation_result_l2_list[0]
    calculation_result_obj["L2"]["Cool"] = calculation_result_l2_list[1]
    calculation_result_obj["L2"]["Archive"] = calculation_result_l2_list[2]

    calculation_result_obj["L3"] = cheaper_provider_for_layer3.split("_")[1]
    
    if cheaper_provider_layer4 != "L4_None":
        calculation_result_obj["L4"] = cheaper_provider_layer4.split("_")[1]
    else:
        calculation_result_obj["L4"] = "None"
        
    calculation_result_obj["L5"] = cheaper_provider_layer5.split("_")[1]

    result = {
        "calculationResult": calculation_result_obj,
        "cheapestPath": cheapest_path,
        "awsCosts": aws_costs,
        "azureCosts": azure_costs,
        "gcpCosts": gcp_costs,
        "l2OptimizationOverride": l2_optimization_override,
        "l3OptimizationOverride": l3_optimization_override,
        "l4OptimizationOverride": l4_optimization_override,
        "l1OptimizationOverride": l1_optimization_override,
        "l2CoolOptimizationOverride": l2_cool_optimization_override,
        "l2ArchiveOptimizationOverride": l2_archive_optimization_override,
        "l2_l3_combinations": l2_l3_combinations,
        "l2_cool_combinations": cool_combinations,
        "l2_archive_combinations": archive_combinations
    }
    
    # Currency Conversion (USD -> EUR) if requested
    currency = params.get("currency", "USD")
    if currency == "EUR":
        from backend.pricing_utils import get_currency_rates
        from decimal import Decimal
        
        try:
            rates = get_currency_rates()
            eur_rate = Decimal(str(rates["usd_to_eur_rate"]))
            
            def convert_recursive(data):
                if isinstance(data, dict):
                    return {k: convert_recursive(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return [convert_recursive(i) for i in data]
                elif isinstance(data, (int, float)):
                    amount = Decimal(str(data)) * eur_rate
                    return float(amount.quantize(Decimal("0.000000000001")))
                else:
                    return data
                    
            result = convert_recursive(result)
            result["currency"] = "EUR"
        except Exception as e:
            # Fallback if conversion fails
            print(f"Currency conversion failed: {e}")
            result["currency"] = "USD"
    else:
        result["currency"] = "USD"

    return result
