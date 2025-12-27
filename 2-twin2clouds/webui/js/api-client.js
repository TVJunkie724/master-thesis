/**
 * API Client for Twin2Clouds REST API
 * Handles UI interactions and API communication
 */

"use strict";

/**
 * Set UI to "dirty" state - inputs have changed since last calculation
 * Enables calculate button and dims results to indicate stale data
 */
function setDirtyState() {
    const btn = document.getElementById("calculateBtn");
    const results = document.getElementById("result");

    if (btn) {
        btn.disabled = false;
        btn.classList.remove("btn-secondary");
        btn.classList.add("btn-primary");
    }
    if (results && results.innerHTML.trim() !== "") {
        results.style.opacity = "0.5";
    }
}

/**
 * Set UI to "fresh" state - calculation just completed
 * Disables calculate button and shows results at full opacity
 */
function setFreshState() {
    const btn = document.getElementById("calculateBtn");
    const results = document.getElementById("result");

    if (btn) {
        btn.disabled = true;
        btn.classList.remove("btn-primary");
        btn.classList.add("btn-secondary");
    }
    if (results) {
        results.style.opacity = "1";
    }
}

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
    let average3DModelSizeInMB = 100;
    if (needs3DModel) {
        entityCount = parseInt(document.getElementById("entityCount").value);
        average3DModelSizeInMB = parseFloat(document.getElementById("average3DModelSizeInMB").value);
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

    const integrateErrorHandling = (document.getElementById("integrateErrorHandling") || {}).checked;
    const apiCallsPerDashboardRefresh = parseInt(document.getElementById("apiCallsPerDashboardRefresh").value);

    // New enhanced calculation inputs
    const numberOfDeviceTypes = parseInt(document.getElementById("numberOfDeviceTypes").value) || 1;
    const numberOfEventActions = parseInt(document.getElementById("numberOfEventActions").value) || 0;
    const eventTriggerRate = 0.1; // Default, could add UI field if needed

    // GCP Self-Hosted Options (L4/L5) - ALWAYS FALSE (not implemented)
    // These features are disabled until GCP self-hosted L4/L5 is implemented
    const allowGcpSelfHostedL4 = false;
    const allowGcpSelfHostedL5 = false;

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
        average3DModelSizeInMB,
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
        numberOfDeviceTypes,
        numberOfEventActions,
        eventTriggerRate,
        allowGcpSelfHostedL4,
        allowGcpSelfHostedL5,
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

    if (params.needs3DModel) {
        if (isNaN(params.entityCount) || params.entityCount <= 0 || isNaN(params.average3DModelSizeInMB) || params.average3DModelSizeInMB <= 0) {
            alert("Please provide valid positive numbers for Entity Count and Average Model Size.");
            return false;
        }
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
        const response = await fetch('/calculate', {
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
            results.gcpCosts,
            results.cheapestPath,
            params.currency,
            params, // Pass params for detailed service logic
            results.l2OptimizationOverride, // Pass override info
            results.l3OptimizationOverride, // Pass L3 override info
            results.l2CoolOptimizationOverride, // Pass L2 Cool override info
            results.l2_l3_combinations, // Pass comparison table data
            results.l2ArchiveOptimizationOverride, // Pass L2 Archive override info
            results.l2_cool_combinations, // Pass Cool combinations
            results.l2_archive_combinations, // Pass Archive combinations
            results.l1OptimizationOverride, // Pass L1 override info
            results.l4OptimizationOverride, // Pass L4 override info
            results.transferCosts // Pass transfer costs for cross-cloud display
        );

        // Mark UI as fresh (results are current)
        setFreshState();

        console.log("params", params);
        console.log("results", results);

    } catch (error) {
        console.error("Calculation failed:", error);
        document.getElementById("result").classList.remove("displayed");
        document.getElementById("result").innerHTML = `<p class="error-message">❌ Calculation failed: ${error.message}</p>`;
        document.getElementById("result").classList.add("error");
    }
}
