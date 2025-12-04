
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

    azure_result_layer4 = None
    if not params["needs3DModel"]:
        azure_result_layer4 = azure.calculate_azure_digital_twins_cost(
            params["numberOfDevices"],
            params["deviceSendingIntervalInMinutes"],
            params["averageSizeOfMessageInKb"],
            params["dashboardRefreshesPerHour"],
            params["dashboardActiveHoursPerDay"],
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

    # 1. Calculate combined costs
    aws_l2_l3_total = aws_costs["resultHot"]["totalMonthlyCost"] + aws_costs["dataProcessing"]["totalMonthlyCost"]
    azure_l2_l3_total = azure_costs["resultHot"]["totalMonthlyCost"] + azure_costs["dataProcessing"]["totalMonthlyCost"]
    gcp_l2_l3_total = gcp_costs["resultHot"]["totalMonthlyCost"] + gcp_costs["dataProcessing"]["totalMonthlyCost"]

    l2_l3_options = [
        ("AWS_Hot", aws_l2_l3_total),
        ("Azure_Hot", azure_l2_l3_total),
        ("GCP_Hot", gcp_l2_l3_total)
    ]
    l2_l3_options.sort(key=lambda x: x[1])
    
    # 2. Select the best provider for the Hot Path
    best_hot_provider = l2_l3_options[0][0] # e.g., "Azure_Hot"

    # 3. Check if this overrides the "Cheapest L2" (for UI warning)
    # Find who would have been chosen if we only looked at L2
    l2_only_options = [
        ("AWS_Hot", aws_costs["resultHot"]["totalMonthlyCost"]),
        ("Azure_Hot", azure_costs["resultHot"]["totalMonthlyCost"]),
        ("GCP_Hot", gcp_costs["resultHot"]["totalMonthlyCost"])
    ]
    l2_only_options.sort(key=lambda x: x[1])
    cheapest_l2_provider = l2_only_options[0][0]

    l2_optimization_override = None
    if best_hot_provider != cheapest_l2_provider:
        l2_optimization_override = {
            "selectedProvider": best_hot_provider.split("_")[0], # AWS
            "cheapestL2Provider": cheapest_l2_provider.split("_")[0], # Azure
            "savings": l2_only_options[0][1] - [x[1] for x in l2_only_options if x[0] == best_hot_provider][0] # Negative value showing higher storage cost
        }

    # 4. Check if L3 is suboptimal (locked by L2)
    # Find who would have been chosen if we only looked at L3
    l3_only_options = [
        ("AWS_Hot", aws_costs["dataProcessing"]["totalMonthlyCost"]),
        ("Azure_Hot", azure_costs["dataProcessing"]["totalMonthlyCost"]),
        ("GCP_Hot", gcp_costs["dataProcessing"]["totalMonthlyCost"])
    ]
    l3_only_options.sort(key=lambda x: x[1])
    cheapest_l3_provider = l3_only_options[0][0]

    l3_optimization_override = None
    # If the selected provider (best_hot_provider) is NOT the cheapest L3 provider
    if best_hot_provider != cheapest_l3_provider:
         l3_optimization_override = {
            "selectedProvider": best_hot_provider.split("_")[0], # AWS
            "cheapestL3Provider": cheapest_l3_provider.split("_")[0], # Azure
            "savings": l3_only_options[0][1] - [x[1] for x in l3_only_options if x[0] == best_hot_provider][0]
        }

    # 5. Find cheapest storage path STARTING from our optimized provider
    # We force the start node to be our chosen provider to respect Data Gravity
    cheapest_storage = decision.find_cheapest_storage_path(
        graph,
        [best_hot_provider], 
        ["AWS_Archive", "Azure_Archive", "GCP_Archive"]
    )
    print(f"Optimized Storage Path (L2+L3): {cheapest_storage}")

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
    l1_aws_cost = aws_costs_after_layer1 + transfer_costs.get(f"L1_AWS_to_{hot_storage_provider}", 0)
    if hot_storage_provider != "AWS_Hot":
        # L1=AWS, L2!=AWS. Add AWS Connector + Target Ingestion
        l1_aws_cost += aws.calculate_aws_connector_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        if hot_storage_provider == "Azure_Hot":
            l1_aws_cost += azure.calculate_azure_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        elif hot_storage_provider == "GCP_Hot":
            l1_aws_cost += gcp.calculate_gcp_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)

    # Azure L1
    l1_azure_cost = azure_costs_after_layer1 + transfer_costs.get(f"L1_Azure_to_{hot_storage_provider}", 0)
    if hot_storage_provider != "Azure_Hot":
        l1_azure_cost += azure.calculate_azure_connector_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        if hot_storage_provider == "AWS_Hot":
            l1_azure_cost += aws.calculate_aws_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        elif hot_storage_provider == "GCP_Hot":
            l1_azure_cost += gcp.calculate_gcp_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)

    # GCP L1
    l1_gcp_cost = gcp_costs_after_layer1 + transfer_costs.get(f"L1_GCP_to_{hot_storage_provider}", 0)
    if hot_storage_provider != "GCP_Hot":
        l1_gcp_cost += gcp.calculate_gcp_connector_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        if hot_storage_provider == "AWS_Hot":
            l1_gcp_cost += aws.calculate_aws_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)
        elif hot_storage_provider == "Azure_Hot":
            l1_gcp_cost += azure.calculate_azure_ingestion_function_cost(params["numberOfDevices"] * (60 / params["deviceSendingIntervalInMinutes"]) * 730, pricing)

    l1_options = [
        ("L1_AWS", l1_aws_cost),
        ("L1_Azure", l1_azure_cost),
        ("L1_GCP", l1_gcp_cost)
    ]
    
    # Sort by cost
    l1_options.sort(key=lambda x: x[1])
    cheaper_provider_for_layer1 = l1_options[0][0]
    
    if hot_storage_provider == "AWS_Hot":
        cheaper_provider_for_layer3 = "L3_AWS"
    elif hot_storage_provider == "Azure_Hot":
        cheaper_provider_for_layer3 = "L3_Azure"
    elif hot_storage_provider == "GCP_Hot":
        cheaper_provider_for_layer3 = "L3_GCP"
    else:
        print("Storage Path incorrect!")

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
        l4_options.append(("L4_AWS", aws_costs["resultL4"]["totalMonthlyCost"]))
    if azure_costs["resultL4"]:
        l4_options.append(("L4_Azure", azure_costs["resultL4"]["totalMonthlyCost"]))
    if gcp_costs["resultL4"]:
        l4_options.append(("L4_GCP", gcp_costs["resultL4"]["totalMonthlyCost"]))
    
    # Add Cross-Cloud Glue Costs (L3 -> L4)
    # If L3 != L4, add L3 API Gateway + L3 Hot Reader
    # L3 Provider is derived from hot_storage_provider (e.g., "AWS_Hot" -> "AWS")
    l3_provider_name = hot_storage_provider.split("_")[0] # AWS, Azure, GCP
    
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

    # Update L4 options with glue costs
    updated_l4_options = []
    for l4_name, l4_cost in l4_options:
        l4_provider_name = l4_name.split("_")[1] # AWS, Azure, GCP
        
        final_cost = l4_cost
        if l4_provider_name != l3_provider_name:
            final_cost += l3_api_gateway_cost + l3_reader_cost
            
        updated_l4_options.append((l4_name, final_cost))
    
    l4_options = updated_l4_options
    
    if l4_options:
        l4_options.sort(key=lambda x: x[1])
        cheaper_provider_layer4 = l4_options[0][0]
    else:
        cheaper_provider_layer4 = "L4_None"

    cheapest_path.append(cheaper_provider_layer4)
    cheapest_path.append(cheaper_provider_layer5)

    # 7. Check for L4 Optimization Override
    l4_only_options = [
        ("AWS", aws_costs["resultL4"]["totalMonthlyCost"] if aws_costs["resultL4"] else 0),
        ("Azure", azure_costs["resultL4"]["totalMonthlyCost"] if azure_costs["resultL4"] else 0),
        ("GCP", gcp_costs["resultL4"]["totalMonthlyCost"] if gcp_costs["resultL4"] else 0)
    ]
    # Filter out 0 costs if any (unless all are 0)
    l4_valid_options = [x for x in l4_only_options if x[1] > 0]
    if not l4_valid_options: l4_valid_options = l4_only_options
    
    l4_valid_options.sort(key=lambda x: x[1])
    cheapest_l4_provider = l4_valid_options[0][0]
    
    selected_l4_provider = cheaper_provider_layer4.split("_")[1] if cheaper_provider_layer4 != "L4_None" else "None"
    
    l4_optimization_override = None
    if selected_l4_provider != "None" and selected_l4_provider != cheapest_l4_provider:
        l4_optimization_override = {
            "selectedProvider": selected_l4_provider,
            "cheapestL4Provider": cheapest_l4_provider,
            "savings": l4_valid_options[0][1] - [x[1] for x in l4_valid_options if x[0] == selected_l4_provider][0]
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
    
    l2_cool_optimization_override = None
    if selected_cool_provider != "None" and selected_cool_provider != cheapest_cool_provider:
         l2_cool_optimization_override = {
            "selectedProvider": selected_cool_provider,
            "cheapestProvider": cheapest_cool_provider,
            "savings": l2_cool_only_options[0][1] - [x[1] for x in l2_cool_only_options if x[0] == selected_cool_provider][0]
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
        "l2CoolOptimizationOverride": l2_cool_optimization_override
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
