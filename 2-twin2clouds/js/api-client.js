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
 * Update HTML with calculation results
 * @param {Object} awsCosts AWS cost breakdown
 * @param {Object} azureCosts Azure cost breakdown
 * @param {Object} gcpCosts GCP cost breakdown
 * @param {Array} cheapestPath Array of cheapest provider per layer
 */
async function updateHtml(awsCosts, azureCosts, gcpCosts, cheapestPath, currency) {
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

    const formattedCheapestPath = cheapestPath
        .map((segment) => `<span class="path-segment">${segment}</span>`)
        .join('<span class="arrow">→</span>');

    const resultHTML = generateResultHTML(comparisonPerLayerObj, formattedCheapestPath, currency);

    document.getElementById("result").classList.remove("error");
    document.getElementById("result").innerHTML = resultHTML;
}

/**
 * Generate HTML for results display
 */
function generateResultHTML(comparison, path, currency) {
    return `
    <h2>Your most cost-efficient Digital Twin solution</h2>
    
    <div id="optimal-path">
      <div class="path-container">${path}</div>
    </div>
    
    <div class="cost-container">
      ${generateLayerCard(comparison.layer1, "Layer 1: Data Acquisition", "https://aws.amazon.com/iot-core/", "AWS IoT Core", "https://azure.microsoft.com/products/iot-hub", "Azure IoT Hub", "https://cloud.google.com/iot-core", "Google Cloud IoT Core", "", currency)}
      ${generateLayerCard(comparison.layer2a, "Layer 2: Hot Storage", "https://aws.amazon.com/dynamodb/", "AWS DynamoDB", "https://azure.microsoft.com/products/cosmos-db", "Azure CosmosDB", "https://cloud.google.com/firestore", "Google Cloud Firestore", "data storage for frequently accessed data", currency)}
      ${generateLayerCard(comparison.layer2b, "Layer 2: Cool Storage", "https://aws.amazon.com/s3/", "AWS S3-Infrequent Access", "https://azure.microsoft.com/products/storage/blobs", "Azure BlobStorage (Cool Tier)", "https://cloud.google.com/storage", "Google Cloud Storage (Nearline)", "data storage for infrequently accessed data", currency)}
      ${generateLayerCard(comparison.layer2c, "Layer 2: Archive Storage", "https://aws.amazon.com/s3/storage-classes/glacier/", "Amazon S3-Glacier Deep Archive", "https://azure.microsoft.com/products/storage/blobs", "Azure Blob Storage (Archive Tier)", "https://cloud.google.com/storage", "Google Cloud Storage (Archive)", "data storage for archived data", currency)}
      ${generateLayerCard(comparison.layer3, "Layer 3: Data Processing", "https://aws.amazon.com/lambda/", "AWS Lambda", "https://azure.microsoft.com/products/functions", "Azure Functions", "https://cloud.google.com/functions", "Google Cloud Functions", "", currency)}
      ${generateLayerCard(comparison.layer4, "Layer 4: Twin Management", "https://aws.amazon.com/iot-twinmaker/", "AWS IoT TwinMaker", "https://azure.microsoft.com/products/digital-twins", "Azure Digital Twins", null, null, "3D model of the Digital Twin", currency)}
      ${generateLayerCard(comparison.layer5, "Layer 5: Data Visualization", "https://aws.amazon.com/grafana/", "Amazon Managed Grafana", "https://azure.microsoft.com/products/managed-grafana", "Azure Managed Grafana", "https://grafana.com", "Grafana (self-hosted on GCP)", "", currency)}
    </div>
  `;
}

/**
 * Generate individual layer comparison card
 */
function generateLayerCard(layer, title, awsUrl, awsName, azureUrl, azureName, gcpUrl, gcpName, description = "", currency = "USD") {
    const formatCost = (cost) => cost ? cost.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "N/A";
    const currencySymbol = currency === "EUR" ? "€" : "$";

    return `
    <div class="cost-card" onclick="flipCard(this)">
      <div class="card-front">
        <h3>${title} <span class="info-icon">ℹ️</span></h3>
        <p><strong>AWS:</strong> <span class="total-cost">${currencySymbol}${formatCost(layer.aws)}</span></p>
        <p><strong>Azure:</strong> <span class="total-cost">${currencySymbol}${formatCost(layer.azure)}</span></p>
        ${layer.gcp !== undefined ? `<p><strong>GCP:</strong> <span class="total-cost">${currencySymbol}${formatCost(layer.gcp)}</span></p>` : ''}
      </div>
      <div class="card-back">
        <h3>${title} Info</h3>
        <p>This layer compares ${description ? description + ' in ' : ''}
          <a href="${awsUrl}" target="_blank"><strong>${awsName}</strong></a> vs. 
          <a href="${azureUrl}" target="_blank"><strong>${azureName}</strong></a>
          ${gcpUrl ? ` vs. <a href="${gcpUrl}" target="_blank"><strong>${gcpName}</strong></a>` : ''}
        </p>
      </div>
    </div>
  `;
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
            params.currency
        );

        console.log("API result", results);

    } catch (error) {
        console.error("Calculation failed:", error);
        document.getElementById("result").classList.remove("displayed");
        document.getElementById("result").innerHTML = `<p class="error-message">❌ Calculation failed: ${error.message}</p>`;
        document.getElementById("result").classList.add("error");
    }
}

// Make function available globally for HTML onclick handlers
if (typeof window !== "undefined") {
    window.calculateCheapestCostsFromUI = calculateCheapestCostsFromUI;
}
