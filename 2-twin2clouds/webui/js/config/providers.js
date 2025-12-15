/**
 * Provider Configuration
 * ======================
 * Central definitions for all cloud providers.
 * 
 * This module contains provider metadata and styling information
 * used throughout the UI for consistent provider representation.
 */

"use strict";

/**
 * Provider definitions
 * 
 * Each provider has:
 * - id: Unique identifier used in code (lowercase)
 * - name: Short display name
 * - displayName: Full display name
 */
const PROVIDERS = {
    AWS: {
        id: 'aws',
        name: 'AWS',
        displayName: 'Amazon Web Services',
    },
    AZURE: {
        id: 'azure',
        name: 'Azure',
        displayName: 'Microsoft Azure',
    },
    GCP: {
        id: 'gcp',
        name: 'GCP',
        displayName: 'Google Cloud Platform',
    },
};

/**
 * Provider CSS classes for styling
 * Maps provider ID to Bootstrap and custom CSS classes
 */
const PROVIDER_STYLES = {
    aws: {
        badgeClass: 'badge-aws',
        textClass: 'text-aws',
        borderClass: 'border-aws',
    },
    azure: {
        badgeClass: 'badge-azure',
        textClass: 'text-azure',
        borderClass: 'border-azure',
    },
    gcp: {
        badgeClass: 'badge-gcp',
        textClass: 'text-gcp',
        borderClass: 'border-gcp',
    },
};

/**
 * Get provider by ID
 * @param {string} id - Provider id (e.g., 'aws', 'azure')
 * @returns {object|null} Provider object or null
 */
function getProviderById(id) {
    return Object.values(PROVIDERS).find(p => p.id === id.toLowerCase()) || null;
}

/**
 * Get provider styles by ID
 * @param {string} id - Provider id
 * @returns {object} Style classes object (defaults to AWS styles if not found)
 */
function getProviderStyles(id) {
    return PROVIDER_STYLES[id.toLowerCase()] || PROVIDER_STYLES.aws;
}
