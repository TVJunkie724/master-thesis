/**
 * Service Registry
 * =================
 * Central registry of all cloud services used per layer and provider.
 * 
 * This module maps each layer → provider → services with URLs,
 * including optional services and glue code for cross-cloud integration.
 */

"use strict";

/**
 * Service registry - maps layer → provider → services[]
 * Each service has: name, url
 */
const SERVICE_REGISTRY = {
    l1: {
        aws: [
            { name: 'AWS IoT Core', url: 'https://aws.amazon.com/iot-core/' },
            { name: 'Dispatcher Lambda', url: 'https://aws.amazon.com/lambda/' },
        ],
        azure: [
            { name: 'Azure IoT Hub', url: 'https://azure.microsoft.com/en-us/products/iot-hub/' },
            { name: 'Dispatcher Function', url: 'https://azure.microsoft.com/en-us/products/functions/' },
            { name: 'Event Grid Subscription', url: 'https://azure.microsoft.com/en-us/products/event-grid/' },
        ],
        gcp: [
            { name: 'Google Cloud Pub/Sub', url: 'https://cloud.google.com/pubsub' },
            { name: 'Dispatcher Function', url: 'https://cloud.google.com/functions' },
        ],
    },
    l2: {
        aws: [
            { name: 'Persister Lambda', url: 'https://aws.amazon.com/lambda/' },
            { name: 'Processor Lambdas', url: 'https://aws.amazon.com/lambda/' },
        ],
        azure: [
            { name: 'Persister Function', url: 'https://azure.microsoft.com/en-us/products/functions/' },
            { name: 'Processor Functions', url: 'https://azure.microsoft.com/en-us/products/functions/' },
        ],
        gcp: [
            { name: 'Persister Function', url: 'https://cloud.google.com/functions' },
            { name: 'Processor Functions', url: 'https://cloud.google.com/functions' },
        ],
    },
    l3_hot: {
        aws: [
            { name: 'Amazon DynamoDB', url: 'https://aws.amazon.com/dynamodb/' },
            { name: 'Hot Reader Lambda', url: 'https://aws.amazon.com/lambda/' },
        ],
        azure: [
            { name: 'Azure Cosmos DB', url: 'https://azure.microsoft.com/en-us/products/cosmos-db/' },
            { name: 'Hot Reader Function', url: 'https://azure.microsoft.com/en-us/products/functions/' },
        ],
        gcp: [
            { name: 'Google Cloud Firestore', url: 'https://cloud.google.com/firestore' },
            { name: 'Hot Reader Function', url: 'https://cloud.google.com/functions' },
        ],
    },
    l3_cool: {
        aws: [
            { name: 'Amazon S3 (IA)', url: 'https://aws.amazon.com/s3/' },
            { name: 'Hot-Cold Mover Lambda', url: 'https://aws.amazon.com/lambda/' },
            { name: 'EventBridge Scheduler', url: 'https://aws.amazon.com/eventbridge/' },
        ],
        azure: [
            { name: 'Azure Blob Storage (Cool)', url: 'https://azure.microsoft.com/en-us/products/storage/blobs/' },
            { name: 'Hot-Cold Mover Function', url: 'https://azure.microsoft.com/en-us/products/functions/' },
        ],
        gcp: [
            { name: 'Google Cloud Storage (Nearline)', url: 'https://cloud.google.com/storage' },
            { name: 'Hot-Cold Mover Function', url: 'https://cloud.google.com/functions' },
            { name: 'Cloud Scheduler', url: 'https://cloud.google.com/scheduler' },
        ],
    },
    l3_archive: {
        aws: [
            { name: 'Amazon S3 Glacier Deep Archive', url: 'https://aws.amazon.com/s3/storage-classes/glacier/' },
            { name: 'Cold-Archive Mover Lambda', url: 'https://aws.amazon.com/lambda/' },
            { name: 'EventBridge Scheduler', url: 'https://aws.amazon.com/eventbridge/' },
        ],
        azure: [
            { name: 'Azure Blob Storage (Archive)', url: 'https://azure.microsoft.com/en-us/products/storage/blobs/' },
            { name: 'Cold-Archive Mover Function', url: 'https://azure.microsoft.com/en-us/products/functions/' },
        ],
        gcp: [
            { name: 'Google Cloud Storage (Archive)', url: 'https://cloud.google.com/storage' },
            { name: 'Cold-Archive Mover Function', url: 'https://cloud.google.com/functions' },
            { name: 'Cloud Scheduler', url: 'https://cloud.google.com/scheduler' },
        ],
    },
    l4: {
        aws: [
            { name: 'AWS IoT TwinMaker', url: 'https://aws.amazon.com/iot-twinmaker/' },
        ],
        azure: [
            { name: 'Azure Digital Twins', url: 'https://azure.microsoft.com/en-us/products/digital-twins/' },
            { name: 'ADT Updater Function', url: 'https://azure.microsoft.com/en-us/products/functions/' },
            { name: 'Event Grid Subscription', url: 'https://azure.microsoft.com/en-us/products/event-grid/' },
        ],
        gcp: [
            { name: 'Not Available (Future Work)', url: '#', disabled: true },
        ],
    },
    l5: {
        aws: [
            { name: 'Amazon Managed Grafana', url: 'https://aws.amazon.com/grafana/' },
        ],
        azure: [
            { name: 'Azure Managed Grafana', url: 'https://azure.microsoft.com/en-us/products/managed-grafana/' },
        ],
        gcp: [
            { name: 'Not Available (Future Work)', url: '#', disabled: true },
        ],
    },
};

/**
 * Optional services added based on user params
 */
const OPTIONAL_SERVICES = {
    l2: {
        eventChecking: {
            aws: { name: 'Event Checker Lambda', url: 'https://aws.amazon.com/lambda/' },
            azure: { name: 'Event Checker Function', url: 'https://azure.microsoft.com/en-us/products/functions/' },
            gcp: { name: 'Event Checker Function', url: 'https://cloud.google.com/functions' },
        },
        orchestration: {
            aws: { name: 'AWS Step Functions', url: 'https://aws.amazon.com/step-functions/' },
            azure: { name: 'Azure Logic Apps', url: 'https://azure.microsoft.com/en-us/products/logic-apps/' },
            gcp: { name: 'Google Cloud Workflows', url: 'https://cloud.google.com/workflows' },
        },
        eventFeedback: {
            aws: { name: 'Event Feedback Lambda', url: 'https://aws.amazon.com/lambda/' },
            azure: { name: 'Event Feedback Function', url: 'https://azure.microsoft.com/en-us/products/functions/' },
            gcp: { name: 'Event Feedback Function', url: 'https://cloud.google.com/functions' },
        },
        eventActions: {
            aws: { name: 'Event Action Lambdas', url: 'https://aws.amazon.com/lambda/' },
            azure: { name: 'Event Action Functions', url: 'https://azure.microsoft.com/en-us/products/functions/' },
            gcp: { name: 'Event Action Functions', url: 'https://cloud.google.com/functions' },
        },
    },
};

/**
 * Glue services deployed when providers differ between layers.
 * These are calculated in the engine's transfer_costs when providers differ.
 */
const GLUE_SERVICES = {
    // L1 → L2: Connector (on L1 side) + Ingestion (on L2 side)
    connector: {
        aws: { name: 'Connector Lambda', url: 'https://aws.amazon.com/lambda/', isGlue: true },
        azure: { name: 'Connector Function', url: 'https://azure.microsoft.com/en-us/products/functions/', isGlue: true },
        gcp: { name: 'Connector Function', url: 'https://cloud.google.com/functions', isGlue: true },
    },
    ingestion: {
        aws: { name: 'Ingestion Lambda', url: 'https://aws.amazon.com/lambda/', isGlue: true },
        azure: { name: 'Ingestion Function', url: 'https://azure.microsoft.com/en-us/products/functions/', isGlue: true },
        gcp: { name: 'Ingestion Function', url: 'https://cloud.google.com/functions', isGlue: true },
    },
    // L2 → L3_hot: Hot Writer
    hotWriter: {
        aws: { name: 'Hot Writer Lambda', url: 'https://aws.amazon.com/lambda/', isGlue: true },
        azure: { name: 'Hot Writer Function', url: 'https://azure.microsoft.com/en-us/products/functions/', isGlue: true },
        gcp: { name: 'Hot Writer Function', url: 'https://cloud.google.com/functions', isGlue: true },
    },
    // L3_hot → L3_cool: Cold Writer
    coldWriter: {
        aws: { name: 'Cold Writer Lambda', url: 'https://aws.amazon.com/lambda/', isGlue: true },
        azure: { name: 'Cold Writer Function', url: 'https://azure.microsoft.com/en-us/products/functions/', isGlue: true },
        gcp: { name: 'Cold Writer Function', url: 'https://cloud.google.com/functions', isGlue: true },
    },
    // L3_cool → L3_archive: Archive Writer
    archiveWriter: {
        aws: { name: 'Archive Writer Lambda', url: 'https://aws.amazon.com/lambda/', isGlue: true },
        azure: { name: 'Archive Writer Function', url: 'https://azure.microsoft.com/en-us/products/functions/', isGlue: true },
        gcp: { name: 'Archive Writer Function', url: 'https://cloud.google.com/functions', isGlue: true },
    },
    // L3_hot → L4: ADT Pusher (on L4 side)
    adtPusher: {
        aws: { name: 'ADT Pusher Lambda', url: 'https://aws.amazon.com/lambda/', isGlue: true },
        azure: { name: 'ADT Pusher Function', url: 'https://azure.microsoft.com/en-us/products/functions/', isGlue: true },
        gcp: { name: 'ADT Pusher Function', url: 'https://cloud.google.com/functions', isGlue: true },
    },
};

/**
 * Get base services for a layer/provider combination
 * @param {string} layerId - Layer id (e.g., 'l1', 'l3_hot')
 * @param {string} providerId - Provider id (e.g., 'aws')
 * @returns {Array} Array of service objects
 */
function getBaseServices(layerId, providerId) {
    const layer = SERVICE_REGISTRY[layerId];
    if (!layer) return [];
    return layer[providerId.toLowerCase()] || [];
}

/**
 * Get services for a layer including optional services based on params
 * @param {string} layerId - Layer id
 * @param {string} providerId - Provider id
 * @param {object} params - User parameters (useEventChecking, triggerNotificationWorkflow, etc.)
 * @param {object} selectedProviders - Selected providers for each layer (used for glue services)
 * @returns {Array} Array of service objects
 */
function getServicesForLayer(layerId, providerId, params = {}, selectedProviders = {}) {
    const services = [...getBaseServices(layerId, providerId)];
    const provider = providerId.toLowerCase();

    // Add optional L2 services based on user params
    if (layerId === 'l2') {
        if (params.useEventChecking && OPTIONAL_SERVICES.l2.eventChecking[provider]) {
            services.push(OPTIONAL_SERVICES.l2.eventChecking[provider]);
        }
        if (params.triggerNotificationWorkflow && OPTIONAL_SERVICES.l2.orchestration[provider]) {
            services.push(OPTIONAL_SERVICES.l2.orchestration[provider]);
        }
        if (params.returnFeedbackToDevice && OPTIONAL_SERVICES.l2.eventFeedback[provider]) {
            services.push(OPTIONAL_SERVICES.l2.eventFeedback[provider]);
        }
        if (params.numberOfEventActions > 0 && OPTIONAL_SERVICES.l2.eventActions[provider]) {
            services.push(OPTIONAL_SERVICES.l2.eventActions[provider]);
        }
        // Glue: Ingestion function when L1 ≠ L2
        if (selectedProviders.l1 && selectedProviders.l1.toLowerCase() !== provider) {
            services.push(GLUE_SERVICES.ingestion[provider]);
        }
    }

    // Glue: Hot Writer when L2 ≠ L3_hot
    if (layerId === 'l3_hot' && selectedProviders.l2 && selectedProviders.l2.toLowerCase() !== provider) {
        services.push(GLUE_SERVICES.hotWriter[provider]);
    }

    // Glue: Cold Writer when L3_hot ≠ L3_cool
    if (layerId === 'l3_cool' && selectedProviders.l3_hot && selectedProviders.l3_hot.toLowerCase() !== provider) {
        services.push(GLUE_SERVICES.coldWriter[provider]);
    }

    // Glue: Archive Writer when L3_cool ≠ L3_archive
    if (layerId === 'l3_archive' && selectedProviders.l3_cool && selectedProviders.l3_cool.toLowerCase() !== provider) {
        services.push(GLUE_SERVICES.archiveWriter[provider]);
    }

    // Glue: ADT Pusher when L3_hot ≠ L4
    if (layerId === 'l4' && selectedProviders.l3_hot && selectedProviders.l3_hot.toLowerCase() !== provider) {
        services.push(GLUE_SERVICES.adtPusher[provider]);
    }

    return services;
}

/**
 * Check if any glue services are included for this layer
 * @param {string} layerId - Layer id
 * @param {object} selectedProviders - Selected providers for each layer
 * @returns {boolean} True if glue services would be added
 */
function hasGlueServices(layerId, providerId, selectedProviders = {}) {
    const provider = providerId.toLowerCase();

    if (layerId === 'l2' && selectedProviders.l1 && selectedProviders.l1.toLowerCase() !== provider) {
        return true;
    }
    if (layerId === 'l3_hot' && selectedProviders.l2 && selectedProviders.l2.toLowerCase() !== provider) {
        return true;
    }
    if (layerId === 'l3_cool' && selectedProviders.l3_hot && selectedProviders.l3_hot.toLowerCase() !== provider) {
        return true;
    }
    if (layerId === 'l3_archive' && selectedProviders.l3_cool && selectedProviders.l3_cool.toLowerCase() !== provider) {
        return true;
    }
    if (layerId === 'l4' && selectedProviders.l3_hot && selectedProviders.l3_hot.toLowerCase() !== provider) {
        return true;
    }

    return false;
}

