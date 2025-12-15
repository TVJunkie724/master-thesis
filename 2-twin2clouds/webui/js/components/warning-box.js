/**
 * Warning Box Component
 * ======================
 * Generates optimization warning/info alert boxes.
 * 
 * These warnings explain to the user WHY the optimizer selected
 * a particular provider over a cheaper alternative (e.g., to avoid
 * glue code costs, transfer fees, etc.).
 */

"use strict";

/**
 * Insert a warning box into the result container
 * @param {string} type - Alert type ('warning', 'info', 'danger')
 * @param {string} html - HTML content for the warning
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
 * Clear all existing warning boxes
 */
function clearWarnings() {
    const existingWarnings = document.querySelectorAll(".optimization-warning");
    existingWarnings.forEach(el => el.remove());
}

/**
 * Generate L1 optimization warning
 * Shows when L1 provider differs from cheapest due to glue code costs
 * @param {object} override - Override info { selectedProvider, cheapestProvider, candidates }
 * @returns {object|null} Warning config or null
 */
function generateL1Warning(override) {
    if (!override) return null;

    return {
        type: 'warning',
        html: `
            <h5 class="alert-heading"><i class="bi bi-exclamation-triangle-fill me-2"></i>Optimization Note (Layer 1 Data Acquisition)</h5>
            <p class="mb-0">
                Layer 1 uses <strong>${override.selectedProvider}</strong>. Although <strong>${override.cheapestProvider}</strong> offers lower base rates, this choice minimizes <strong>Integration Costs</strong>.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> Using ${override.selectedProvider} avoids expensive "Glue Code" (Connector/Ingestion Functions) and Data Transfer fees required to send data to the selected Layer 2 provider.
            </p>
            ${generateDetailedComparisonTable(override.candidates, override.selectedProvider)}
        `,
    };
}

/**
 * Generate L2 Processing optimization warning
 * Shows when L2 provider optimizes for combined L2+L3 cost
 * @param {object} override - Override info
 * @returns {object|null} Warning config or null
 */
function generateL2ProcessingWarning(override) {
    if (!override) return null;

    return {
        type: 'info',
        html: `
            <h5 class="alert-heading"><i class="bi bi-info-circle-fill me-2"></i>Optimization Note (Layer 2 Processing)</h5>
            <p class="mb-0">
                Layer 2 (Processing) is set to <strong>${override.selectedProvider}</strong> to minimize total costs, even though <strong>${override.cheapestL3Provider}</strong> is cheaper for processing alone.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> The combined cost of Storage and Processing is lower with this selection. 
                Sticking to the cheapest processing provider would have incurred higher data transfer costs from the storage layer.
            </p>
        `,
    };
}

/**
 * Generate L3 Hot Storage optimization warning
 * @param {object} override - Override info
 * @param {Array} combinations - L2/L3 combination data
 * @returns {object|null} Warning config or null
 */
function generateL3HotWarning(override, combinations) {
    if (!override) return null;

    return {
        type: 'warning',
        html: `
            <h5 class="alert-heading"><i class="bi bi-exclamation-triangle-fill me-2"></i>Optimization Note (Layer 3 Hot Storage)</h5>
            <p class="mb-0">
                The system selected <strong>${override.selectedProvider}</strong> for Layer 3 (Hot Storage) instead of the cheaper <strong>${override.cheapestL2Provider}</strong>.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> The combined cost of Storage and Processing (plus any Data Transfer) is lower with this selection. 
                Choosing ${override.cheapestL2Provider} for storage would have resulted in a higher total cost due to integration or transfer fees.
            </p>
            ${generateComparisonTable(combinations, 'l2_l3')}
        `,
    };
}

/**
 * Generate L3 Cool Storage optimization warning
 * @param {object} override - Override info
 * @param {Array} combinations - Cool path combinations
 * @returns {object|null} Warning config or null
 */
function generateL3CoolWarning(override, combinations) {
    if (!override) return null;

    return {
        type: 'warning',
        html: `
            <h5 class="alert-heading"><i class="bi bi-exclamation-triangle-fill me-2"></i>Optimization Note (Layer 3 Cool Storage)</h5>
            <p class="mb-0">
                Layer 3 (Cool Storage) uses <strong>${override.selectedProvider}</strong>. Although <strong>${override.cheapestProvider}</strong> offers lower storage rates, this choice results in the lowest <strong>Total Path Cost</strong> (Hot &rarr; Cool &rarr; Archive).
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> The decision considers the entire lifecycle. Higher costs at this stage are often offset by significantly cheaper <strong>Archive Storage</strong> or avoided <strong>Transfer Fees</strong> downstream.
            </p>
            ${generateComparisonTable(combinations, 'cool')}
        `,
    };
}

/**
 * Generate L3 Archive Storage optimization warning
 * @param {object} override - Override info
 * @param {Array} combinations - Archive path combinations
 * @returns {object|null} Warning config or null
 */
function generateL3ArchiveWarning(override, combinations) {
    if (!override) return null;

    return {
        type: 'warning',
        html: `
            <h5 class="alert-heading"><i class="bi bi-exclamation-triangle-fill me-2"></i>Optimization Note (Layer 3 Archive Storage)</h5>
            <p class="mb-0">
                Layer 3 (Archive Storage) uses <strong>${override.selectedProvider}</strong>. Although <strong>${override.cheapestProvider}</strong> offers lower storage rates, this choice minimizes the <strong>Total Path Cost</strong>.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> The decision includes transfer costs from the previous Cool Storage layer. A slightly more expensive Archive provider might be chosen if it avoids high egress fees from the Cool layer.
            </p>
            ${generateComparisonTable(combinations, 'archive')}
        `,
    };
}

/**
 * Generate L4 optimization warning
 * Shows when L4 provider differs from cheapest due to glue code costs
 * @param {object} override - Override info
 * @returns {object|null} Warning config or null
 */
function generateL4Warning(override) {
    if (!override) return null;

    return {
        type: 'warning',
        html: `
            <h5 class="alert-heading"><i class="bi bi-exclamation-triangle-fill me-2"></i>Optimization Note (Layer 4 Twin Management)</h5>
            <p class="mb-0">
                Layer 4 uses <strong>${override.selectedProvider}</strong>. Although <strong>${override.cheapestProvider}</strong> offers lower base rates, this choice minimizes <strong>Integration Costs</strong>.
            </p>
            <hr>
            <p class="mb-0 small">
                <strong>Why?</strong> Using ${override.selectedProvider} avoids expensive "Glue Code" (API Gateway + Reader Functions) required to fetch data from Layer 3.
            </p>
            ${generateDetailedComparisonTable(override.candidates, override.selectedProvider)}
        `,
    };
}

/**
 * Display all applicable warnings
 * @param {object} overrides - Object with override info for each layer
 * @param {object} combinations - Object with combination data for tables
 */
function displayWarnings(overrides, combinations) {
    clearWarnings();

    const warnings = [
        generateL1Warning(overrides.l1),
        generateL3HotWarning(overrides.l2, combinations.l2_l3),
        generateL2ProcessingWarning(overrides.l3),
        generateL3CoolWarning(overrides.l2Cool, combinations.cool),
        generateL3ArchiveWarning(overrides.l2Archive, combinations.archive),
        generateL4Warning(overrides.l4),
    ];

    warnings.filter(w => w !== null).forEach(warning => {
        insertWarning(warning.type, warning.html);
    });
}
