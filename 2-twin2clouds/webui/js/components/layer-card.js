/**
 * Layer Card Component
 * =====================
 * Generates the flip-card HTML for individual layer cost comparison.
 * 
 * Each card displays:
 * - Front: Cost comparison for AWS/Azure/GCP with selection indicators
 * - Back: Service stack comparison showing which services are used
 */

"use strict";

/**
 * Generate a layer comparison card
 * @param {object} layerCosts - Cost data { aws: number, azure: number, gcp?: number }
 * @param {string} title - Card title (e.g., "Layer 1: Data Acquisition")
 * @param {string} layerKey - Layer ID (e.g., 'l1', 'l3_hot')
 * @param {object} params - User parameters
 * @param {object} selectedProviders - Map of layer to selected provider
 * @param {string} currency - Currency code
 * @returns {string} HTML string for the card
 */
function generateLayerCard(layerCosts, title, layerKey, params, selectedProviders, currency = 'USD') {
    const currencySymbol = getCurrencySymbol(currency);
    const selectedProvider = selectedProviders[layerKey] || 'aws';

    // Find local cheapest for this layer
    const localCheapest = findLocalCheapest(layerCosts);
    const isOverride = selectedProvider !== localCheapest && localCheapest !== 'none';

    // Get border class based on selected provider
    const styles = getProviderStyles(selectedProvider);
    const borderClass = styles.borderClass;

    // Generate service lists for card back
    const awsServices = getServicesForLayer(layerKey, 'aws', params, selectedProviders);
    const azureServices = getServicesForLayer(layerKey, 'azure', params, selectedProviders);
    const gcpServices = getServicesForLayer(layerKey, 'gcp', params, selectedProviders);

    // Check if glue code is included (for badge display)
    // Only check the SELECTED provider's services, not all providers
    const selectedServices = selectedProvider === 'aws' ? awsServices :
        selectedProvider === 'azure' ? azureServices :
            gcpServices;
    const hasGlueCode = selectedServices.some(s => s.isGlue);

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
                        ${generateCostRow('AWS', layerCosts.aws, currencySymbol, 'aws', selectedProvider, localCheapest)}
                        ${generateCostRow('Azure', layerCosts.azure, currencySymbol, 'azure', selectedProvider, localCheapest)}
                        ${layerCosts.gcp !== undefined ? generateCostRow('GCP', layerCosts.gcp, currencySymbol, 'gcp', selectedProvider, localCheapest, false) : ''}
                    </div>
                </div>
                <div class="card-back p-4 bg-light rounded border ${borderClass} d-flex flex-column justify-content-center text-center h-100">
                    <i class="bi bi-arrow-repeat flip-indicator" title="Click to flip back"></i>
                    <h5 class="text-primary mb-2">${title}</h5>
                    <h6 class="text-muted mb-3 small">Service Stack Comparison</h6>
                    <div class="card-back-content text-start mb-3">
                        ${generateServiceStack('AWS', 'aws', awsServices, selectedProvider)}
                        ${generateServiceStack('Azure', 'azure', azureServices, selectedProvider)}
                        ${layerCosts.gcp !== undefined ? generateServiceStack('GCP', 'gcp', gcpServices, selectedProvider) : ''}
                    </div>
                </div>
            </div>
        </div>
    </div>
    `;
}

/**
 * Find the cheapest provider for a layer
 * @param {object} costs - Cost object { aws, azure, gcp }
 * @returns {string} Provider ID of cheapest option
 */
function findLocalCheapest(costs) {
    let minCost = Infinity;
    let cheapest = 'none';

    if (costs.aws !== undefined && costs.aws < minCost) { minCost = costs.aws; cheapest = 'aws'; }
    if (costs.azure !== undefined && costs.azure < minCost) { minCost = costs.azure; cheapest = 'azure'; }
    if (costs.gcp !== undefined && costs.gcp < minCost) { minCost = costs.gcp; cheapest = 'gcp'; }

    return cheapest;
}

/**
 * Generate a cost row for the card front
 * @param {string} providerName - Display name
 * @param {number} cost - Cost value
 * @param {string} symbol - Currency symbol
 * @param {string} providerId - Provider ID
 * @param {string} selectedProvider - Currently selected provider
 * @param {string} localCheapest - Cheapest provider for this layer
 * @param {boolean} hasBorder - Whether to show bottom border
 * @returns {string} HTML for the row
 */
function generateCostRow(providerName, cost, symbol, providerId, selectedProvider, localCheapest, hasBorder = true) {
    const isSelected = providerId === selectedProvider;
    const isCheapest = providerId === localCheapest;

    let badgeClass = 'text-muted';
    let label = '';

    if (isSelected) {
        const styles = getProviderStyles(providerId);
        badgeClass = `fw-bold text-white ${styles.badgeClass} px-2 rounded`;
        label = ' <i class="bi bi-check-circle-fill text-success ms-1" title="System Choice"></i>';
    } else if (isCheapest) {
        label = ' <small class="text-muted ms-1">(Cheapest)</small>';
    }

    const borderClass = hasBorder ? 'border-bottom' : '';
    const formattedCost = formatCost(cost);

    return `
        <div class="d-flex justify-content-between ${borderClass} py-2">
            <strong>${providerName}:</strong>
            <div><span class="${badgeClass}">${symbol}${formattedCost}</span>${label}</div>
        </div>
    `;
}

/**
 * Generate service stack list for card back
 * @param {string} providerName - Display name
 * @param {string} providerId - Provider ID
 * @param {Array} services - Array of service objects { name, url }
 * @param {string} selectedProvider - Currently selected provider
 * @returns {string} HTML for the service stack
 */
function generateServiceStack(providerName, providerId, services, selectedProvider) {
    const isSelected = providerId === selectedProvider;
    const styles = getProviderStyles(providerId);
    const listClass = isSelected ? 'fw-bold' : '';
    const checkIcon = isSelected ? '<i class="bi bi-check-circle-fill text-success me-1"></i>' : '';

    if (services.length === 0) {
        return `
            <div class="mb-2">
                <strong class="${styles.textClass}">${providerName}:</strong>
                <span class="text-muted">N/A</span>
            </div>
        `;
    }

    const serviceLinks = services.map(s =>
        `<li>${checkIcon}<a href="${s.url}" target="_blank" class="text-decoration-none text-reset hover-underline">${s.name}</a></li>`
    ).join('');

    return `
        <div class="mb-2">
            <strong class="${styles.textClass}">${providerName}:</strong>
            <ul class="list-unstyled mb-1 small text-start ps-3 border-start border-2 ${styles.borderClass} ${listClass}">
                ${serviceLinks}
            </ul>
        </div>
    `;
}
