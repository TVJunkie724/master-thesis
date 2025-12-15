/**
 * Path Parser Utility
 * ====================
 * Parses the cheapestPath array from the API response.
 * 
 * The optimizer returns a path like:
 * ['L1_AWS', 'L2_AWS', 'L3_hot_AWS', 'L3_cool_Azure', 'L3_archive_GCP', 'L4_AWS', 'L5_AWS']
 * 
 * This module extracts the selected provider for each layer from this format.
 */

"use strict";

/**
 * Parse cheapest path array to extract selected providers for each layer.
 * 
 * Path format: ['L1_AWS', 'L2_AWS', 'L3_hot_AWS', 'L3_cool_Azure', 'L3_archive_GCP', 'L4_AWS', 'L5_AWS']
 * 
 * @param {Array<string>} cheapestPath - Array of path segments
 * @returns {object} Map of layer ID to selected provider
 */
function parseSelectedProviders(cheapestPath) {
    if (!Array.isArray(cheapestPath)) {
        console.error('parseSelectedProviders: expected array, got', typeof cheapestPath);
        return getDefaultProviders();
    }

    return {
        l1: extractProvider(cheapestPath, 'L1_', 1),
        l2: extractProvider(cheapestPath, 'L2_', 1),
        l3_hot: extractProvider(cheapestPath, 'L3_hot_', 2),
        l3_cool: extractProvider(cheapestPath, 'L3_cool_', 2),
        l3_archive: extractProvider(cheapestPath, 'L3_archive_', 2),
        l4: extractProvider(cheapestPath, 'L4_', 1),
        l5: extractProvider(cheapestPath, 'L5_', 1),
    };
}

/**
 * Extract provider from path segment
 * 
 * For simple layers (L1, L2, L4, L5): segment is 'L1_AWS' → split index 1 = 'AWS'
 * For L3 tiers: segment is 'L3_hot_AWS' → split index 2 = 'AWS'
 * 
 * @param {Array} path - Cheapest path array
 * @param {string} prefix - Segment prefix to find
 * @param {number} splitIndex - Index to extract provider after split('_')
 * @returns {string} Provider id (lowercase)
 */
function extractProvider(path, prefix, splitIndex) {
    const segment = path.find(p => p.startsWith(prefix));
    if (!segment) return 'aws';

    const parts = segment.split('_');
    const provider = parts[splitIndex];
    return provider ? provider.toLowerCase() : 'aws';
}

/**
 * Get default providers (all AWS)
 * Fallback when path parsing fails or path is empty
 * @returns {object} Default provider mapping
 */
function getDefaultProviders() {
    return {
        l1: 'aws',
        l2: 'aws',
        l3_hot: 'aws',
        l3_cool: 'aws',
        l3_archive: 'aws',
        l4: 'aws',
        l5: 'aws',
    };
}

/**
 * Check if a provider is selected for a layer
 * @param {object} selectedProviders - Selected providers map
 * @param {string} layerId - Layer ID
 * @param {string} providerId - Provider ID to check
 * @returns {boolean} True if provider is selected for layer
 */
function isProviderSelectedForLayer(selectedProviders, layerId, providerId) {
    const selected = selectedProviders[layerId];
    return selected && selected.toLowerCase() === providerId.toLowerCase();
}
