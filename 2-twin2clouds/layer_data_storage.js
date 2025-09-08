"use strict";

/* LAYER 3 - Data Storage Layer */
/* We have 3 layers within this layer if we want. We have hot storage, cool storage and archive storage.
  This means we have a couple of paths we need to calculate cost-wise.*/

/* HOT Storage */

/**
 * This function calculates the cost of the AWS service DynamoDB.
 * This service is used for hot and warm storage of the Digital Twin
 * By using the user inputs for layer 1 we will calculate the amount of data that needs to be stored
 * and use that in order to estimate the cost of the given service for storing that data.
 * Since write costs are also important to calculate to overall costs of DynamoDB we also need use the amount of
 * messages per month and the average size of these messages.
 *
 * @param {number} dataSizeInGB
 * @param {number} totalMessagesPerMonth
 * @param {number} averageSizeOfMessageInKb
 * @param {number} storageDurationInMonths
 * @returns an object including the provider name, the monthly costs, and the data size in GB that is needed for the storage
 */

function calculateDynamoDBCost(
  dataSizeInGB,
  totalMessagesPerMonth,
  averageSizeOfMessageInKb,
  storageDurationInMonths
) {
  let storageNeededForDuration = dataSizeInGB * (storageDurationInMonths + 0.5); // added buffer in addition to the data size

  let writeUnitsNeeded = totalMessagesPerMonth * averageSizeOfMessageInKb;
  let readUnitsNeeded = totalMessagesPerMonth / 2;

  const writePrice = global.pricing.aws.dynamoDB.writePrice; // per million units
  const readPrice = global.pricing.aws.dynamoDB.readPrice; // per million units
  const storagePrice = global.pricing.aws.dynamoDB.storagePrice; // per GB after the first 25gb
  const freeStoragePerMonth = global.pricing.aws.dynamoDB.freeStorage;

  let totalStoragePrice =
    storageNeededForDuration <= freeStoragePerMonth * storageDurationInMonths
      ? 0
      : Math.ceil(
          (storageNeededForDuration -
            freeStoragePerMonth * storageDurationInMonths) *
            storagePrice
        );

  let totalMonthlyCost =
    writePrice * writeUnitsNeeded +
    readPrice * readUnitsNeeded +
    totalStoragePrice;

  return {
    provider: "AWS",
    totalMonthlyCost: totalMonthlyCost,
    dataSizeInGB: dataSizeInGB,
  };
}

/**
 * This function calculates the estimated costs for the Azure service CosmosDB.
 * Azure has a minimum of 400 request units / s per month.
 * We use a multiplier in the function to estimate the increase on costs based on the average message size because there is no real rule on how this is calculated by Azure.
 * The given number was tested with various inputs on the calculator and came very close to the actual result.
 * @param {} dataSizeInGB
 * @param {} totalMessagesPerMonth
 * @returns
 */

function calculateCosmosDBCost(
  dataSizeInGB,
  totalMessagesPerMonth,
  averageSizeOfMessageInKb,
  storageDurationInMonths
) {
  let storageNeededForDuration = dataSizeInGB * (storageDurationInMonths + 0.5);

  let requestUnitsNeeded = global.pricing.azure.cosmosDB.minimumRequestUnits; // minimum of request units that CosmosDB offers
  let writesPerSecond = totalMessagesPerMonth / (30 * 24 * 60 * 60);
  let readsPerSecond = writesPerSecond;
  const multiplierForMessageSize = 1.0 + (averageSizeOfMessageInKb - 1) * 0.05; // we use this in order to estimate the costs when the RUs increase since the scaling on Azure calculator is not understandable and these values are giving results very close to the calculator

  let RUsPerWrite = global.pricing.azure.cosmosDB.RUsPerWrite;
  let RUsPerRead = global.pricing.azure.cosmosDB.RUsPerRead;

  let totalWriteRUs = writesPerSecond * RUsPerWrite * multiplierForMessageSize; // depending on message
  let totalReadRUs = readsPerSecond * RUsPerRead;

  if (Math.ceil(totalWriteRUs + totalReadRUs) > requestUnitsNeeded) {
    requestUnitsNeeded = Math.ceil(totalWriteRUs + totalReadRUs);
  }

  let storagePrice = global.pricing.azure.cosmosDB.storagePrice;
  let requestPrice = global.pricing.azure.cosmosDB.requestPrice;

  let totalMonthlyCost =
    requestUnitsNeeded * requestPrice +
    storageNeededForDuration * storagePrice; 
  return {
    provider: "Azure",
    totalMonthlyCost: totalMonthlyCost,
    dataSizeInGB: dataSizeInGB,
  };
}

/* COOL Storage */

/**
 * This function calculates the price for the AWS S3-Infrequent Access storage needed
 * To do so we use the monthly storage that we need in the hot layer to estimate the costs for the cold layer.
 * This is because we want to move data once per month in chunks of 100MB objects.
 * From this we calculate the amount of monthly PUT requests needed.
 * Since this is infrequent-access tier we assume that maybe 10% of the stored data will be retrieved per month in addition to all of the data that needs to be moved to the archive tier.
 * Minimum storage duration needs to be 1 month, otherwise AWS charges extra fees for early deletion of data.
 *
 * @param {number} dataSizeInGB
 * @param {number} hotStorageDurationInMonths
 * @param {string} previousProvider
 * @returns an object including the provider, the total monthly cost, and the amount of data stored.
 */

function calculateS3InfrequentAccessCost(
  dataSizeInGB,
  coolStorageDurationInMonths
) {
  const storagePrice = global.pricing.aws.s3InfrequentAccess.storagePrice; // per GB
  const upfrontPrice = global.pricing.aws.s3InfrequentAccess.upfrontPrice; // per GB
  const requestPrice = global.pricing.aws.s3InfrequentAccess.requestPrice; //per request
  const dataRetrievalPrice = global.pricing.aws.s3InfrequentAccess.dataRetrievalPrice; // per GB
  const dataRetrievalAmount =
    dataSizeInGB * coolStorageDurationInMonths * 0.1 + dataSizeInGB;

  let amountOfRequestsNeeded = Math.ceil((dataSizeInGB * 1024) / 100) * 2; // We need this for initial puts and monthly lifecycle updates

  let totalMonthlyCost =
    storagePrice * dataSizeInGB * coolStorageDurationInMonths +
    upfrontPrice * dataSizeInGB * coolStorageDurationInMonths +
    requestPrice * amountOfRequestsNeeded +
    dataRetrievalPrice * dataRetrievalAmount;

  return {
    provider: "AWS",
    totalMonthlyCost: totalMonthlyCost,
    dataSizeInGB: dataSizeInGB,
  };
}

/**
 * We store the objects in cool storage just as we did in AWS' S3-Infrequent Access in 100MB objects.
 * @param {} dataSizeInGB
 * @param {} previousProvider
 * @returns an object including the provider, the total monthly cost, and the amount of data stored.
 */

function calculateAzureBlobStorageCost(
  dataSizeInGB,
  coolStorageDurationInMonths
) {
  const amountOfWritesNeeded = Math.ceil((dataSizeInGB * 1024) / 100);
  const amountOfReadsNeeded = amountOfWritesNeeded * 0.1; // assuming 10% of the data stored will be read. Same assuption as we used in AWS.
  const dataRetrievalAmount = dataSizeInGB * 0.1 + dataSizeInGB; // again assuming 10% of the data stored needs to be retrieved + all of the data that is moved for this month to the archive layer.

  const storagePrice = global.pricing.azure.blobStorageCool.storagePrice; // per GB
  const writePrice = global.pricing.azure.blobStorageCool.writePrice; //per 10000 writes
  const readPrice = global.pricing.azure.blobStorageCool.readPrice; // per 10000 reads
  const dataRetrievalPrice = global.pricing.azure.blobStorageCool.dataRetrievalPrice; // per GB

  let totalMonthlyCost =
    storagePrice * dataSizeInGB * coolStorageDurationInMonths +
    amountOfWritesNeeded * writePrice +
    amountOfReadsNeeded * readPrice +
    dataRetrievalAmount * dataRetrievalPrice;

  return {
    provider: "Azure",
    totalMonthlyCost: totalMonthlyCost,
    dataSizeInGB: dataSizeInGB,
  };
}

/* ARCHIVE Storage */
/* This tier will store data up to 3 years.*/

/**
 * This function calculates the costs for S3 Glacier Deep Archive. We assume that 1% of the total data stored
 * will be retrieved at some point to estimate the cost.
 * Data needs to be stored for at least 6 months, in order to avoid extra fees for early deletion.
 *
 * @param {number} dataSizeInGB
 * @param {string} previousProvider
 */
function calculateS3GlacierDeepArchiveCost(
  dataSizeInGB,
  archiveStorageDurationInMonths
) {
  const storageNeededForDuration =
    dataSizeInGB * archiveStorageDurationInMonths;
  const amountOfRequestsNeeded = dataSizeInGB * 2; // we use this for puts and lifecycle
  const dataRetrievalAmount = 0.01 * storageNeededForDuration;

  const storagePrice = global.pricing.aws.s3GlacierDeepArchive.storagePrice; // per GB
  const lifecycleAndWritePrice =
    global.pricing.aws.s3GlacierDeepArchive.lifecycleAndWritePrice; // per request
  const dataRetrievalPrice =
    global.pricing.aws.s3GlacierDeepArchive.dataRetrievalPrice; // per GB (bulk)

  let totalMonthlyCost =
    storageNeededForDuration * storagePrice +
    amountOfRequestsNeeded * lifecycleAndWritePrice +
    dataRetrievalAmount * dataRetrievalPrice;

  return {
    provider: "AWS",
    dataSizeInGB: dataSizeInGB,
    totalMonthlyCost: totalMonthlyCost,
  };
}

/**
 * This function calculates the costs of the archive storage for Azures Blob Storage service.
 * Again we assume a retrieval rate of 1%.
 * @param {*} dataSizeInGB
 * @param {*} previousProvider
 */
function calculateAzureBlobStorageArchiveCost(
  dataSizeInGB,
  archiveStorageDurationInMonths
) {
  const storageNeededForDuration =
    dataSizeInGB * archiveStorageDurationInMonths;
  const amountOfWritesNeeded = dataSizeInGB;
  const dataRetrievalAmount = storageNeededForDuration * 0.01;

  const storagePrice = global.pricing.azure.blobStorageArchive.storagePrice; // per GB
  const writePrice = global.pricing.azure.blobStorageArchive.writePrice; // per request
  const dataRetrievalPrice =
    global.pricing.azure.blobStorageArchive.dataRetrievalPrice; // per GB

  let totalMonthlyCost =
    storageNeededForDuration * storagePrice +
    amountOfWritesNeeded * writePrice +
    dataRetrievalAmount * dataRetrievalPrice;

  return {
    provider: "Azure",
    dataSizeInGB: dataSizeInGB,
    totalMonthlyCost: totalMonthlyCost,
  };
}

module.exports = {
  calculateDynamoDBCost,
  calculateCosmosDBCost,  
  calculateS3InfrequentAccessCost,
  calculateAzureBlobStorageCost,
  calculateS3GlacierDeepArchiveCost,
  calculateAzureBlobStorageArchiveCost,
};