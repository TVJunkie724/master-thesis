/**
 * Formatters Utility
 * ==================
 * Formatting helpers for costs, currency, and display.
 * 
 * These functions provide consistent formatting across the UI
 * for monetary values and path visualization.
 */

"use strict";

/**
 * Format cost value with proper locale and decimal places
 * @param {number} cost - Cost value
 * @param {string} currency - Currency code ('USD' or 'EUR')
 * @returns {string} Formatted cost string (e.g., "1,234.56")
 */
function formatCost(cost, currency = 'USD') {
    if (cost === undefined || cost === null || isNaN(cost)) {
        return 'N/A';
    }
    return cost.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

/**
 * Get currency symbol
 * @param {string} currency - Currency code
 * @returns {string} Currency symbol ('$' or '€')
 */
function getCurrencySymbol(currency = 'USD') {
    return currency === 'EUR' ? '€' : '$';
}

/**
 * Format cost with currency symbol
 * @param {number} cost - Cost value
 * @param {string} currency - Currency code
 * @returns {string} Formatted cost with symbol (e.g., "$1,234.56")
 */
function formatCostWithCurrency(cost, currency = 'USD') {
    const symbol = getCurrencySymbol(currency);
    return `${symbol}${formatCost(cost, currency)}`;
}

/**
 * Format cheapest path as badge HTML
 * Creates visual badges with arrows for the path visualization
 * @param {Array<string>} cheapestPath - Path segments (e.g., ['L1_AWS', 'L2_Azure'])
 * @returns {string} HTML string of path badges
 */
function formatPathAsBadges(cheapestPath) {
    if (!Array.isArray(cheapestPath) || cheapestPath.length === 0) {
        return '<span class="text-muted">No path available</span>';
    }

    return cheapestPath
        .map(segment => {
            const badgeClass = getPathBadgeClass(segment);
            return `<span class="badge ${badgeClass} mx-1">${segment}</span>`;
        })
        .join('<i class="bi bi-arrow-right text-muted mx-2"></i>');
}

/**
 * Get badge class based on segment content
 * Determines provider from segment text and returns appropriate CSS class
 * @param {string} segment - Path segment (e.g., 'L1_AWS')
 * @returns {string} Bootstrap badge class
 */
function getPathBadgeClass(segment) {
    const lower = segment.toLowerCase();
    if (lower.includes('aws') || lower.includes('amazon')) return 'badge-aws';
    if (lower.includes('azure')) return 'badge-azure';
    if (lower.includes('gcp') || lower.includes('google')) return 'badge-gcp';
    return 'bg-secondary';
}
