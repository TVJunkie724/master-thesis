/**
 * API Client for Twin2Clouds REST API
 * Handles UI interactions and API communication
 */

"use strict";

/**
 * Read parameters from UI form
 * @returns {Object|null} Parameters object or null if validation fails
 */
async function readParamsFromUi() {
    const numberOfDevices = parseInt(document.getElementById("devices").value);
    const deviceSendingIntervalInMinutes = parseFloat(document.getElementById("interval").value);
    const averageSizeOfMessageInKb = parseFloat(document.getElementById("messageSize").value);
    const hotStorageDurationInMonths = parseInt(document.getElementById("hotStorageDurationInMonths").value);
    const coolStorageDurationInMonths = parseInt(document.getElementById("coolStorageDurationInMonths").value);
    const archiveStorageDurationInMonths = parseInt(document.getElementById("archiveStorageDurationInMonths").value);
    const needs3DModel = document.querySelector('input[name="needs3DModel"]:checked').value === "yes";

    let entityCount = 0;
    if (needs3DModel) {
        entityCount = parseInt(document.getElementById("entityCount").value);
    }

    const amountOfActiveEditors = parseInt(document.getElementById("monthlyEditors").value);
    const amountOfActiveViewers = parseInt(document.getElementById("monthlyViewers").value);
    const dashboardRefreshesPerHour = parseInt(document.getElementById("dashboardRefreshesPerHour").value);
    const dashboardActiveHoursPerDay = parseInt(document.getElementById("dashboardActiveHoursPerDay").value);

    // New Inputs
    const useEventChecking = document.getElementById("useEventChecking").checked;
    const eventsPerMessage = parseInt(document.getElementById("eventsPerMessage").value);
    const returnFeedbackToDevice = document.getElementById("returnFeedbackToDevice").checked;
    const triggerNotificationWorkflow = document.getElementById("triggerNotificationWorkflow").checked;
    const orchestrationActionsPerMessage = parseInt(document.getElementById("orchestrationActionsPerMessage").value);
    const integrateErrorHandling = document.getElementById("integrateErrorHandling").checked;
    const apiCallsPerDashboardRefresh = parseInt(document.getElementById("apiCallsPerDashboardRefresh").value);

    const currency = document.getElementById("currency").value;

    const params = {
        numberOfDevices,
        deviceSendingIntervalInMinutes,
        averageSizeOfMessageInKb,
        hotStorageDurationInMonths,
        coolStorageDurationInMonths,
        archiveStorageDurationInMonths,
        needs3DModel,
        entityCount,
        amountOfActiveEditors,
        amountOfActiveViewers,
        dashboardRefreshesPerHour,
        dashboardActiveHoursPerDay,
        useEventChecking,
        eventsPerMessage,
        returnFeedbackToDevice,
        triggerNotificationWorkflow,
        orchestrationActionsPerMessage,
        integrateErrorHandling,
        apiCallsPerDashboardRefresh,
        currency,
    };

    if (!(await validateInputs(params))) {
        console.log("Input validation failed.");
        return null;
    }

    return params;
}

/**
 * Validate input parameters
 * @param {Object} params Parameters to validate
 * @returns {boolean} true if valid, false otherwise
 */
async function validateInputs(params) {
    // Check for NaN values
    if (
        isNaN(params.numberOfDevices) ||
        isNaN(params.deviceSendingIntervalInMinutes) ||
        isNaN(params.averageSizeOfMessageInKb) ||
        params.numberOfDevices <= 0 ||
        params.deviceSendingIntervalInMinutes <= 0 ||
        params.averageSizeOfMessageInKb <= 0
    ) {
        alert("Please provide valid positive numbers for Device, Interval, and Message Size.");
        return false;
    }

    // Validate new numeric inputs
    if (
        isNaN(params.eventsPerMessage) ||
        isNaN(params.orchestrationActionsPerMessage) ||
        isNaN(params.apiCallsPerDashboardRefresh) ||
        params.eventsPerMessage <= 0 ||
        params.orchestrationActionsPerMessage <= 0 ||
        params.apiCallsPerDashboardRefresh <= 0
    ) {
        alert("Please provide valid positive numbers for Events, Orchestration Actions, and API Calls.");
        return false;
    }

    // Validate storage durations
    if (
        params.hotStorageDurationInMonths > params.coolStorageDurationInMonths ||
        params.hotStorageDurationInMonths > params.archiveStorageDurationInMonths ||
        params.coolStorageDurationInMonths > params.archiveStorageDurationInMonths
    ) {
        alert("Storage durations must follow: Hot <= Cool <= Archive.");
        return false;
    }

    return true;
}

/**
 * Calculate costs from UI and update display
 * Main entry point called from the HTML button
 */
async function calculateCheapestCostsFromUI() {
    const params = await readParamsFromUi();
    if (!params) {
        return;
    }

    try {
        const response = await fetch('/api/calculate', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(params)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API Error: ${response.status} - ${errorText}`);
        }

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        const results = data.result;
        await updateHtml(
            results.awsCosts,
            results.azureCosts,
            results.gcpCosts || results.azureCosts, // Fallback if GCP not in response
            results.cheapestPath,
            params.currency,
            params, // Pass params for detailed service logic
            results.l2OptimizationOverride, // Pass override info
            results.l3OptimizationOverride, // Pass L3 override info
            results.l4OptimizationOverride, // Pass L4 override info
            results.l2CoolOptimizationOverride // Pass L2 Cool override info
        );

    } catch (error) {
        console.error("Calculation failed:", error);
        document.getElementById("result").classList.remove("displayed");
        document.getElementById("result").innerHTML = `<p class="error-message">❌ Calculation failed: ${error.message}</p>`;
        document.getElementById("result").classList.add("error");
    }
}
/**
 * Update HTML with calculation results
 */
async function updateHtml(awsCosts, azureCosts, gcpCosts, cheapestPath, currency, params, l2Override, l3Override, l4Override, l2CoolOverride) {
    // Display L2 Optimization Warning if applicable
    const warningContainer = document.getElementById("optimization-warning");
    if (warningContainer) warningContainer.remove(); // Clear previous

    const resultContainer = document.getElementById("result");

    if (l2Override) {
        const warningDiv = document.createElement("div");
        warningDiv.id = "optimization-warning";
        warningDiv.className = "alert alert-warning shadow-sm mb-4";
        warningDiv.innerHTML = `
            <h5 class="alert-heading"><i class="bi bi-exclamation-triangle-fill me-2"></i>Optimization Note (Storage)</h5>
            <p class="mb-0">
                The system selected <strong>${l2Override.selectedProvider}</strong> for Layer 2 (Hot Storage) instead of the cheaper <strong>${l2Override.cheapestL2Provider}</strong>.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> Combining Layer 2 and Layer 3 on ${l2Override.selectedProvider} is cheaper overall. 
                Choosing ${l2Override.cheapestL2Provider} for storage would have required expensive <strong>Data Transfer</strong> and <strong>Ingestion</strong> costs to move data to the processing layer.
            </p>
        `;
        resultContainer.parentNode.insertBefore(warningDiv, resultContainer);
    } else if (l3Override) {
        const warningDiv = document.createElement("div");
        warningDiv.id = "optimization-warning";
        warningDiv.className = "alert alert-info shadow-sm mb-4";
        warningDiv.innerHTML = `
            <h5 class="alert-heading"><i class="bi bi-info-circle-fill me-2"></i>Optimization Note (Processing)</h5>
            <p class="mb-0">
                Layer 3 (Processing) is set to <strong>${l3Override.selectedProvider}</strong> to match the storage layer, even though <strong>${l3Override.cheapestL3Provider}</strong> is cheaper for processing alone.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> Keeping data and processing on the same cloud (${l3Override.selectedProvider}) avoids massive <strong>Data Transfer</strong> costs. 
                Moving data to ${l3Override.cheapestL3Provider} would cost more than the savings on processing.
            </p>
        `;
        resultContainer.parentNode.insertBefore(warningDiv, resultContainer);
    } else if (l4Override) {
        const warningDiv = document.createElement("div");
        warningDiv.id = "optimization-warning";
        warningDiv.className = "alert alert-info shadow-sm mb-4";
        warningDiv.innerHTML = `
            <h5 class="alert-heading"><i class="bi bi-info-circle-fill me-2"></i>Optimization Note (Twin Management)</h5>
            <p class="mb-0">
                Layer 4 (Twin Management) is set to <strong>${l4Override.selectedProvider}</strong> to minimize integration costs, even though <strong>${l4Override.cheapestL4Provider}</strong> is cheaper in isolation.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> Using ${l4Override.selectedProvider} avoids cross-cloud glue code (API Gateways, Reader Functions) required to connect with Layer 3 (${l4Override.selectedProvider}).
            </p>
        `;
        resultContainer.parentNode.insertBefore(warningDiv, resultContainer);
    } else if (l2CoolOverride) {
        const warningDiv = document.createElement("div");
        warningDiv.id = "optimization-warning";
        warningDiv.className = "alert alert-info shadow-sm mb-4";
        warningDiv.innerHTML = `
            <h5 class="alert-heading"><i class="bi bi-info-circle-fill me-2"></i>Optimization Note (Cool Storage)</h5>
            <p class="mb-0">
                Layer 2 (Cool Storage) uses <strong>${l2CoolOverride.selectedProvider}</strong> to reduce transfer costs from Hot Storage, even though <strong>${l2CoolOverride.cheapestProvider}</strong> is cheaper for storage alone.
            </p>
        `;
        resultContainer.parentNode.insertBefore(warningDiv, resultContainer);
    }
    // Build comparison object per layer
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
    const selectedProviders = {
        l1: cheapestPath.find(p => p.startsWith('L1_'))?.split('_')[1].toLowerCase() || 'aws',
        l2_hot: cheapestPath.find(p => p.startsWith('L2_') && p.includes('Hot'))?.split('_')[1].toLowerCase() || 'aws',
        l2_cool: cheapestPath.find(p => p.startsWith('L2_') && p.includes('Cool'))?.split('_')[1].toLowerCase() || 'aws',
        l2_archive: cheapestPath.find(p => p.startsWith('L2_') && p.includes('Archive'))?.split('_')[1].toLowerCase() || 'aws',
        l3: cheapestPath.find(p => p.startsWith('L3_'))?.split('_')[1].toLowerCase() || 'aws',
        l4: cheapestPath.find(p => p.startsWith('L4_'))?.split('_')[1].toLowerCase() || 'none',
        l5: cheapestPath.find(p => p.startsWith('L5_'))?.split('_')[1].toLowerCase() || 'aws',
    };

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
        if (candidateProvider === 'aws') services.push(svc('Amazon S3 (IA)', 'https://aws.amazon.com/s3/'));
        if (candidateProvider === 'azure') services.push(svc('Azure Blob Storage (Cool)', 'https://azure.microsoft.com/en-us/products/storage/blobs/'));
        if (candidateProvider === 'gcp') services.push(svc('Google Cloud Storage (Nearline)', 'https://cloud.google.com/storage'));
    } else if (layerKey === 'l2_archive') {
        if (candidateProvider === 'aws') services.push(svc('Amazon S3 Glacier Deep Archive', 'https://aws.amazon.com/s3/storage-classes/glacier/'));
        if (candidateProvider === 'azure') services.push(svc('Azure Blob Storage (Archive)', 'https://azure.microsoft.com/en-us/products/storage/blobs/'));
        if (candidateProvider === 'gcp') services.push(svc('Google Cloud Storage (Archive)', 'https://cloud.google.com/storage'));
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
        if (candidateProvider === 'aws') services.push(svc('AWS IoT TwinMaker', 'https://aws.amazon.com/iot-twinmaker/'));
        if (candidateProvider === 'azure') services.push(svc('Azure Digital Twins', 'https://azure.microsoft.com/en-us/products/digital-twins/'));
        if (candidateProvider === 'gcp') services.push(svc('Self-Hosted Twin (Firestore)', 'https://cloud.google.com/firestore'), svc('Self-Hosted Twin (Functions)', 'https://cloud.google.com/functions'));
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
    const formatCost = (cost) => cost ? cost.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "N/A";
    const currencySymbol = currency === "EUR" ? "€" : "$";

    // Determine selected provider from the optimal path
    let cheapestProvider = selectedProviders[layerKey] || 'none';

    // Fallback to finding the cheapest in isolation if not found in selectedProviders (safety check)
    if (cheapestProvider === 'none') {
        let minCost = Infinity;
        if (layer.aws !== undefined && layer.aws < minCost) { minCost = layer.aws; cheapestProvider = 'aws'; }
        if (layer.azure !== undefined && layer.azure < minCost) { minCost = layer.azure; cheapestProvider = 'azure'; }
        if (layer.gcp !== undefined && layer.gcp < minCost) { minCost = layer.gcp; cheapestProvider = 'gcp'; }
    }

    const borderClass = `border-${cheapestProvider}`;

    // Get services for the cheapest provider (for front badge)
    const cheapestServices = getServicesForLayer(layerKey, cheapestProvider, params, selectedProviders);
    const hasGlueCode = cheapestServices.some(s => s.name.includes('Glue Code'));

    // Generate comparison list for back of card
    const generateServiceList = (provider) => {
        const services = getServicesForLayer(layerKey, provider, params, selectedProviders);
        if (services.length === 0) return '<span class="text-muted">N/A</span>';

        const isSelected = provider === cheapestProvider;
        const listClass = isSelected ? 'fw-bold' : '';
        const checkIcon = isSelected ? '<i class="bi bi-check-circle-fill text-success me-1"></i>' : '';

        return `<ul class="list-unstyled mb-1 small text-start ps-3 border-start border-2 border-${provider} ${listClass}">
                  ${services.map(s => `<li>${checkIcon}<a href="${s.url}" target="_blank" class="text-decoration-none text-reset hover-underline">${s.name}</a></li>`).join('')}
                </ul>`;
    };

    return `
    <div class="col">
      <div class="cost-card-container" onclick="flipCard(this)">
        <div class="cost-card shadow-sm h-100">
          <div class="card-front p-4 bg-white rounded border ${borderClass} d-flex flex-column justify-content-center align-items-center text-center h-100">
            <i class="bi bi-arrow-repeat flip-indicator" title="Click to flip details"></i>
            <h4 class="text-primary mb-2">${title}</h4>
            <small class="text-muted mb-3">Monthly Cost</small>
            ${hasGlueCode ? '<span class="badge bg-info text-dark mb-2"><i class="bi bi-puzzle me-1"></i>Includes Glue Code</span>' : ''}
            <div class="w-100">
              <div class="d-flex justify-content-between border-bottom py-2">
                <strong>AWS:</strong> <span class="${cheapestProvider === 'aws' ? 'fw-bold text-dark badge-aws px-2 rounded' : 'text-muted'}">${currencySymbol}${formatCost(layer.aws)}</span>
              </div>
              <div class="d-flex justify-content-between border-bottom py-2">
                <strong>Azure:</strong> <span class="${cheapestProvider === 'azure' ? 'fw-bold text-white badge-azure px-2 rounded' : 'text-muted'}">${currencySymbol}${formatCost(layer.azure)}</span>
              </div>
              ${layer.gcp !== undefined ? `
              <div class="d-flex justify-content-between py-2">
                <strong>GCP:</strong> <span class="${cheapestProvider === 'gcp' ? 'fw-bold text-white badge-gcp px-2 rounded' : 'text-muted'}">${currencySymbol}${formatCost(layer.gcp)}</span>
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
 * Generate HTML for results display
 */
function generateResultHTML(comparison, path, currency, params, selectedProviders) {
    // Helper to generate card with dynamic names
    const card = (layer, title, desc, layerKey) => {
        // URLs for main services
        const awsUrl = layerKey === 'l1' ? "https://aws.amazon.com/iot-core/" :
            layerKey === 'l2_hot' ? "https://aws.amazon.com/dynamodb/" :
                layerKey === 'l2_cool' ? "https://aws.amazon.com/s3/" :
                    layerKey === 'l2_archive' ? "https://aws.amazon.com/s3/storage-classes/glacier/" :
                        layerKey === 'l3' ? "https://aws.amazon.com/lambda/" :
                            layerKey === 'l4' ? "https://aws.amazon.com/iot-twinmaker/" :
                                "https://aws.amazon.com/grafana/";

        const azureUrl = layerKey === 'l1' ? "https://azure.microsoft.com/products/iot-hub" :
            layerKey === 'l2_hot' ? "https://azure.microsoft.com/products/cosmos-db" :
                layerKey === 'l2_cool' ? "https://azure.microsoft.com/products/storage/blobs" :
                    layerKey === 'l2_archive' ? "https://azure.microsoft.com/products/storage/blobs" :
                        layerKey === 'l3' ? "https://azure.microsoft.com/products/functions" :
                            layerKey === 'l4' ? "https://azure.microsoft.com/products/digital-twins" :
                                "https://azure.microsoft.com/products/managed-grafana";

        const gcpUrl = layerKey === 'l1' ? "https://cloud.google.com/pubsub" :
            layerKey === 'l2_hot' ? "https://cloud.google.com/firestore" :
                layerKey === 'l2_cool' ? "https://cloud.google.com/storage" :
                    layerKey === 'l2_archive' ? "https://cloud.google.com/storage" :
                        layerKey === 'l3' ? "https://cloud.google.com/functions" :
                            layerKey === 'l4' ? "https://cloud.google.com/firestore" : // Fallback for self-hosted
                                "https://grafana.com"; // Fallback for self-hosted

        return generateLayerCard(layer, title, awsUrl, "", azureUrl, "", gcpUrl, "", desc, currency, layerKey, params, selectedProviders);
    };

    return `
    <h2 class="text-center mb-4 text-primary">Your most cost-efficient Digital Twin solution</h2>
    
    <div id="optimal-path" class="mb-5 text-center">
      <div class="d-inline-block p-3 bg-white rounded shadow-sm border">
        ${path} 
      </div>
    </div>
    
    <div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4">
      ${card(comparison.layer1, "Layer 1: Data Acquisition", "", 'l1')}
      ${card(comparison.layer2a, "Layer 2: Hot Storage", "data storage for frequently accessed data", 'l2_hot')}
      ${card(comparison.layer2b, "Layer 2: Cool Storage", "data storage for infrequently accessed data", 'l2_cool')}
      ${card(comparison.layer2c, "Layer 2: Archive Storage", "data storage for archived data", 'l2_archive')}
      ${card(comparison.layer3, "Layer 3: Data Processing", "", 'l3')}
      ${card(comparison.layer4, "Layer 4: Twin Management", "3D model of the Digital Twin", 'l4')}
      ${card(comparison.layer5, "Layer 5: Data Visualization", "", 'l5')}
    </div>
  `;
}

// Make function available globally for HTML onclick handlers
if (typeof window !== "undefined") {
    window.calculateCheapestCostsFromUI = calculateCheapestCostsFromUI;
}
