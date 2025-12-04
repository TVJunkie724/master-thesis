"use strict";

/**
 * Helper to generate comparison table
 */
function generateComparisonTable(combinations, type = "l2_l3", selectedProviders = null) {
    if (!combinations || combinations.length === 0) return '';

    let headers = '';
    let rows = '';

    if (type === "l2_l3") {
        headers = `
            <tr>
                <th><small>Combination</small></th>
                <th class="text-end"><small>L2 Hot Cost</small></th>
                <th class="text-end"><small>L3 Processing Cost</small></th>
                <th class="text-end"><small>Transfer/Glue</small></th>
                <th class="text-end"><small>Total</small></th>
            </tr>
        `;
        rows = combinations.slice(0, 3).map(c => {
            let isSelected = false;
            if (selectedProviders) {
                isSelected = c.l2_provider.toLowerCase() === selectedProviders.l2_hot && c.l3_provider.toLowerCase() === selectedProviders.l3;
            }
            const rowClass = isSelected ? 'table-success' : '';
            return `
            <tr class="${rowClass}">
                <td><small>${c.l2_provider} + ${c.l3_provider}</small></td>
                <td class="text-end"><small>$${(c.l2_cost || 0).toFixed(2)}</small></td>
                <td class="text-end"><small>$${(c.l3_cost || 0).toFixed(2)}</small></td>
                <td class="text-end"><small>$${((c.transfer_cost || 0) + (c.glue_cost || 0)).toFixed(2)}</small></td>
                <td class="text-end fw-bold"><small>$${(c.total_cost || 0).toFixed(2)}</small></td>
            </tr>
        `}).join('');
    } else if (type === "cool") {
        headers = `
            <tr>
                <th><small>Path (Hot &rarr; Cool &rarr; Archive)</small></th>
                <th class="text-end"><small>Transfer (Hot&rarr;Cool)</small></th>
                <th class="text-end"><small>Cool Cost</small></th>
                <th class="text-end"><small>Transfer (Cool&rarr;Archive)</small></th>
                <th class="text-end"><small>Archive Cost</small></th>
                <th class="text-end"><small>Total</small></th>
            </tr>
        `;
        rows = combinations.slice(0, 3).map(c => {
            let isSelected = false;
            if (selectedProviders && c.path) {
                // Strict path matching by splitting segments
                // Format expected: "L2_Provider_Hot -> L2_Provider_Cool -> L2_Provider_Archive"
                const segments = c.path.split('->').map(s => s.trim().toLowerCase());

                if (type === "cool" && segments.length >= 3) {
                    const hot = selectedProviders.l2_hot;
                    const cool = selectedProviders.l2_cool;
                    const archive = selectedProviders.l2_archive;
                    // Check if each segment contains the corresponding provider name
                    isSelected = segments[0].includes(hot) && segments[1].includes(cool) && segments[2].includes(archive);
                } else if (type === "archive" && segments.length >= 2) {
                    // Archive path might be full or partial, but we care about the last two for Cool -> Archive transition
                    // checking the last segment for archive and second to last for cool
                    const cool = selectedProviders.l2_cool;
                    const archive = selectedProviders.l2_archive;
                    const len = segments.length;
                    isSelected = segments[len - 1].includes(archive) && segments[len - 2].includes(cool);
                }
            }
            const rowClass = isSelected ? 'table-success' : '';
            return `
            <tr class="${rowClass}">
                <td><small>${c.path}</small></td>
                <td class="text-end"><small>$${(c.trans_h_c || 0).toFixed(2)}</small></td>
                <td class="text-end"><small>$${(c.cool_cost || 0).toFixed(2)}</small></td>
                <td class="text-end"><small>$${(c.trans_c_a || 0).toFixed(2)}</small></td>
                <td class="text-end"><small>$${(c.archive_cost || 0).toFixed(2)}</small></td>
                <td class="text-end fw-bold"><small>$${(c.total_cost || 0).toFixed(2)}</small></td>
            </tr>
        `}).join('');
    } else if (type === "archive") {
        headers = `
            <tr>
                <th><small>Path (... &rarr; Cool &rarr; Archive)</small></th>
                <th class="text-end"><small>Transfer (Cool&rarr;Archive)</small></th>
                <th class="text-end"><small>Archive Cost</small></th>
                <th class="text-end"><small>Total</small></th>
            </tr>
        `;
        rows = combinations.slice(0, 3).map(c => {
            let isSelected = false;
            if (selectedProviders) {
                const p = c.path.toLowerCase();
                const cool = selectedProviders.l2_cool;
                const archive = selectedProviders.l2_archive;
                isSelected = p.includes(cool) && p.includes(archive);
            }
            const rowClass = isSelected ? 'table-success' : '';
            return `
            <tr class="${rowClass}">
                <td><small>${c.path}</small></td>
                <td class="text-end"><small>$${(c.trans_c_a || 0).toFixed(2)}</small></td>
                <td class="text-end"><small>$${(c.archive_cost || 0).toFixed(2)}</small></td>
                <td class="text-end fw-bold"><small>$${(c.total_cost || 0).toFixed(2)}</small></td>
            </tr>
        `}).join('');
    }

    return `
        <div class="table-responsive mt-3">
            <table class="table table-sm table-hover table-borderless mb-0 bg-white rounded">
                <thead class="table-light">
                    ${headers}
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        </div>
    `;
}

/**
 * Helper to generate detailed comparison table for L1/L4
 */
function generateDetailedComparisonTable(candidates, selectedProvider = null) {
    if (!candidates || candidates.length === 0) return '';

    const rows = candidates.sort((a, b) => a.total_cost - b.total_cost)
        .map(c => {
            const provider = c.provider || (c.key ? c.key.split('_')[1] : 'Unknown');
            const base = c.base_cost || 0;
            const glue = c.glue_cost || 0;
            const transfer = c.transfer_cost || 0;
            const total = c.total_cost || 0;

            const isSelected = selectedProvider && provider.toLowerCase() === selectedProvider.toLowerCase();
            const rowClass = isSelected ? 'table-success' : '';

            return `
            <tr class="${rowClass}">
                <td>${provider}</td>
                <td class="text-end">$${base.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                <td class="text-end text-muted"><small>+ $${glue.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</small></td>
                <td class="text-end text-muted"><small>+ $${transfer.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</small></td>
                <td class="text-end fw-bold">$${total.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
            </tr>
        `;
        }).join('');

    return `
        <div class="table-responsive mt-3">
            <table class="table table-sm table-hover table-borderless mb-0 bg-white rounded">
                <thead class="table-light">
                    <tr>
                        <th>Provider</th>
                        <th class="text-end">Base Cost</th>
                        <th class="text-end">Glue Code</th>
                        <th class="text-end">Data Transfer</th>
                        <th class="text-end">Total Cost</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        </div>
    `;
}

/**
 * Helper to create and insert warning
 */
function insertWarning(type, html) {
    const resultContainer = document.getElementById("result");
    if (!resultContainer) return;

    const div = document.createElement("div");
    div.className = `optimization-warning alert alert-${type} shadow-sm mb-5`;
    div.innerHTML = html;
    resultContainer.parentNode.insertBefore(div, resultContainer);
}

/**
 * Helper to get detailed service list for a layer/provider
 * @param {string} layerKey - The layer identifier (l1, l2_hot, etc.)
 * @param {string} candidateProvider - The provider we are listing services for (aws, azure, gcp)
 * @param {Object} params - User parameters
 * @param {Object} selectedProviders - The set of providers selected in the optimal path
 * @returns {Array<{name: string, url: string}>} List of service objects
 */
function getServicesForLayer(layerKey, candidateProvider, params, selectedProviders) {
    const services = [];

    // Determine if glue code would be needed IF this candidate provider were selected
    let isGlueNeededL1L2 = false;
    let isGlueNeededL3L5 = false;

    if (layerKey === 'l1') {
        isGlueNeededL1L2 = candidateProvider !== selectedProviders.l2_hot;
    } else if (layerKey === 'l2_hot') {
        isGlueNeededL1L2 = candidateProvider !== selectedProviders.l1;
    } else if (layerKey === 'l3') {
        isGlueNeededL3L5 = candidateProvider !== selectedProviders.l5;
    } else if (layerKey === 'l4') {
        isGlueNeededL3L5 = candidateProvider !== selectedProviders.l3; // Reusing variable name for simplicity or creating new one
    }

    // Helper to create service object
    const svc = (name, url) => ({ name, url });

    if (layerKey === 'l1') {
        if (candidateProvider === 'aws') services.push(svc('AWS IoT Core', 'https://aws.amazon.com/iot-core/'));
        if (candidateProvider === 'azure') services.push(svc('Azure IoT Hub', 'https://azure.microsoft.com/en-us/products/iot-hub/'));
        if (candidateProvider === 'gcp') services.push(svc('Google Cloud Pub/Sub', 'https://cloud.google.com/pubsub'));

        if (isGlueNeededL1L2) {
            services.push(svc('Connector Function (Glue Code)', 'https://aws.amazon.com/lambda/'));
        }
    } else if (layerKey === 'l2_hot') {
        if (candidateProvider === 'aws') services.push(svc('Amazon DynamoDB', 'https://aws.amazon.com/dynamodb/'));
        if (candidateProvider === 'azure') services.push(svc('Azure Cosmos DB', 'https://azure.microsoft.com/en-us/products/cosmos-db/'));
        if (candidateProvider === 'gcp') services.push(svc('Google Cloud Firestore', 'https://cloud.google.com/firestore'));

        if (isGlueNeededL1L2) {
            services.push(svc('Ingestion Function (Glue Code)', 'https://azure.microsoft.com/en-us/products/functions/'));
        }
    } else if (layerKey === 'l2_cool') {
        if (candidateProvider === 'aws') services.push(svc('Amazon S3 (IA)', 'https://aws.amazon.com/s3/'), svc('Hot to Cold Mover Function', 'https://aws.amazon.com/lambda/'));
        if (candidateProvider === 'azure') services.push(svc('Azure Blob Storage (Cool)', 'https://azure.microsoft.com/en-us/products/storage/blobs/'), svc('Hot to Cold Mover Function', 'https://azure.microsoft.com/en-us/products/functions/'));
        if (candidateProvider === 'gcp') services.push(svc('Google Cloud Storage (Nearline)', 'https://cloud.google.com/storage'), svc('Hot to Cold Mover Function', 'https://cloud.google.com/functions'));
    } else if (layerKey === 'l2_archive') {
        if (candidateProvider === 'aws') services.push(svc('Amazon S3 Glacier Deep Archive', 'https://aws.amazon.com/s3/storage-classes/glacier/'), svc('Cold to Archive Mover Function', 'https://aws.amazon.com/lambda/'));
        if (candidateProvider === 'azure') services.push(svc('Azure Blob Storage (Archive)', 'https://azure.microsoft.com/en-us/products/storage/blobs/'), svc('Cold to Archive Mover Function', 'https://azure.microsoft.com/en-us/products/functions/'));
        if (candidateProvider === 'gcp') services.push(svc('Google Cloud Storage (Archive)', 'https://cloud.google.com/storage'), svc('Cold to Archive Mover Function', 'https://cloud.google.com/functions'));
    } else if (layerKey === 'l3') {
        if (candidateProvider === 'aws') {
            services.push(svc('AWS Lambda', 'https://aws.amazon.com/lambda/'));
            if (params.useEventChecking) services.push(svc('Amazon EventBridge', 'https://aws.amazon.com/eventbridge/'));
            if (params.triggerNotificationWorkflow) services.push(svc('AWS Step Functions', 'https://aws.amazon.com/step-functions/'));
            if (isGlueNeededL3L5) services.push(svc('Amazon API Gateway', 'https://aws.amazon.com/api-gateway/'), svc('Reader Function (Glue Code)', 'https://aws.amazon.com/lambda/'));
        }
        if (candidateProvider === 'azure') {
            services.push(svc('Azure Functions', 'https://azure.microsoft.com/en-us/products/functions/'));
            if (params.useEventChecking) services.push(svc('Azure Event Grid', 'https://azure.microsoft.com/en-us/products/event-grid/'));
            if (params.triggerNotificationWorkflow) services.push(svc('Azure Logic Apps', 'https://azure.microsoft.com/en-us/products/logic-apps/'));
            if (isGlueNeededL3L5) services.push(svc('Azure API Management', 'https://azure.microsoft.com/en-us/products/api-management/'), svc('Reader Function (Glue Code)', 'https://azure.microsoft.com/en-us/products/functions/'));
        }
        if (candidateProvider === 'gcp') {
            services.push(svc('Google Cloud Functions', 'https://cloud.google.com/functions'));
            if (params.useEventChecking) services.push(svc('Google Cloud Pub/Sub', 'https://cloud.google.com/pubsub'));
            if (params.triggerNotificationWorkflow) services.push(svc('Google Cloud Workflows', 'https://cloud.google.com/workflows'));
            if (isGlueNeededL3L5) services.push(svc('Google Cloud API Gateway', 'https://cloud.google.com/api-gateway'), svc('Reader Function (Glue Code)', 'https://cloud.google.com/functions'));
        }
    } else if (layerKey === 'l4') {
        if (candidateProvider === 'aws') {
            services.push(svc('AWS IoT TwinMaker', 'https://aws.amazon.com/iot-twinmaker/'));
            if (isGlueNeededL3L5) services.push(svc('Amazon API Gateway', 'https://aws.amazon.com/api-gateway/'), svc('Reader Function (Glue Code)', 'https://aws.amazon.com/lambda/'));
        }
        if (candidateProvider === 'azure') {
            services.push(svc('Azure Digital Twins', 'https://azure.microsoft.com/en-us/products/digital-twins/'));
            if (isGlueNeededL3L5) services.push(svc('Azure API Management', 'https://azure.microsoft.com/en-us/products/api-management/'), svc('Reader Function (Glue Code)', 'https://azure.microsoft.com/en-us/products/functions/'));
        }
        if (candidateProvider === 'gcp') {
            services.push(svc('Self-Hosted Twin (Firestore)', 'https://cloud.google.com/firestore'), svc('Self-Hosted Twin (Functions)', 'https://cloud.google.com/functions'));
            if (isGlueNeededL3L5) services.push(svc('Google Cloud API Gateway', 'https://cloud.google.com/api-gateway'), svc('Reader Function (Glue Code)', 'https://cloud.google.com/functions'));
        }
    } else if (layerKey === 'l5') {
        if (candidateProvider === 'aws') services.push(svc('Amazon Managed Grafana', 'https://aws.amazon.com/grafana/'));
        if (candidateProvider === 'azure') services.push(svc('Azure Managed Grafana', 'https://azure.microsoft.com/en-us/products/managed-grafana/'));
        if (candidateProvider === 'gcp') services.push(svc('Self-Hosted Grafana', 'https://grafana.com/'));
    }

    return services;
}

/**
 * Generate individual layer comparison card
 */
function generateLayerCard(layer, title, awsUrl, awsName, azureUrl, azureName, gcpUrl, gcpName, description = "", currency = "USD", layerKey = "", params = {}, selectedProviders = {}) {
    const formatCost = (cost) => (cost !== undefined && cost !== null) ? cost.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "N/A";
    const currencySymbol = currency === "EUR" ? "€" : "$";

    // Determine selected provider from the optimal path
    let selectedProviderKey = selectedProviders[layerKey] || 'none';

    // Find local cheapest (isolation)
    let localCheapestKey = 'none';
    let minCost = Infinity;
    if (layer.aws !== undefined && layer.aws < minCost) { minCost = layer.aws; localCheapestKey = 'aws'; }
    if (layer.azure !== undefined && layer.azure < minCost) { minCost = layer.azure; localCheapestKey = 'azure'; }
    if (layer.gcp !== undefined && layer.gcp < minCost) { minCost = layer.gcp; localCheapestKey = 'gcp'; }

    // Fallback if selectedProviderKey is 'none' (should not happen with correct logic, but safety first)
    if (selectedProviderKey === 'none') {
        selectedProviderKey = localCheapestKey;
    }

    const isOverride = selectedProviderKey !== 'none' && localCheapestKey !== 'none' && selectedProviderKey !== localCheapestKey;
    const borderClass = `border-${selectedProviderKey}`;

    // Get services for the selected provider (for front badge)
    const selectedServices = getServicesForLayer(layerKey, selectedProviderKey, params, selectedProviders);
    const hasGlueCode = selectedServices.some(s => s.name.includes('Glue Code'));

    // Generate comparison list for back of card
    const generateServiceList = (provider) => {
        const services = getServicesForLayer(layerKey, provider, params, selectedProviders);
        if (services.length === 0) return '<span class="text-muted">N/A</span>';

        const isSelected = provider === selectedProviderKey;
        const listClass = isSelected ? 'fw-bold' : '';
        const checkIcon = isSelected ? '<i class="bi bi-check-circle-fill text-success me-1"></i>' : '';

        return `<ul class="list-unstyled mb-1 small text-start ps-3 border-start border-2 border-${provider} ${listClass}">
            ${services.map(s => `<li>${checkIcon}<a href="${s.url}" target="_blank" class="text-decoration-none text-reset hover-underline">${s.name}</a></li>`).join('')}
        </ul>`;
    };

    // Helper to generate price badge
    const getPriceBadge = (provider, cost) => {
        const isSelected = provider === selectedProviderKey;
        const isCheapest = provider === localCheapestKey;

        let badgeClass = 'text-muted';
        let label = '';

        if (isSelected) {
            if (provider === 'aws') badgeClass = 'fw-bold text-dark badge-aws px-2 rounded';
            else if (provider === 'azure') badgeClass = 'fw-bold text-white badge-azure px-2 rounded';
            else if (provider === 'gcp') badgeClass = 'fw-bold text-white badge-gcp px-2 rounded';
            label = ' <i class="bi bi-check-circle-fill text-success ms-1" title="System Choice"></i>';
        } else if (isCheapest) {
            label = ' <small class="text-muted ms-1">(Cheapest)</small>';
        }

        return `<span class="${badgeClass}">${currencySymbol}${formatCost(cost)}</span>${label}`;
    };

    // Special handling for L4 when omitted - REVERTED
    // if (layerKey === 'l4' && layer.aws === 0 && layer.azure === 0 && layer.gcp === 0) { ... }

    return `
    <div class="col">
        <div class="cost-card-container" onclick="flipCard(this)">
            <div class="cost-card shadow-sm h-100">
                <div class="card-front p-4 bg-white rounded border ${borderClass} d-flex flex-column justify-content-center align-items-center text-center h-100">
                    <i class="bi bi-arrow-repeat flip-indicator" title="Click to flip details"></i>
                    ${isOverride ? '<i class="bi bi-exclamation-triangle-fill text-warning position-absolute top-0 start-0 m-3" title="Optimized for System Cost (not Layer Cost)"></i>' : ''}
                    <h4 class="text-primary mb-2">${title}</h4>
                    <small class="text-muted mb-3">Monthly Cost</small>
                    ${hasGlueCode ? '<span class="badge bg-info text-dark mb-2"><i class="bi bi-puzzle me-1"></i>Includes Glue Code</span>' : ''}
                    <div class="w-100">
                        <div class="d-flex justify-content-between border-bottom py-2">
                            <strong>AWS:</strong> <div>${getPriceBadge('aws', layer.aws)}</div>
                        </div>
                        <div class="d-flex justify-content-between border-bottom py-2">
                            <strong>Azure:</strong> <div>${getPriceBadge('azure', layer.azure)}</div>
                        </div>
                        ${layer.gcp !== undefined ? `
<div class="d-flex justify-content-between py-2">
<strong>GCP:</strong> <div>${getPriceBadge('gcp', layer.gcp)}</div>
</div>` : ''}
                    </div>
                </div>
                <div class="card-back p-4 bg-light rounded border ${borderClass} d-flex flex-column justify-content-center text-center h-100">
                    <i class="bi bi-arrow-repeat flip-indicator" title="Click to flip back"></i>
                    <h5 class="text-primary mb-2">${title}</h5>
                    <h6 class="text-muted mb-3 small">Service Stack Comparison</h6>

                    <div class="card-back-content text-start mb-3">
                        <div class="mb-2">
                            <strong class="text-aws">AWS:</strong>
                            ${generateServiceList('aws')}
                        </div>
                        <div class="mb-2">
                            <strong class="text-azure">Azure:</strong>
                            ${generateServiceList('azure')}
                        </div>
                        ${layer.gcp !== undefined ? `
<div class="mb-2">
<strong class="text-gcp">GCP:</strong>
${generateServiceList('gcp')}
</div>` : ''}
                    </div>
                </div>
            </div>
        </div>
    </div>
    `;
}

/**
 * Generate full result HTML
 */
function generateResultHTML(comparison, path, currency, params, selectedProviders) {
    const card = (layer, title, desc, layerKey) => {
        const awsUrl = layerKey === 'l1' ? "https://aws.amazon.com/iot-core/" :
            layerKey === 'l2_hot' ? "https://aws.amazon.com/dynamodb/" :
                layerKey === 'l2_cool' ? "https://aws.amazon.com/s3/" :
                    layerKey === 'l2_archive' ? "https://aws.amazon.com/s3/storage-classes/glacier/" :
                        layerKey === 'l3' ? "https://aws.amazon.com/lambda/" :
                            layerKey === 'l4' ? "https://aws.amazon.com/iot-twinmaker/" :
                                "https://aws.amazon.com/grafana/";

        const azureUrl = layerKey === 'l1' ? "https://azure.microsoft.com/en-us/products/iot-hub/" :
            layerKey === 'l2_hot' ? "https://azure.microsoft.com/en-us/products/cosmos-db/" :
                layerKey === 'l2_cool' ? "https://azure.microsoft.com/en-us/products/storage/blobs/" :
                    layerKey === 'l2_archive' ? "https://azure.microsoft.com/en-us/products/storage/blobs/" :
                        layerKey === 'l3' ? "https://azure.microsoft.com/en-us/products/functions/" :
                            layerKey === 'l4' ? "https://azure.microsoft.com/en-us/products/digital-twins/" :
                                "https://azure.microsoft.com/en-us/products/managed-grafana/";

        const gcpUrl = layerKey === 'l1' ? "https://cloud.google.com/pubsub" :
            layerKey === 'l2_hot' ? "https://cloud.google.com/firestore" :
                layerKey === 'l2_cool' ? "https://cloud.google.com/storage" :
                    layerKey === 'l2_archive' ? "https://cloud.google.com/storage" :
                        layerKey === 'l3' ? "https://cloud.google.com/functions" :
                            layerKey === 'l4' ? "https://cloud.google.com/firestore" :
                                "https://grafana.com/";

        return generateLayerCard(layer, title, awsUrl, "", azureUrl, "", gcpUrl, "", desc, currency, layerKey, params, selectedProviders);
    };

    return `
    <h2 class="text-center mb-4 text-primary">Your most cost-efficient Digital Twin solution</h2>
    <div class="text-center mb-5">
        <h5 class="text-muted">Optimal Path</h5>
        <div class="d-flex justify-content-center align-items-center flex-wrap gap-2">
            ${path}
        </div>
    </div>

    <div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4 mb-5">
        ${card(comparison.layer1, "Layer 1: Data Acquisition", "Ingestion & Messaging", "l1")}
        ${card(comparison.layer2a, "Layer 2: Hot Storage", "High-speed access", "l2_hot")}
        ${card(comparison.layer2b, "Layer 2: Cool Storage", "Infrequent access", "l2_cool")}
        ${card(comparison.layer2c, "Layer 2: Archive Storage", "Long-term retention", "l2_archive")}
        ${card(comparison.layer3, "Layer 3: Data Processing", "Compute & Transformation", "l3")}
        ${card(comparison.layer4, "Layer 4: Twin Management", "Digital Twin Graph", "l4")}
        ${card(comparison.layer5, "Layer 5: Visualization", "Dashboards & Analytics", "l5")}
    </div>
    `;
}

/**
 * Update HTML with calculation results
 */
async function updateHtml(awsCosts, azureCosts, gcpCosts, cheapestPath, currency, params, l2Override, l3Override, l2CoolOverride, l2_l3_combinations, l2ArchiveOverride, l2_cool_combinations, l2_archive_combinations, l1OptimizationOverride, l4OptimizationOverride) {
    // Display L2 Optimization Warning if applicable

    // Clear previous warnings
    const existingWarnings = document.querySelectorAll(".optimization-warning");
    existingWarnings.forEach(el => el.remove());

    const resultContainer = document.getElementById("result");

    // Parse cheapest path to identify selected providers
    // Path format: ['L1_AWS', 'L2_AWS_Hot', 'L2_AWS_Cool', 'L2_AWS_Archive', 'L3_AWS', 'L4_AWS', 'L5_AWS']
    const selectedProviders = {
        l1: cheapestPath.find(p => p.startsWith('L1_'))?.split('_')[1].toLowerCase() || 'aws',
        l2_hot: cheapestPath.find(p => p.startsWith('L2_') && p.includes('Hot'))?.split('_')[1].toLowerCase() || 'aws',
        l2_cool: cheapestPath.find(p => p.startsWith('L2_') && p.includes('Cool'))?.split('_')[1].toLowerCase() || 'aws',
        l2_archive: cheapestPath.find(p => p.startsWith('L2_') && p.includes('Archive'))?.split('_')[1].toLowerCase() || 'aws',
        l3: cheapestPath.find(p => p.startsWith('L3_'))?.split('_')[1].toLowerCase() || 'aws',
        l4: cheapestPath.find(p => p.startsWith('L4_'))?.split('_')[1].toLowerCase() || 'none',
        l5: cheapestPath.find(p => p.startsWith('L5_'))?.split('_')[1].toLowerCase() || 'aws',
    };

    // 6. L1 Override
    if (l1OptimizationOverride) {
        const o = l1OptimizationOverride;
        insertWarning("warning", `
            <h5 class="alert-heading"><i class="bi bi-exclamation-triangle-fill me-2"></i>Optimization Note (Layer 1 Data Acquisition)</h5>
            <p class="mb-0">
                Layer 1 uses <strong>${o.selectedProvider}</strong>. Although <strong>${o.cheapestProvider}</strong> offers lower base rates, this choice minimizes <strong>Integration Costs</strong>.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> Using ${o.selectedProvider} avoids expensive "Glue Code" (Connector/Ingestion Functions) and Data Transfer fees required to send data to the selected Layer 2 provider.
            </p>
            ${generateDetailedComparisonTable(o.candidates, o.selectedProvider)}
        `);
    }

    // 1. L2 Hot Override
    if (l2Override) {
        insertWarning("warning", `
            <h5 class="alert-heading"><i class="bi bi-exclamation-triangle-fill me-2"></i>Optimization Note (Layer 2 Hot Storage)</h5>
            <p class="mb-0">
                The system selected <strong>${l2Override.selectedProvider}</strong> for Layer 2 (Hot Storage) instead of the cheaper <strong>${l2Override.cheapestL2Provider}</strong>.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> The combined cost of Storage and Processing (plus any Data Transfer) is lower with this selection. 
                Choosing ${l2Override.cheapestL2Provider} for storage would have resulted in a higher total cost due to integration or transfer fees.
            </p>
            ${generateComparisonTable(l2_l3_combinations, "l2_l3", selectedProviders)}
        `);
    }

    // 2. L3 Override
    if (l3Override) {
        insertWarning("info", `
            <h5 class="alert-heading"><i class="bi bi-info-circle-fill me-2"></i>Optimization Note (Layer 3 Processing)</h5>
            <p class="mb-0">
                Layer 3 (Processing) is set to <strong>${l3Override.selectedProvider}</strong> to minimize total costs, even though <strong>${l3Override.cheapestL3Provider}</strong> is cheaper for processing alone.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> The combined cost of Storage and Processing is lower with this selection. 
                Sticking to the cheapest processing provider would have incurred higher data transfer costs from the storage layer.
            </p>
        `);
    }

    // 4. L2 Cool Override
    if (l2CoolOverride) {
        insertWarning("warning", `
            <h5 class="alert-heading"><i class="bi bi-exclamation-triangle-fill me-2"></i>Optimization Note (Layer 2 Cool Storage)</h5>
            <p class="mb-0">
                Layer 2 (Cool Storage) uses <strong>${l2CoolOverride.selectedProvider}</strong>. Although <strong>${l2CoolOverride.cheapestProvider}</strong> offers lower storage rates, this choice results in the lowest <strong>Total Path Cost</strong> (Hot &rarr; Cool &rarr; Archive).
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> The decision considers the entire lifecycle. Higher costs at this stage are often offset by significantly cheaper <strong>Archive Storage</strong> or avoided <strong>Transfer Fees</strong> downstream.
            </p>
            ${generateComparisonTable(l2_cool_combinations, "cool", selectedProviders)}
        `);
    }

    // 5. L2 Archive Override
    if (l2ArchiveOverride) {
        insertWarning("warning", `
            <h5 class="alert-heading"><i class="bi bi-exclamation-triangle-fill me-2"></i>Optimization Note (Layer 2 Archive Storage)</h5>
            <p class="mb-0">
                Layer 2 (Archive Storage) uses <strong>${l2ArchiveOverride.selectedProvider}</strong>. Although <strong>${l2ArchiveOverride.cheapestProvider}</strong> offers lower storage rates, this choice minimizes the <strong>Total Path Cost</strong>.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> The decision includes transfer costs from the previous Cool Storage layer. A slightly more expensive Archive provider might be chosen if it avoids high egress fees from the Cool layer.
            </p>
            ${generateComparisonTable(l2_archive_combinations, "archive", selectedProviders)}
        `);
    }

    // 7. L4 Override
    // l4OptimizationOverride passed from backend
    if (l4OptimizationOverride) {
        const o = l4OptimizationOverride;
        insertWarning("warning", `
            <h5 class="alert-heading"><i class="bi bi-exclamation-triangle-fill me-2"></i>Optimization Note (Layer 4 Twin Management)</h5>
            <p class="mb-0">
                Layer 4 uses <strong>${o.selectedProvider}</strong>. Although <strong>${o.cheapestProvider}</strong> offers lower base rates, this choice minimizes <strong>Integration Costs</strong>.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> Using ${o.selectedProvider} avoids expensive "Glue Code" (API Gateway + Reader Functions) required to fetch data from Layer 3.
            </p>
            ${generateDetailedComparisonTable(o.candidates, o.selectedProvider)}
        `);
    }

    const comparisonPerLayerObj = {
        layer1: {
            name: "Data Acquisition",
            aws: awsCosts.dataAquisition.totalMonthlyCost,
            azure: azureCosts.dataAquisition.totalMonthlyCost,
            gcp: gcpCosts.dataAquisition.totalMonthlyCost,
        },
        layer2a: {
            name: "Hot Storage",
            aws: awsCosts.resultHot.totalMonthlyCost,
            azure: azureCosts.resultHot.totalMonthlyCost,
            gcp: gcpCosts.resultHot.totalMonthlyCost,
        },
        layer2b: {
            name: "Cool Storage",
            aws: awsCosts.resultL3Cool.totalMonthlyCost,
            azure: azureCosts.resultL3Cool.totalMonthlyCost,
            gcp: gcpCosts.resultL3Cool.totalMonthlyCost,
        },
        layer2c: {
            name: "Archive Storage",
            aws: awsCosts.resultL3Archive.totalMonthlyCost,
            azure: azureCosts.resultL3Archive.totalMonthlyCost,
            gcp: gcpCosts.resultL3Archive.totalMonthlyCost,
        },
        layer3: {
            name: "Data Processing",
            aws: awsCosts.dataProcessing.totalMonthlyCost,
            azure: azureCosts.dataProcessing.totalMonthlyCost,
            gcp: gcpCosts.dataProcessing.totalMonthlyCost,
        },
        layer4: {
            name: "Twin Management",
            aws: awsCosts.resultL4 ? awsCosts.resultL4.totalMonthlyCost : 0,
            azure: azureCosts.resultL4 ? azureCosts.resultL4.totalMonthlyCost : 0,
            gcp: gcpCosts.resultL4 ? gcpCosts.resultL4.totalMonthlyCost : 0,
        },
        layer5: {
            name: "Data Visualization",
            aws: awsCosts.resultL5.totalMonthlyCost,
            azure: azureCosts.resultL5.totalMonthlyCost,
            gcp: gcpCosts.resultL5.totalMonthlyCost,
        },
    };

    // Parse cheapest path to identify selected providers
    // Path format: ['L1_AWS', 'L2_AWS_Hot', 'L2_AWS_Cool', 'L2_AWS_Archive', 'L3_AWS', 'L4_AWS', 'L5_AWS']
    // Note: The backend returns a list of strings.
    // (Moved to top of function)

    const formattedCheapestPath = cheapestPath
        .map((segment) => {
            let badgeClass = 'bg-secondary';
            if (segment.toLowerCase().includes('aws') || segment.toLowerCase().includes('amazon')) badgeClass = 'badge-aws';
            else if (segment.toLowerCase().includes('azure')) badgeClass = 'badge-azure';
            else if (segment.toLowerCase().includes('gcp') || segment.toLowerCase().includes('google')) badgeClass = 'badge-gcp';
            return `<span class="badge ${badgeClass} mx-1">${segment}</span>`;
        })
        .join('<i class="bi bi-arrow-right text-muted mx-2"></i>');

    const resultHTML = generateResultHTML(comparisonPerLayerObj, formattedCheapestPath, currency, params, selectedProviders);

    document.getElementById("result").classList.remove("error");
    document.getElementById("result").innerHTML = resultHTML;
}
