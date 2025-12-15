/**
 * Layer Configuration
 * ===================
 * Central definitions for all layers in the Twin2Clouds architecture.
 * 
 * This module provides the layer registry with display properties, 
 * ordering, and path prefix patterns for parsing the optimizer's
 * cheapest path output.
 */

"use strict";

/**
 * Layer definitions with display properties
 * 
 * Each layer has:
 * - id: Unique identifier used in code (lowercase)
 * - name: Short display name
 * - displayName: Full display name for UI headers
 * - order: Sort order for display (1-indexed)
 * - pathPrefix: Pattern to match in cheapestPath array
 */
const LAYERS = {
    L1: {
        id: 'l1',
        name: 'Data Acquisition',
        displayName: 'Layer 1: Data Acquisition',
        order: 1,
        pathPrefix: 'L1_',
    },
    L2: {
        id: 'l2',
        name: 'Data Processing',
        displayName: 'Layer 2: Data Processing',
        order: 2,
        pathPrefix: 'L2_',
    },
    L3_HOT: {
        id: 'l3_hot',
        name: 'Hot Storage',
        displayName: 'Layer 3: Hot Storage',
        order: 3,
        pathPrefix: 'L3_hot_',
    },
    L3_COOL: {
        id: 'l3_cool',
        name: 'Cool Storage',
        displayName: 'Layer 3: Cool Storage',
        order: 4,
        pathPrefix: 'L3_cool_',
    },
    L3_ARCHIVE: {
        id: 'l3_archive',
        name: 'Archive Storage',
        displayName: 'Layer 3: Archive Storage',
        order: 5,
        pathPrefix: 'L3_archive_',
    },
    L4: {
        id: 'l4',
        name: 'Twin Management',
        displayName: 'Layer 4: Twin Management',
        order: 6,
        pathPrefix: 'L4_',
    },
    L5: {
        id: 'l5',
        name: 'Visualization',
        displayName: 'Layer 5: Visualization',
        order: 7,
        pathPrefix: 'L5_',
    },
};

/**
 * Layer order for cheapest path display
 * Array of layer objects in display order
 */
const LAYER_ORDER = [
    LAYERS.L1,
    LAYERS.L2,
    LAYERS.L3_HOT,
    LAYERS.L3_COOL,
    LAYERS.L3_ARCHIVE,
    LAYERS.L4,
    LAYERS.L5,
];

/**
 * Get layer by ID
 * @param {string} id - Layer id (e.g., 'l1', 'l3_hot')
 * @returns {object|null} Layer object or null if not found
 */
function getLayerById(id) {
    return Object.values(LAYERS).find(l => l.id === id) || null;
}

/**
 * Get layer by path prefix
 * @param {string} prefix - Path prefix (e.g., 'L1_', 'L3_hot_')
 * @returns {object|null} Layer object or null if not found
 */
function getLayerByPathPrefix(prefix) {
    return Object.values(LAYERS).find(l => l.pathPrefix === prefix) || null;
}
