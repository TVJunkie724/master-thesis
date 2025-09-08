"use strict";

function calculateTransferCostFromAWSToInternet(dataSizeInGB) {
  const freeTierLimit = pricing.aws.transfer.pricing_tiers.freeTier.limit;
  const tier1Limit = pricing.aws.transfer.pricing_tiers.tier1.limit;
  const tier2Limit = pricing.aws.transfer.pricing_tiers.tier2.limit;
  const tier3Limit = pricing.aws.transfer.pricing_tiers.tier3.limit;
  const tier4Limit = pricing.aws.transfer.pricing_tiers.tier4.limit;
  const freeTierPrice = 0;
  const tier1Price = pricing.aws.transfer.pricing_tiers.tier1.price;
  const tier2Price = pricing.aws.transfer.pricing_tiers.tier2.price;
  const tier3Price = pricing.aws.transfer.pricing_tiers.tier3.price;
  const tier4Price = pricing.aws.transfer.pricing_tiers.tier4.price;

  let totalCost = 0;

  if (dataSizeInGB <= freeTierLimit) {
    return totalCost;
  }
  dataSizeInGB -= freeTierLimit;
  if (dataSizeInGB <= tier1Limit) {
    totalCost = dataSizeInGB * tier1Price;
  } else if (dataSizeInGB <= tier1Limit + tier2Limit) {
    totalCost =
      tier1Limit * tier1Price + (dataSizeInGB - tier1Limit) * tier2Price;
  } else if (dataSizeInGB <= tier1Limit + tier2Limit + tier3Limit) {
    totalCost =
      tier1Limit * tier1Price +
      tier2Limit * tier2Price +
      (dataSizeInGB - tier1Limit - tier2Limit) * tier3Price;
  } else {
    totalCost =
      tier1Limit * tier1Price +
      tier2Limit * tier2Price +
      tier3Limit * tier3Price +
      (dataSizeInGB - tier1Limit - tier2Limit - tier3Limit) * tier4Price;
  }

  return totalCost;
}
/**
 * This function calculates the transfer fee from the Azure network to the public internet.
 * @param {number} dataSizeInGB
 * @returns transfer fee to transfer from azure network to internet
 */

function calculateTransferCostFromAzureToInternet(dataSizeInGB) {
  const transferPricing = pricing.azure.transfer.pricing_tiers;
  let remainingData = dataSizeInGB;
  let totalCost = 0;

  if (remainingData <= transferPricing.freeTier.limit) {
    return totalCost;
  }
  remainingData -= transferPricing.freeTier.limit;

  if (remainingData <= transferPricing.tier1.limit) {
    totalCost += remainingData * transferPricing.tier1.price;
    return totalCost;
  }
  totalCost += transferPricing.tier1.limit * transferPricing.tier1.price;
  remainingData -= transferPricing.tier1.limit;

  if (remainingData <= transferPricing.tier2.limit) {
    totalCost += remainingData * transferPricing.tier2.price;
    return totalCost;
  }
  totalCost += transferPricing.tier2.limit * transferPricing.tier2.price;
  remainingData -= transferPricing.tier2.limit;

  if (remainingData <= transferPricing.tier3.limit) {
    totalCost += remainingData * transferPricing.tier3.price;
    return totalCost;
  }
  totalCost += transferPricing.tier3.limit * transferPricing.tier3.price;
  remainingData -= transferPricing.tier3.limit;

  totalCost += remainingData * transferPricing.tier4.price;

  return totalCost;
}

/* Transfer costs between Layer 2 and Layer 3 (Hot) */

function calculateTransferCostFromL2AWSToAWSHot(dataSizeInGB) {
  return 0;
}

function calculateTransferCostFromL2AWSToAzureHot(dataSizeInGB) {
  return calculateTransferCostFromAWSToInternet(dataSizeInGB);
}

function calculateTransferCostFromL2AzureToAWSHot(dataSizeInGB) {
  return calculateTransferCostFromAzureToInternet(dataSizeInGB);
}

function calculateTransferCostFromL2AzureToAzureHot(dataSizeInGB) {
  return 0;
}

/* Transfer costs between Layer 3 (Hot) and Layer 3 (Cool)*/

function calculateTransferCostFromAWSHotToAWSCool(dataSizeInGB) {
  const transferCostFromDynamoDBToS3 =
    pricing.aws.s3InfrequentAccess.transferCostFromDynamoDB;

  return dataSizeInGB * transferCostFromDynamoDBToS3;
}

function calculateTransferCostFromAWSHotToAzureCool(dataSizeInGB) {
  return calculateTransferCostFromAWSToInternet(dataSizeInGB);
}

function calculateTransferCostsFromAzureHotToAWSCool(dataSizeInGB) {
  const transferCostFromCosmosDBToS3 =
    pricing.aws.s3InfrequentAccess.transferCostFromCosmosDB;
  return (
    dataSizeInGB * transferCostFromCosmosDBToS3 +
    calculateTransferCostFromAzureToInternet(dataSizeInGB)
  );
}

function calculateTransferCostFromAzureHotToAzureCool(dataSizeInGB) {
  const transferCostFromCosmosDBToAzure =
    pricing.azure.blobStorageCool.transferCostFromCosmosDB;
  return dataSizeInGB <= 5
    ? 0
    : (dataSizeInGB - 5) * transferCostFromCosmosDBToAzure;
}

/* Transfer costs between Layer 3 (Cool) and Layer 3 (Archive) */

function calculateTransferCostFromAWSCoolToAWSArchive(dataSizeInGB) {
  return 0;
}

function calculateTransferCostFromAWSCoolToAzureArchive(dataSizeInGB) {
  return calculateTransferCostFromAWSToInternet(dataSizeInGB);
}

function calculateTransferCostFromAzureCoolToAWSArchive(dataSizeInGB) {
  return calculateTransferCostFromAzureToInternet(dataSizeInGB);
}

function calculateTransferCostFromAzureCoolToAzureArchive(dataSizeInGB) {
  return 0;
}
