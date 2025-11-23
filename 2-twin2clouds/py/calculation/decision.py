
import heapq

def build_graph_for_storage(
    aws_result_hot,
    azure_result_hot,
    gcp_result_hot,
    aws_result_l3_cool,
    azure_result_l3_cool,
    gcp_result_l3_cool,
    aws_result_l3_archive,
    azure_result_l3_archive,
    gcp_result_l3_archive,
    transfer_costs
):
    """
    Constructs a directed graph representing the possible storage paths and their costs.
    
    Nodes represent storage tiers on specific providers (e.g., "AWS_Hot", "Azure_Cool").
    Edges represent the transfer costs between these tiers.
    Node costs represent the monthly storage cost for that specific tier.
    
    Structure:
    - Hot Storage Nodes: Start points (AWS_Hot, Azure_Hot, GCP_Hot)
    - Cool Storage Nodes: Intermediate points
    - Archive Storage Nodes: End points
    """
    graph = {
        "AWS_Hot": {
            "costs": aws_result_hot["totalMonthlyCost"],
            "edges": {
                "AWS_Cool": transfer_costs["AWS_Hot_to_AWS_Cool"],
                "Azure_Cool": transfer_costs["AWS_Hot_to_Azure_Cool"],
                "GCP_Cool": transfer_costs["AWS_Hot_to_GCP_Cool"],
            },
        },
        "Azure_Hot": {
            "costs": azure_result_hot["totalMonthlyCost"],
            "edges": {
                "AWS_Cool": transfer_costs["Azure_Hot_to_AWS_Cool"],
                "Azure_Cool": transfer_costs["Azure_Hot_to_Azure_Cool"],
                "GCP_Cool": transfer_costs["Azure_Hot_to_GCP_Cool"],
            },
        },
        "GCP_Hot": {
            "costs": gcp_result_hot["totalMonthlyCost"],
            "edges": {
                "AWS_Cool": transfer_costs["GCP_Hot_to_AWS_Cool"],
                "Azure_Cool": transfer_costs["GCP_Hot_to_Azure_Cool"],
                "GCP_Cool": transfer_costs["GCP_Hot_to_GCP_Cool"],
            },
        },
        "AWS_Cool": {
            "costs": aws_result_l3_cool["totalMonthlyCost"],
            "edges": {
                "AWS_Archive": transfer_costs["AWS_Cool_to_AWS_Archive"],
                "Azure_Archive": transfer_costs["AWS_Cool_to_Azure_Archive"],
                "GCP_Archive": transfer_costs["AWS_Cool_to_GCP_Archive"],
            },
        },
        "Azure_Cool": {
            "costs": azure_result_l3_cool["totalMonthlyCost"],
            "edges": {
                "AWS_Archive": transfer_costs["Azure_Cool_to_AWS_Archive"],
                "Azure_Archive": transfer_costs["Azure_Cool_to_Azure_Archive"],
                "GCP_Archive": transfer_costs["Azure_Cool_to_GCP_Archive"],
            },
        },
        "GCP_Cool": {
            "costs": gcp_result_l3_cool["totalMonthlyCost"],
            "edges": {
                "AWS_Archive": transfer_costs["GCP_Cool_to_AWS_Archive"],
                "Azure_Archive": transfer_costs["GCP_Cool_to_Azure_Archive"],
                "GCP_Archive": transfer_costs["GCP_Cool_to_GCP_Archive"],
            },
        },
        "AWS_Archive": {
            "costs": aws_result_l3_archive["totalMonthlyCost"],
            "edges": {},
        },
        "Azure_Archive": {
            "costs": azure_result_l3_archive["totalMonthlyCost"],
            "edges": {},
        },
        "GCP_Archive": {
            "costs": gcp_result_l3_archive["totalMonthlyCost"],
            "edges": {},
        },
    }
    return graph

def find_cheapest_storage_path(graph, start_nodes, end_nodes):
    """
    Finds the path with the minimum total cost from any start node to any end node using Dijkstra's algorithm.
    
    Total Cost = Sum of (Node Costs + Edge Costs) along the path.
    
    Args:
        graph: The graph structure returned by build_graph_for_storage.
        start_nodes: List of possible starting nodes (Hot Storage tiers).
        end_nodes: List of possible ending nodes (Archive Storage tiers).
        
    Returns:
        A dictionary containing:
        - "path": List of nodes in the cheapest path (e.g., ["AWS_Hot", "Azure_Cool", "GCP_Archive"])
        - "cost": The total monthly cost of this path.
    """
    costs = {node: float('inf') for node in graph}
    parents = {}
    pq = []

    # Initialize costs
    for start_node in start_nodes:
        if start_node in graph:
            costs[start_node] = graph[start_node]["costs"]
            heapq.heappush(pq, (costs[start_node], start_node))

    while pq:
        current_cost, current_node = heapq.heappop(pq)

        if current_cost > costs[current_node]:
            continue

        if current_node not in graph or "edges" not in graph[current_node]:
            continue

        for neighbor, edge_cost in graph[current_node]["edges"].items():
            if neighbor not in graph:
                continue
                
            new_cost = current_cost + edge_cost + graph[neighbor]["costs"]

            if new_cost < costs[neighbor]:
                costs[neighbor] = new_cost
                parents[neighbor] = current_node
                heapq.heappush(pq, (new_cost, neighbor))

    # Find the cheapest path to any archive node
    # Filter end_nodes that are actually in the graph
    valid_end_nodes = [node for node in end_nodes if node in graph]
    
    if not valid_end_nodes:
        return {"path": [], "cost": float('inf')}

    target = min(valid_end_nodes, key=lambda node: costs[node])

    if costs[target] == float('inf'):
         return {"path": [], "cost": float('inf')}

    # Reconstruct the path
    cheapest_path = []
    current_node = target
    while current_node:
        cheapest_path.insert(0, current_node)
        current_node = parents.get(current_node)

    return {
        "path": cheapest_path,
        "cost": costs[target]
    }
