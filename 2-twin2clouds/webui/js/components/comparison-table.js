/**
 * Comparison Table Component
 * ===========================
 * Generates comparison tables for multi-provider path optimization.
 * 
 * Used in warning boxes to show why the optimizer selected a specific
 * provider combination over others (showing cost breakdowns).
 */

"use strict";

/**
 * Generate a comparison table for layer combinations
 * @param {Array} combinations - Array of combination objects
 * @param {string} type - Table type: 'l2_l3', 'cool', or 'archive'
 * @param {object} selectedProviders - Currently selected providers
 * @returns {string} HTML table string
 */
function generateComparisonTable(combinations, type = 'l2_l3', selectedProviders = {}) {
    if (!combinations || combinations.length === 0) return '';

    const headers = getTableHeaders(type);
    const rows = generateTableRows(combinations, type, selectedProviders);

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
 * Get table headers based on type
 * @param {string} type - Table type
 * @returns {string} HTML for table headers
 */
function getTableHeaders(type) {
    switch (type) {
        case 'l2_l3':
            return `
                <tr>
                    <th><small>Combination</small></th>
                    <th class="text-end"><small>L2 Processing Cost</small></th>
                    <th class="text-end"><small>L3 Hot Cost</small></th>
                    <th class="text-end"><small>Transfer/Glue</small></th>
                    <th class="text-end"><small>Total</small></th>
                </tr>
            `;
        case 'cool':
            return `
                <tr>
                    <th><small>Path (Hot &rarr; Cool &rarr; Archive)</small></th>
                    <th class="text-end"><small>Transfer (Hot&rarr;Cool)</small></th>
                    <th class="text-end"><small>Cool Cost</small></th>
                    <th class="text-end"><small>Transfer (Cool&rarr;Archive)</small></th>
                    <th class="text-end"><small>Archive Cost</small></th>
                    <th class="text-end"><small>Total</small></th>
                </tr>
            `;
        case 'archive':
            return `
                <tr>
                    <th><small>Path (... &rarr; Cool &rarr; Archive)</small></th>
                    <th class="text-end"><small>Transfer (Cool&rarr;Archive)</small></th>
                    <th class="text-end"><small>Archive Cost</small></th>
                    <th class="text-end"><small>Total</small></th>
                </tr>
            `;
        default:
            return '';
    }
}

/**
 * Generate table rows from combinations data
 * @param {Array} combinations - Combination data from optimizer
 * @param {string} type - Table type
 * @param {object} selectedProviders - Currently selected providers
 * @returns {string} HTML for table rows
 */
function generateTableRows(combinations, type, selectedProviders) {
    return combinations.slice(0, 3).map(c => {
        const isSelected = isRowSelected(c, type, selectedProviders);
        const rowClass = isSelected ? 'table-success' : '';

        switch (type) {
            case 'l2_l3':
                return `
                    <tr class="${rowClass}">
                        <td><small>${c.l2_provider} + ${c.l3_provider}</small></td>
                        <td class="text-end"><small>$${(c.l2_cost || 0).toFixed(2)}</small></td>
                        <td class="text-end"><small>$${(c.l3_cost || 0).toFixed(2)}</small></td>
                        <td class="text-end"><small>$${((c.transfer_cost || 0) + (c.glue_cost || 0)).toFixed(2)}</small></td>
                        <td class="text-end fw-bold"><small>$${(c.total_cost || 0).toFixed(2)}</small></td>
                    </tr>
                `;
            case 'cool':
                return `
                    <tr class="${rowClass}">
                        <td><small>${c.path}</small></td>
                        <td class="text-end"><small>$${(c.trans_h_c || 0).toFixed(2)}</small></td>
                        <td class="text-end"><small>$${(c.cool_cost || 0).toFixed(2)}</small></td>
                        <td class="text-end"><small>$${(c.trans_c_a || 0).toFixed(2)}</small></td>
                        <td class="text-end"><small>$${(c.archive_cost || 0).toFixed(2)}</small></td>
                        <td class="text-end fw-bold"><small>$${(c.total_cost || 0).toFixed(2)}</small></td>
                    </tr>
                `;
            case 'archive':
                return `
                    <tr class="${rowClass}">
                        <td><small>${c.path}</small></td>
                        <td class="text-end"><small>$${(c.trans_c_a || 0).toFixed(2)}</small></td>
                        <td class="text-end"><small>$${(c.archive_cost || 0).toFixed(2)}</small></td>
                        <td class="text-end fw-bold"><small>$${(c.total_cost || 0).toFixed(2)}</small></td>
                    </tr>
                `;
            default:
                return '';
        }
    }).join('');
}

/**
 * Check if a row should be highlighted as selected
 * @param {object} combination - Row data
 * @param {string} type - Table type
 * @param {object} selectedProviders - Currently selected providers
 * @returns {boolean} True if row matches current selection
 */
function isRowSelected(combination, type, selectedProviders) {
    if (!selectedProviders) return false;

    switch (type) {
        case 'l2_l3':
            return combination.l2_provider?.toLowerCase() === selectedProviders.l3_hot &&
                combination.l3_provider?.toLowerCase() === selectedProviders.l2;
        case 'cool':
        case 'archive':
            if (!combination.path) return false;
            const segments = combination.path.split('->').map(s => s.trim().toLowerCase());
            if (segments.length >= 3) {
                return segments[0].includes(selectedProviders.l3_hot) &&
                    segments[1].includes(selectedProviders.l3_cool) &&
                    segments[2].includes(selectedProviders.l3_archive);
            }
            return false;
        default:
            return false;
    }
}

/**
 * Generate detailed comparison table for L1/L4 candidates
 * Used for showing glue code cost breakdowns
 * @param {Array} candidates - Array of candidate objects
 * @param {string} selectedProvider - Currently selected provider
 * @returns {string} HTML table string
 */
function generateDetailedComparisonTable(candidates, selectedProvider = null) {
    if (!candidates || candidates.length === 0) return '';

    const rows = candidates
        .sort((a, b) => a.total_cost - b.total_cost)
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
