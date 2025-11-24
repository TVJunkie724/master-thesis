
import json
import math
from backend.calculation import aws, azure, gcp, transfer, decision
from backend.config_loader import load_json_file
import backend.constants as CONSTANTS

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
        pricing
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
        pricing
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
        pricing
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
    
    1. Calculates costs for AWS, Azure, and GCP independently.
    2. Aggregates all possible transfer costs between providers and storage tiers.
    3. Builds a graph representing storage tiers (Hot -> Cool -> Archive) and their connections.
    4. Uses Dijkstra's algorithm (via decision.py) to find the cheapest path through storage layers.
    5. Determines the cheapest provider for Layer 1 (Data Acquisition) and Layer 3 (Data Processing)
       based on the selected Hot Storage provider to minimize transfer costs.
    6. Determines the cheapest provider for Layer 4 (Twin Management) and Layer 5 (Visualization).
    
    Returns a comprehensive result object with the cheapest path, detailed costs, and currency info.
    """
    if pricing is None:
        pricing = load_json_file(CONSTANTS.DYNAMIC_PRICING_FILE_PATH)

    aws_costs = calculate_aws_costs(params, pricing)
    azure_costs = calculate_azure_costs(params, pricing)
    gcp_costs = calculate_gcp_costs(params, pricing)

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

    cheapest_storage = decision.find_cheapest_storage_path(
        graph,
        ["AWS_Hot", "Azure_Hot", "GCP_Hot"],
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
    # The cheapest storage path determines the "backbone" of the architecture.
    # We then select the best L1 provider that minimizes the total cost of L1 + Transfer to that Hot Storage.
    
    hot_storage_provider = cheapest_storage["path"][0]
    
    l1_options = [
        ("L1_AWS", aws_costs_after_layer1 + transfer_costs.get(f"L1_AWS_to_{hot_storage_provider}", 0)),
        ("L1_Azure", azure_costs_after_layer1 + transfer_costs.get(f"L1_Azure_to_{hot_storage_provider}", 0)),
        ("L1_GCP", gcp_costs_after_layer1 + transfer_costs.get(f"L1_GCP_to_{hot_storage_provider}", 0))
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
    
    if l4_options:
        l4_options.sort(key=lambda x: x[1])
        cheaper_provider_layer4 = l4_options[0][0]
    else:
        cheaper_provider_layer4 = "L4_None"

    cheapest_path.append(cheaper_provider_layer4)
    cheapest_path.append(cheaper_provider_layer5)

    calculation_result_obj = {}
    calculation_result_obj["L1"] = cheaper_provider_for_layer1.split("_")[1]

    calculation_result_l2_list = [x.split("_")[0] for x in cheapest_storage["path"]]
    
    calculation_result_obj["L2"] = {}



def calculate_cheapest_costs(params, pricing=None):
    if pricing is None:
        pricing = load_json_file(CONSTANTS.DYNAMIC_PRICING_FILE_PATH)

    aws_costs = calculate_aws_costs(params, pricing)
    azure_costs = calculate_azure_costs(params, pricing)
    gcp_costs = calculate_gcp_costs(params, pricing)

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

    cheapest_storage = decision.find_cheapest_storage_path(
        graph,
        ["AWS_Hot", "Azure_Hot", "GCP_Hot"],
        ["AWS_Archive", "Azure_Archive", "GCP_Archive"]
    )
    print(cheapest_storage)

    aws_costs_after_layer1 = aws_costs["dataAquisition"]["totalMonthlyCost"]
    azure_costs_after_layer1 = azure_costs["dataAquisition"]["totalMonthlyCost"]
    gcp_costs_after_layer1 = gcp_costs["dataAquisition"]["totalMonthlyCost"]

    cheaper_provider_for_layer1 = ""
    cheaper_provider_for_layer3 = ""
    
    # Determine L1 and L3 based on Hot Storage start
    # Logic: Minimize (L1 cost + Transfer to Hot)
    # L3 is coupled to Hot Storage provider (as per original logic)
    
    hot_storage_provider = cheapest_storage["path"][0]
    
    l1_options = [
        ("L1_AWS", aws_costs_after_layer1 + transfer_costs.get(f"L1_AWS_to_{hot_storage_provider}", 0)),
        ("L1_Azure", azure_costs_after_layer1 + transfer_costs.get(f"L1_Azure_to_{hot_storage_provider}", 0)),
        ("L1_GCP", gcp_costs_after_layer1 + transfer_costs.get(f"L1_GCP_to_{hot_storage_provider}", 0))
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
    
    if l4_options:
        l4_options.sort(key=lambda x: x[1])
        cheaper_provider_layer4 = l4_options[0][0]
    else:
        cheaper_provider_layer4 = "L4_None"

    cheapest_path.append(cheaper_provider_layer4)
    cheapest_path.append(cheaper_provider_layer5)

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
        "gcpCosts": gcp_costs
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
