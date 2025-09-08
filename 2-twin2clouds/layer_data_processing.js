"use strict";

/* LAYER 2 - Data Processing Layer */

/**
 * This function calculates the cost of AWS Lambda.
 * This includes 1 million free requests per month and 400 000 GB/s compute time per month for free
 * @param {} numberOfDevices
 * @param {} deviceSendingIntervalInMinutes
 * @param {} averageSizeOfMessageInKb
 * @returns an object including the provider used, the total monthly costs, the data size in GB and the total messages sent per month
 */
function calculateAWSCostDataProcessing(
  numberOfDevices,
  deviceSendingIntervalInMinutes,
  averageSizeOfMessageInKb
) {
  const executionDurationInMS = 100;
  const allocatedMemoryInGB = 128 / 1024;
  const layer2Pricing = pricing.aws.lambda;

  const executionsPerMonth =
    numberOfDevices * (60 / deviceSendingIntervalInMinutes) * 730;

  let dataSizeInGB =
    (executionsPerMonth * averageSizeOfMessageInKb) / (1024 * 1024);

  const requestCost =
    executionsPerMonth > layer2Pricing.freeRequests
      ? (executionsPerMonth - layer2Pricing.freeRequests) *
        layer2Pricing.requestPrice
      : 0;

  const totalComputeSeconds =
    executionsPerMonth * executionDurationInMS * 0.001;

  const durationCost =
    Math.max(
      totalComputeSeconds * allocatedMemoryInGB - layer2Pricing.freeComputeTime,
      0
    ) * layer2Pricing.durationPrice;

  const totalMonthlyCost = requestCost + durationCost;

  return {
    provider: "AWS",
    totalMonthlyCost: totalMonthlyCost,
    dataSizeInGB: dataSizeInGB,
    totalMessagesPerMonth: executionsPerMonth,
  };
}

/**
 * We execute the same function as for AWS since the costs and the free tier per month are identical
 * @param {} numberOfDevices
 * @param {} deviceSendingIntervalInMinutes
 * @param {} averageSizeOfMessageInKb
 * @returns
 */

function calculateAzureCostDataProcessing(
  numberOfDevices,
  deviceSendingIntervalInMinutes,
  averageSizeOfMessageInKb
) {
  let result = calculateAWSCostDataProcessing(
    numberOfDevices,
    deviceSendingIntervalInMinutes,
    averageSizeOfMessageInKb
  );
  result.provider = "Azure";
  return result;
}
