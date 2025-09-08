"use strict";

/* LAYER 1 - Data Acqusition Layer*/

/**
 * This function calculates the prices for AWS service IoT Core, that is used for the Data Acquisition of the Digital Twin
 *
 * @param {number} numberOfDevices
 * @param {number} deviceSendingIntervalInMinutes
 * @param {number} averageSizeOfMessageInKb
 * @returns and object including the name of the provider, the monthly cost, the total messages per month, the data size in GB
 */

function calculateAWSCostDataAcquisition(
  numberOfDevices,
  deviceSendingIntervalInMinutes,
  averageSizeOfMessageInKb
) {
  const layerPricing = pricing.aws.iotCore;
  const tier1Limit = layerPricing.pricing_tiers.tier1.limit;
  const tier2Limit = layerPricing.pricing_tiers.tier2.limit;
  const tier3Limit = layerPricing.pricing_tiers.tier3.limit;
  const priceTier1 = layerPricing.pricing_tiers.tier1.price;
  const priceTier2 = layerPricing.pricing_tiers.tier2.price;
  const priceTier3 = layerPricing.pricing_tiers.tier3.price;

  const totalMessagesPerMonth = Math.ceil(
    numberOfDevices * (1 / deviceSendingIntervalInMinutes) * 60 * 24 * 30
  );
  const dataSizeInGB =
    (totalMessagesPerMonth * averageSizeOfMessageInKb) / (1024 * 1024);

  let totalMessagesPerMonthAWS =
    averageSizeOfMessageInKb > 5
      ? totalMessagesPerMonth * Math.ceil(averageSizeOfMessageInKb / 5)
      : totalMessagesPerMonth;

  let numberOfRulesTriggered = totalMessagesPerMonthAWS;

  let remainingMessages = totalMessagesPerMonthAWS;
  let monthlyCost =
    numberOfDevices * layerPricing.pricePerDeviceAndMonth +
    2 * numberOfRulesTriggered * layerPricing.priceRulesTriggered;

  // Tiered Pricing
  if (remainingMessages > tier1Limit) {
    monthlyCost += tier1Limit * priceTier1;
    remainingMessages -= tier1Limit;
  } else {
    monthlyCost += remainingMessages * priceTier1;
    return {
      provider: "AWS",
      totalMonthlyCost: monthlyCost,
      totalMessagesPerMonth: totalMessagesPerMonth,
      dataSizeInGB: Math.ceil(dataSizeInGB),
    };
  }

  if (remainingMessages > tier2Limit - tier1Limit) {
    monthlyCost += (tier2Limit - tier1Limit) * priceTier2;
    remainingMessages -= tier2Limit - tier1Limit;
  } else {
    monthlyCost += remainingMessages * priceTier2;
    return {
      provider: "AWS",
      totalMonthlyCost: monthlyCost,
      totalMessagesPerMonth: totalMessagesPerMonth,
      dataSizeInGB: Math.ceil(dataSizeInGB),
    };
  }

  monthlyCost += remainingMessages * priceTier3;

  return {
    provider: "AWS",
    totalMonthlyCost: monthlyCost,
    totalMessagesPerMonth: totalMessagesPerMonth,
    dataSizeInGB: Math.ceil(dataSizeInGB),
  };
}

/**
 *  This function is used to calculate the cost for the Microsoft Azure service IoT Hub
 *
 * @param {number} numberOfDevices
 * @param {number} deviceSendingIntervalInMinutes
 * @param {number} averageSizeOfMessageInKb
 * @returns and object including the name of the provider, the monthly cost, the total messages per month, the data size in GB
 */
function calculateAzureCostDataAcquisition(
  numberOfDevices,
  deviceSendingIntervalInMinutes,
  averageSizeOfMessageInKb
) {
  let layerPricing = pricing.azure.iotHub;
  let monthlyCost;
  let monthlyAzurePrice;
  let azureThresholdMonthly;
  let totalMessagesPerMonthAzure;

  let totalMessagesPerMonth = Math.ceil(
    numberOfDevices * (1 / deviceSendingIntervalInMinutes) * 60 * 24 * 30
  );
  let dataSizeInGB =
    (totalMessagesPerMonth * averageSizeOfMessageInKb) / (1024 * 1024);

  totalMessagesPerMonthAzure =
    averageSizeOfMessageInKb > 4
      ? totalMessagesPerMonth * Math.ceil(averageSizeOfMessageInKb / 4)
      : totalMessagesPerMonth;

  if (totalMessagesPerMonthAzure <= layerPricing.pricing_tiers.tier1.limit) {
    azureThresholdMonthly = layerPricing.pricing_tiers.tier1.threshold;
    monthlyAzurePrice = layerPricing.pricing_tiers.tier1.price;
  } else if (
    totalMessagesPerMonthAzure <= layerPricing.pricing_tiers.tier2.limit
  ) {
    azureThresholdMonthly = layerPricing.pricing_tiers.tier2.threshold;
    monthlyAzurePrice = layerPricing.pricing_tiers.tier2.price;
  } else {
    azureThresholdMonthly = layerPricing.pricing_tiers.tier3.threshold;
    monthlyAzurePrice = layerPricing.pricing_tiers.tier3.price;
  }

  if (totalMessagesPerMonthAzure > azureThresholdMonthly) {
    monthlyCost =
      Math.ceil(totalMessagesPerMonthAzure / azureThresholdMonthly) *
      monthlyAzurePrice;
  } else {
    monthlyCost = monthlyAzurePrice;
  }

  return {
    provider: "Azure",
    totalMonthlyCost: monthlyCost,
    totalMessagesPerMonth: totalMessagesPerMonth,
    dataSizeInGB: Math.ceil(dataSizeInGB),
  };
}
