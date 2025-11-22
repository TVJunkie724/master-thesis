

def calculate_egress_cost(data_size_in_gb, transfer_config):
    """
    Generic function to calculate egress cost based on tiered pricing.
    transfer_config should have a 'pricing_tiers' key.
    """
    pricing_tiers = transfer_config.get("pricing_tiers", {})
    
    # Sort tiers by limit if possible, or assume standard naming tier1, tier2...
    # But the existing code accesses them by name.
    # Let's try to be generic but robust.
    
    # If pricing_tiers is empty, return 0
    if not pricing_tiers:
        return 0
        
    # Check for free tier
    free_tier = pricing_tiers.get("freeTier", {"limit": 0, "price": 0})
    free_limit = free_tier.get("limit", 0)
    
    if data_size_in_gb <= free_limit:
        return 0
        
    remaining_data = data_size_in_gb - free_limit
    total_cost = 0.0
    
    # We need an ordered list of tiers. 
    # Assuming tier1, tier2, tier3...
    # Let's look for keys starting with "tier" and sort them.
    tier_keys = [k for k in pricing_tiers.keys() if k.startswith("tier")]
    # Sort by the number in the key, e.g. tier1 < tier2
    def get_tier_num(k):
        try:
            return int(k.replace("tier", ""))
        except:
            return 999
    tier_keys.sort(key=get_tier_num)
    
    for key in tier_keys:
        tier = pricing_tiers[key]
        limit = tier.get("limit")
        price = tier.get("price", 0)
        
        if limit == "Infinity":
            # Last tier
            total_cost += remaining_data * price
            remaining_data = 0
            break
        
        limit = float(limit)
        
        if remaining_data <= limit:
            total_cost += remaining_data * price
            remaining_data = 0
            break
        else:
            total_cost += limit * price
            remaining_data -= limit
            
    return total_cost

def calculate_transfer_cost_from_aws_to_internet(data_size_in_gb, pricing):
    transfer_pricing = pricing["aws"]["transfer"]["pricing_tiers"]
    free_tier_limit = transfer_pricing["freeTier"]["limit"]
    tier1_limit = transfer_pricing["tier1"]["limit"]
    tier2_limit = transfer_pricing["tier2"]["limit"]
    tier3_limit = transfer_pricing["tier3"]["limit"]
    # tier4_limit = transfer_pricing["tier4"]["limit"] # Infinity

    tier1_price = transfer_pricing["tier1"]["price"]
    tier2_price = transfer_pricing["tier2"]["price"]
    tier3_price = transfer_pricing["tier3"]["price"]
    tier4_price = transfer_pricing["tier4"]["price"]

    total_cost = 0.0

    if data_size_in_gb <= free_tier_limit:
        return total_cost
    
    data_size_in_gb -= free_tier_limit

    if data_size_in_gb <= tier1_limit:
        total_cost = data_size_in_gb * tier1_price
    elif data_size_in_gb <= tier1_limit + tier2_limit:
        total_cost = (tier1_limit * tier1_price) + \
                     ((data_size_in_gb - tier1_limit) * tier2_price)
    elif data_size_in_gb <= tier1_limit + tier2_limit + tier3_limit:
        total_cost = (tier1_limit * tier1_price) + \
                     (tier2_limit * tier2_price) + \
                     ((data_size_in_gb - tier1_limit - tier2_limit) * tier3_price)
    else:
        total_cost = (tier1_limit * tier1_price) + \
                     (tier2_limit * tier2_price) + \
                     (tier3_limit * tier3_price) + \
                     ((data_size_in_gb - tier1_limit - tier2_limit - tier3_limit) * tier4_price)

    return total_cost

def calculate_transfer_cost_from_azure_to_internet(data_size_in_gb, pricing):
    transfer_pricing = pricing["azure"]["transfer"]["pricing_tiers"]
    remaining_data = data_size_in_gb
    total_cost = 0.0

    if remaining_data <= transfer_pricing["freeTier"]["limit"]:
        return total_cost
    
    remaining_data -= transfer_pricing["freeTier"]["limit"]

    if remaining_data <= transfer_pricing["tier1"]["limit"]:
        total_cost += remaining_data * transfer_pricing["tier1"]["price"]
        return total_cost
    
    total_cost += transfer_pricing["tier1"]["limit"] * transfer_pricing["tier1"]["price"]
    remaining_data -= transfer_pricing["tier1"]["limit"]

    if remaining_data <= transfer_pricing["tier2"]["limit"]:
        total_cost += remaining_data * transfer_pricing["tier2"]["price"]
        return total_cost
    
    total_cost += transfer_pricing["tier2"]["limit"] * transfer_pricing["tier2"]["price"]
    remaining_data -= transfer_pricing["tier2"]["limit"]

    if remaining_data <= transfer_pricing["tier3"]["limit"]:
        total_cost += remaining_data * transfer_pricing["tier3"]["price"]
        return total_cost
    
    total_cost += transfer_pricing["tier3"]["limit"] * transfer_pricing["tier3"]["price"]
    remaining_data -= transfer_pricing["tier3"]["limit"]

    total_cost += remaining_data * transfer_pricing["tier4"]["price"]

    return total_cost

# Transfer costs between Layer 2 and Layer 3 (Hot)

def calculate_transfer_cost_from_l2_aws_to_aws_hot(data_size_in_gb):
    return 0

def calculate_transfer_cost_from_l2_aws_to_azure_hot(data_size_in_gb, pricing):
    return calculate_transfer_cost_from_aws_to_internet(data_size_in_gb, pricing)

def calculate_transfer_cost_from_l2_azure_to_aws_hot(data_size_in_gb, pricing):
    return calculate_transfer_cost_from_azure_to_internet(data_size_in_gb, pricing)

def calculate_transfer_cost_from_l2_azure_to_azure_hot(data_size_in_gb):
    return 0

# Transfer costs between Layer 3 (Hot) and Layer 3 (Cool)

def calculate_transfer_cost_from_aws_hot_to_aws_cool(data_size_in_gb, pricing):
    transfer_cost = pricing["aws"]["s3InfrequentAccess"]["transferCostFromDynamoDB"]
    return data_size_in_gb * transfer_cost

def calculate_transfer_cost_from_aws_hot_to_azure_cool(data_size_in_gb, pricing):
    return calculate_transfer_cost_from_aws_to_internet(data_size_in_gb, pricing)

def calculate_transfer_costs_from_azure_hot_to_aws_cool(data_size_in_gb, pricing):
    transfer_cost_from_cosmos_to_s3 = pricing["aws"]["s3InfrequentAccess"]["transferCostFromCosmosDB"]
    return (data_size_in_gb * transfer_cost_from_cosmos_to_s3) + \
           calculate_transfer_cost_from_azure_to_internet(data_size_in_gb, pricing)

def calculate_transfer_cost_from_azure_hot_to_azure_cool(data_size_in_gb, pricing):
    transfer_cost = pricing["azure"]["blobStorageCool"]["transferCostFromCosmosDB"]
    # First 5GB are free? Logic from JS: dataSizeInGB <= 5 ? 0 : (dataSizeInGB - 5) * transferCostFromCosmosDBToAzure;
    if data_size_in_gb <= 5:
        return 0
    return (data_size_in_gb - 5) * transfer_cost

# Transfer costs between Layer 3 (Cool) and Layer 3 (Archive)

def calculate_transfer_cost_from_aws_cool_to_aws_archive(data_size_in_gb):
    return 0

def calculate_transfer_cost_from_aws_cool_to_azure_archive(data_size_in_gb, pricing):
    return calculate_transfer_cost_from_aws_to_internet(data_size_in_gb, pricing)

def calculate_transfer_cost_from_azure_cool_to_aws_archive(data_size_in_gb, pricing):
    return calculate_transfer_cost_from_azure_to_internet(data_size_in_gb, pricing)

def calculate_transfer_cost_from_azure_cool_to_azure_archive(data_size_in_gb):
    return 0

def calculate_transfer_cost_from_l2_gcp_to_gcp_hot(data_size_in_gb):
    return 0

def calculate_transfer_cost_from_l2_gcp_to_aws_hot(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["gcp"]["transfer"])

def calculate_transfer_cost_from_l2_gcp_to_azure_hot(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["gcp"]["transfer"])

def calculate_transfer_cost_from_l2_aws_to_gcp_hot(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["aws"]["transfer"])

def calculate_transfer_cost_from_l2_azure_to_gcp_hot(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["azure"]["transfer"])

def calculate_transfer_cost_from_gcp_hot_to_gcp_cool(data_size_in_gb, pricing):
    # Internal transfer usually free or low cost, but let's check if we have a price
    return 0

def calculate_transfer_cost_from_gcp_hot_to_aws_cool(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["gcp"]["transfer"])

def calculate_transfer_cost_from_gcp_hot_to_azure_cool(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["gcp"]["transfer"])

def calculate_transfer_cost_from_aws_hot_to_gcp_cool(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["aws"]["transfer"])

def calculate_transfer_cost_from_azure_hot_to_gcp_cool(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["azure"]["transfer"])

def calculate_transfer_cost_from_gcp_cool_to_gcp_archive(data_size_in_gb):
    return 0

def calculate_transfer_cost_from_gcp_cool_to_aws_archive(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["gcp"]["transfer"])

def calculate_transfer_cost_from_gcp_cool_to_azure_archive(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["gcp"]["transfer"])

def calculate_transfer_cost_from_aws_cool_to_gcp_archive(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["aws"]["transfer"])

def calculate_transfer_cost_from_azure_cool_to_gcp_archive(data_size_in_gb, pricing):
    return calculate_egress_cost(data_size_in_gb, pricing["azure"]["transfer"])
