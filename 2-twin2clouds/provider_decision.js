"use strict";

class PriorityQueue {
  constructor() {
    this.queue = [];
  }

  enqueue(node, cost) {
    this.queue.push({ node, cost });
    this.queue.sort((a, b) => a.cost - b.cost);
  }

  dequeue() {
    return this.queue.shift();
  }

  isEmpty() {
    return this.queue.length === 0;
  }
}

function buildGraphForStorage(
  awsHot,
  azureHot,
  awsCool,
  azureCool,
  awsArchive,
  azureArchive,
  transferCosts
) {
  let graph = {
    AWS_Hot: {
      costs: awsHot.totalMonthlyCost,
      edges: {
        AWS_Cool: transferCosts.AWS_Hot_to_AWS_Cool,
        Azure_Cool: transferCosts.AWS_Hot_to_Azure_Cool,
      },
    },
    Azure_Hot: {
      costs: azureHot.totalMonthlyCost,
      edges: {
        AWS_Cool: transferCosts.Azure_Hot_to_AWS_Cool,
        Azure_Cool: transferCosts.Azure_Hot_to_Azure_Cool,
      },
    },
    AWS_Cool: {
      costs: awsCool.totalMonthlyCost,
      edges: {
        AWS_Archive: transferCosts.AWS_Cool_to_AWS_Archive,
        Azure_Archive: transferCosts.AWS_Cool_to_Azure_Archive,
      },
    },
    Azure_Cool: {
      costs: azureCool.totalMonthlyCost,
      edges: {
        AWS_Archive: transferCosts.Azure_Cool_to_AWS_Archive,
        Azure_Archive: transferCosts.Azure_Cool_to_Azure_Archive,
      },
    },
    AWS_Archive: {
      costs: awsArchive.totalMonthlyCost,
      edges: {},
    },
    Azure_Archive: {
      costs: azureArchive.totalMonthlyCost,
      edges: {},
    },
  };
  return graph;
}

function findCheapestStoragePath(graph, startNodes, endNodes) {
  let costs = {};
  let parents = {};
  let pq = new PriorityQueue();

  // Initialize costs
  for (let node in graph) {
    costs[node] = Infinity;
  }

  // Start from both hot storage nodes
  for (let startNode of startNodes) {
    costs[startNode] = graph[startNode].costs;
    pq.enqueue(startNode, costs[startNode]);
  }

  while (!pq.isEmpty()) {
    let { node, cost } = pq.dequeue();

    if (cost > costs[node]) continue; // Ignore outdated paths

    if (!graph[node] || !graph[node].edges) continue; // Safety check

    for (let neighbor in graph[node].edges) {
      let edgeCost = graph[node].edges[neighbor] || 0;
      let newCost = cost + edgeCost + graph[neighbor].costs;

      if (newCost < costs[neighbor]) {
        costs[neighbor] = newCost;
        parents[neighbor] = node;
        pq.enqueue(neighbor, newCost);
      }
    }
  }

  // Find the cheapest path to any archive node
  let target = endNodes.reduce(
    (cheapest, node) => (costs[node] < costs[cheapest] ? node : cheapest),
    endNodes[0]
  );

  // Reconstruct the path
  let cheapestPath = [];
  let currentNode = target;
  while (currentNode) {
    cheapestPath.unshift(currentNode);
    currentNode = parents[currentNode];
  }

  return {
    path: cheapestPath,
    cost: costs[target],
  };
}
