"use strict";

let pricing;

// Load JSON Pricing Data
async function loadPricingData() {
  try {
    var response = await fetch("./pricing.json"); // Fetch JSON file
    pricing = await response.json(); // Parse JSON into JavaScript object
  } catch (error) {
    console.error("Error loading pricing data:", error);
  }
}

/**
 * 
 * @returns Params object from UI input
 */
async function readParamsFromUi() {
  var numberOfDevices = parseInt(document.getElementById("devices").value);
  var deviceSendingIntervalInMinutes = parseFloat(
    document.getElementById("interval").value
  );
  var averageSizeOfMessageInKb = parseFloat(
    document.getElementById("messageSize").value
  );
  var hotStorageDurationInMonths = parseInt(
    document.getElementById("hotStorageDurationInMonths").value
  );
  var coolStorageDurationInMonths = parseInt(
    document.getElementById("coolStorageDurationInMonths").value
  );
  var archiveStorageDurationInMonths = parseInt(
    document.getElementById("archiveStorageDurationInMonths").value
  );
  var needs3DModel = document.querySelector(
    'input[name="needs3DModel"]:checked'
  ).value;
  let entityCount = 0;
  if (needs3DModel === "yes") {
    entityCount = parseInt(document.getElementById("entityCount").value);
  }
  var amountOfActiveEditors = parseInt(
    document.getElementById("monthlyEditors").value
  );

  var amountOfActiveViewers = parseInt(
    document.getElementById("monthlyViewers").value
  );

  var dashboardRefreshesPerHour = parseInt(
    document.getElementById("dashboardRefreshesPerHour").value
  );

  var dashboardActiveHoursPerDay = parseInt(
    document.getElementById("dashboardActiveHoursPerDay").value
  );

  var params = {
    numberOfDevices: numberOfDevices,
    deviceSendingIntervalInMinutes: deviceSendingIntervalInMinutes,
    averageSizeOfMessageInKb: averageSizeOfMessageInKb,
    hotStorageDurationInMonths: hotStorageDurationInMonths,
    coolStorageDurationInMonths: coolStorageDurationInMonths,
    archiveStorageDurationInMonths: archiveStorageDurationInMonths,
    needs3DModel: needs3DModel,
    entityCount: entityCount,
    amountOfActiveEditors: amountOfActiveEditors,
    amountOfActiveViewers: amountOfActiveViewers,
    dashboardRefreshesPerHour: dashboardRefreshesPerHour,
    dashboardActiveHoursPerDay: dashboardActiveHoursPerDay,
  };

  if (!(await validateInputs(params))) {
    console.log("Input validation failed.");
    return;
  }

  return params;
}

/**
 * Validate input parameters
 * @param {Params} params 
 * @returns 
 */
async function validateInputs(params) {
  // Validate inputs
  if (
    isNaN(params.numberOfDevices) ||
    isNaN(params.deviceSendingIntervalInMinutes) ||
    isNaN(params.averageSizeOfMessageInKb) ||
    params.numberOfDevices <= 0 ||
    params.deviceSendingIntervalInMinutes <= 0 ||
    params.averageSizeOfMessageInKb <= 0 ||
    isNaN(params.entityCount) ||
    isNaN(params.amountOfActiveEditors) ||
    isNaN(params.amountOfActiveViewers) ||
    params.amountOfActiveEditors < 0 ||
    params.amountOfActiveViewers < 0
  ) {
    document.getElementById("result").classList.remove("displayed");
    document.getElementById("result").innerHTML =
      "All inputs are required. Only positive values are allowed.";
    document.getElementById("result").classList.add("error");
    return false;
  }

  if (params.hotStorageDurationInMonths > params.coolStorageDurationInMonths) {
    document.getElementById("result").classList.remove("displayed");
    document.getElementById("result").innerHTML =
      "Hot storage duration cannot be longer than cool storage duration.";
    document.getElementById("result").classList.add("error");
    return false;
  }

  if (
    params.hotStorageDurationInMonths > params.archiveStorageDurationInMonths
  ) {
    document.getElementById("result").classList.remove("displayed");
    document.getElementById("result").innerHTML =
      "Hot storage duration cannot be longer than archive storage duration.";
    document.getElementById("result").classList.add("error");
    return false;
  }

  if (
    params.coolStorageDurationInMonths > params.archiveStorageDurationInMonths
  ) {
    document.getElementById("result").classList.remove("displayed");
    document.getElementById("result").innerHTML =
      "Cool storage duration cannot be longer than archive storage duration.";
    document.getElementById("result").classList.add("error");
    return false;
  }
  return true;
}

/**
 * Calculate AWS Costs
 * @param {*} params
 */
async function calculateAWSCosts(params) {
  var awsResultDataAcquisition = calculateAWSCostDataAcquisition(
    params.numberOfDevices,
    params.deviceSendingIntervalInMinutes,
    params.averageSizeOfMessageInKb
  );

  var awsResultDataProcessing = calculateAWSCostDataProcessing(
    params.numberOfDevices,
    params.deviceSendingIntervalInMinutes,
    params.averageSizeOfMessageInKb
  );

  var transferCostFromL2AWSToAWSHot = calculateTransferCostFromL2AWSToAWSHot(
    awsResultDataProcessing.dataSizeInGB
  );
  var transferCostFromL2AWSToAzureHot =
    calculateTransferCostFromL2AWSToAzureHot(
      awsResultDataProcessing.dataSizeInGB
    );

  var awsResultHotDynamoDB = calculateDynamoDBCost(
    awsResultDataProcessing.dataSizeInGB,
    awsResultDataProcessing.totalMessagesPerMonth,
    params.averageSizeOfMessageInKb,
    params.hotStorageDurationInMonths
  );

  var transferCostFromAWSHotToAWSCool =
    calculateTransferCostFromAWSHotToAWSCool(awsResultHotDynamoDB.dataSizeInGB);

  var transferCostFromAWSHotToAzureCool =
    calculateTransferCostFromAWSHotToAzureCool(
      awsResultHotDynamoDB.dataSizeInGB
    );

  var awsResultL3Cool = calculateS3InfrequentAccessCost(
    awsResultHotDynamoDB.dataSizeInGB,
    params.coolStorageDurationInMonths
  );

  var transferCostFromAWSCoolToAWSArchive =
    calculateTransferCostFromAWSCoolToAWSArchive(awsResultL3Cool.dataSizeInGB);
  var transferCostFromAWSCoolToAzureArchive =
    calculateTransferCostFromAWSCoolToAzureArchive(
      awsResultL3Cool.dataSizeInGB
    );

  var awsResultL3Archive = calculateS3GlacierDeepArchiveCost(
    awsResultL3Cool.dataSizeInGB,
    params.archiveStorageDurationInMonths
  );

  let awsResultLayer4 = null;
  if (params.needs3DModel === "yes") {
    awsResultLayer4 = calculateAWSIoTTwinMakerCost(
      params.entityCount,
      params.numberOfDevices,
      params.deviceSendingIntervalInMinutes,
      params.dashboardRefreshesPerHour,
      params.dashboardActiveHoursPerDay
    );
  } else if (params.needs3DModel === "no") {
    awsResultLayer4 = calculateAWSIoTTwinMakerCost(
      params.entityCount,
      params.numberOfDevices,
      params.deviceSendingIntervalInMinutes,
      params.dashboardRefreshesPerHour,
      params.dashboardActiveHoursPerDay
    );
  }

  var awsResultLayer5 = calculateAmazonManagedGrafanaCost(
    params.amountOfActiveEditors,
    params.amountOfActiveViewers
  );

  return {
    dataAquisition: awsResultDataAcquisition,
    dataProcessing: awsResultDataProcessing,
    resultHot: awsResultHotDynamoDB,
    resultL3Cool: awsResultL3Cool,
    resultL3Archive: awsResultL3Archive,
    resultL4: awsResultLayer4,
    resultL5: awsResultLayer5,
    transferCostL2ToHotAWS: transferCostFromL2AWSToAWSHot,
    transferCostL2ToHotAzure: transferCostFromL2AWSToAzureHot,
    transferCostHotToCoolAWS: transferCostFromAWSHotToAWSCool,
    transferCostHotToCoolAzure: transferCostFromAWSHotToAzureCool,
    transferCostCoolToArchiveAWS: transferCostFromAWSCoolToAWSArchive,
    transferCostCoolToArchiveAzure: transferCostFromAWSCoolToAzureArchive,
  };
}

/**
 * Calculate Azure Costs
 * @param {*} params
 */
async function calculateAzureCosts(params) {
  var azureResultDataAcquisition = calculateAzureCostDataAcquisition(
    params.numberOfDevices,
    params.deviceSendingIntervalInMinutes,
    params.averageSizeOfMessageInKb
  );

  var azureResultDataProcessing = calculateAzureCostDataProcessing(
    params.numberOfDevices,
    params.deviceSendingIntervalInMinutes,
    params.averageSizeOfMessageInKb
  );

  var transferCostFromL2AzureToAWSHot =
    calculateTransferCostFromL2AzureToAWSHot(
      azureResultDataProcessing.dataSizeInGB
    );

  var transferCostFromL2AzureToAzureHot =
    calculateTransferCostFromL2AzureToAzureHot(
      azureResultDataProcessing.dataSizeInGB
    );

  var azureResultHot = calculateCosmosDBCost(
    azureResultDataProcessing.dataSizeInGB,
    azureResultDataProcessing.totalMessagesPerMonth,
    params.averageSizeOfMessageInKb,
    params.hotStorageDurationInMonths
  );

  var transferCostFromAzureHotToAWSCool =
    calculateTransferCostsFromAzureHotToAWSCool(azureResultHot.dataSizeInGB);

  var transferCostFromAzureHotToAzureCool =
    calculateTransferCostFromAzureHotToAzureCool(azureResultHot.dataSizeInGB);

  var azureResultLayer3CoolBlobStorage = calculateAzureBlobStorageCost(
    azureResultHot.dataSizeInGB,
    params.coolStorageDurationInMonths
  );

  var transferCostFromAzureCoolToAWSArchive =
    calculateTransferCostFromAzureCoolToAWSArchive(
      azureResultLayer3CoolBlobStorage.dataSizeInGB
    );
  var transferCostFromAzureCoolToAzureArchive =
    calculateTransferCostFromAzureCoolToAzureArchive(
      azureResultLayer3CoolBlobStorage.dataSizeInGB
    );

  var azureResultLayer3Archive = calculateAzureBlobStorageArchiveCost(
    azureResultLayer3CoolBlobStorage.dataSizeInGB,
    params.archiveStorageDurationInMonths
  );

  let azureResultLayer4 = null;
  if (params.needs3DModel === "no") {
    azureResultLayer4 = calculateAzureDigitalTwinsCost(
      params.numberOfDevices,
      params.deviceSendingIntervalInMinutes,
      params.averageSizeOfMessageInKb,
      params.dashboardRefreshesPerHour,
      params.dashboardActiveHoursPerDay
    );
  }

  var azureResultLayer5 = calculateAzureManagedGrafanaCost(
    params.amountOfActiveEditors + params.amountOfActiveViewers
  );

  return {
    dataAquisition: azureResultDataAcquisition,
    dataProcessing: azureResultDataProcessing,
    resultHot: azureResultHot,
    resultL3Cool: azureResultLayer3CoolBlobStorage,
    resultL3Archive: azureResultLayer3Archive,
    resultL4: azureResultLayer4,
    resultL5: azureResultLayer5,
    transferCostL2ToHotAWS: transferCostFromL2AzureToAWSHot,
    transferCostL2ToHotAzure: transferCostFromL2AzureToAzureHot,
    transferCostHotToCoolAWS: transferCostFromAzureHotToAWSCool,
    transferCostHotToCoolAzure: transferCostFromAzureHotToAzureCool,
    transferCostCoolToArchiveAWS: transferCostFromAzureCoolToAWSArchive,
    transferCostCoolToArchiveAzure: transferCostFromAzureCoolToAzureArchive,
  };
}

/**
 * Main function to calculate costs and determine the cheapest path
 * @param {*} params
 *
 */
async function calculateCheapestCosts(params) {
  if (!pricing) {
    await loadPricingData();
  }

  let awsCosts = await calculateAWSCosts(params);
  let azureCosts = await calculateAzureCosts(params);

  let transferCosts = {
    L1_AWS_to_AWS_Hot: awsCosts.transferCostL2ToHotAWS,
    L1_AWS_to_Azure_Hot: awsCosts.transferCostL2ToHotAzure,
    L1_Azure_to_AWS_Hot: azureCosts.transferCostL2ToHotAWS,
    L1_Azure_to_Azure_Hot: azureCosts.transferCostL2ToHotAzure,
    AWS_Hot_to_AWS_Cool: awsCosts.transferCostHotToCoolAWS,
    AWS_Hot_to_Azure_Cool: awsCosts.transferCostHotToCoolAzure,
    Azure_Hot_to_AWS_Cool: azureCosts.transferCostHotToCoolAWS,
    Azure_Hot_to_Azure_Cool: azureCosts.transferCostHotToCoolAzure,
    AWS_Cool_to_AWS_Archive: awsCosts.transferCostCoolToArchiveAWS,
    AWS_Cool_to_Azure_Archive: awsCosts.transferCostCoolToArchiveAzure,
    Azure_Cool_to_AWS_Archive: azureCosts.transferCostCoolToArchiveAWS,
    Azure_Cool_to_Azure_Archive: azureCosts.transferCostCoolToArchiveAzure,
    L2_AWS_Archive_to_L3_AWS: 0,
    L2_AWS_Archive_to_L3_Azure: 0,
    L2_Azure_Archive_to_L3_AWS: 0,
    L2_Azure_Archive_to_L3_Azure: 0,
    L4_AWS_to_L5_AWS: 0,
    L4_Azure_to_L5_Azure: 0,
  };

  let graph = buildGraphForStorage(
    awsCosts.resultHot,
    azureCosts.resultHot,
    awsCosts.resultL3Cool,
    azureCosts.resultL3Cool,
    awsCosts.resultL3Archive,
    azureCosts.resultL3Archive,
    transferCosts
  );

  let cheapestStorage = findCheapestStoragePath(
    graph,
    ["AWS_Hot", "Azure_Hot"],
    ["AWS_Archive", "Azure_Archive"]
  );

  var awsCostsAfterLayer1 = awsCosts.dataAquisition.totalMonthlyCost;
  //+ awsCosts.dataProcessing.totalMonthlyCost;

  var azureCostsAfterLayer1 = azureCosts.dataAquisition.totalMonthlyCost;
  //+ azureCosts.dataProcessing.totalMonthlyCost;

  // get cheapest provider per layer
  let cheaperProviderForLayer1;
  let cheaperProviderForLayer3;
  switch (cheapestStorage.path[0]) {
    case "AWS_Hot":
      cheaperProviderForLayer1 =
        awsCostsAfterLayer1 + transferCosts.L1_AWS_to_AWS_Hot <
        azureCostsAfterLayer1 + transferCosts.L1_Azure_to_AWS_Hot
          ? "L1_AWS"
          : "L1_Azure";
      cheaperProviderForLayer3 = "L1_AWS";
      break;
    case "Azure_Hot":
      cheaperProviderForLayer1 =
        awsCostsAfterLayer1 + transferCosts.L1_AWS_to_Azure_Hot <
        azureCostsAfterLayer1 + transferCosts.L1_Azure_to_Azure_Hot
          ? "L3_AWS"
          : "L3_Azure";
      cheaperProviderForLayer3 = "L3_Azure";
      break;
    default:
      console.log("Storage Path incorrect!");
  }

  let cheaperProviderLayer5 =
    awsCosts.resultL5.totalMonthlyCost < azureCosts.resultL5.totalMonthlyCost
      ? "L5_AWS"
      : "L5_Azure";

  let cheapestPath = [];
  cheapestPath.push(cheaperProviderForLayer1);
  cheapestStorage.path
    .map((x) => "L2_" + x)
    .forEach((x) => cheapestPath.push(x));
  cheapestPath.push(cheaperProviderForLayer3);

  let cheaperProviderLayer4 = "";
  if (azureCosts.resultL4) {
    cheaperProviderLayer4 =
      azureCosts.resultL4.totalMonthlyCost < awsCosts.resultL4.totalMonthlyCost
        ? "L4_Azure"
        : "L4_AWS";
  } else {
    cheaperProviderLayer4 = "L4_AWS";
  }

  cheapestPath.push(cheaperProviderLayer4);
  cheapestPath.push(cheaperProviderLayer5);

  // build result
  let calculationResultObj = {};
  calculationResultObj.L1 = cheaperProviderForLayer1.split("_")[1];

  let calculationResultL2List = [];
  cheapestStorage.path.forEach((x) =>
    calculationResultL2List.push(x.split("_")[0])
  );

  calculationResultObj.L2 = {};
  calculationResultObj.L2.Hot = calculationResultL2List[0];
  calculationResultObj.L2.Cool = calculationResultL2List[1];
  calculationResultObj.L2.Archive = calculationResultL2List[2];

  calculationResultObj.L3 = cheaperProviderForLayer3.split("_")[1];
  calculationResultObj.L4 = cheaperProviderLayer4.split("_")[1];

  calculationResultObj.L5 = cheaperProviderLayer5.split("_")[1];

  return {
    calculationResult: calculationResultObj,
    awsCosts: awsCosts,
    azureCosts: azureCosts,
    cheapestPath: cheapestPath,
  };
}

/**
 * update HTML with results
 * @param {*} awsCosts
 * @param {*} azureCosts
 * @param {*} cheapestPath
 */
async function updateHtml(awsCosts, azureCosts, cheapestPath) {
  // build comparison object per layer
  var comparisonPerLayerObj = {
    layer1: {
      name: "Data Aquisition",
      aws: awsCosts.dataAquisition.totalMonthlyCost,
      azure: azureCosts.dataAquisition.totalMonthlyCost,
    },
    layer2a: {
      name: "Hot Storage",
      aws: awsCosts.resultHot.totalMonthlyCost,
      azure: azureCosts.resultHot.totalMonthlyCost,
    },
    layer2b: {
      name: "Cool Storage",
      aws: awsCosts.resultL3Cool.totalMonthlyCost,
      azure: azureCosts.resultL3Cool.totalMonthlyCost,
    },
    layer2c: {
      name: "Archive Storage",
      aws: awsCosts.resultL3Archive.totalMonthlyCost,
      azure: azureCosts.resultL3Archive.totalMonthlyCost,
    },
    layer3: {
      name: "Data Processing",
      aws: awsCosts.dataProcessing.totalMonthlyCost,
      azure: azureCosts.dataProcessing.totalMonthlyCost,
    },
    layer4: {
      name: "Twin Management",
      aws: awsCosts.resultL4 ? awsCosts.resultL4.totalMonthlyCost : 0,
      azure: azureCosts.resultL4 ? azureCosts.resultL4.totalMonthlyCost : 0,
    },
    layer5: {
      name: "Data Visualization",
      aws: awsCosts.resultL5.totalMonthlyCost,
      azure: azureCosts.resultL5.totalMonthlyCost,
    },
  };

  let formattedCheapestPath = cheapestPath
    .map((segment) => `<span class="path-segment">${segment}</span>`)
    .join('<span class="arrow">→</span>');

  let resultHTML = `
  <h2>Your most cost-efficient Digital Twin solution</h2>

  <div id="optimal-path">
    <div class="path-container">${formattedCheapestPath}</div>
  </div>

  <div class="cost-container">
    <!-- Layer 1 -->
    <div class="cost-card" onclick="flipCard(this)">
      <div class="card-front">
        <h3>Layer 1: ${
          comparisonPerLayerObj.layer1.name
        } <span class="info-icon">ℹ️</span></h3>
        <p><strong>AWS:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer1.aws.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
        <p><strong>Azure:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer1.azure.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
      </div>
      <div class="card-back">
        <h3>Layer 1: ${comparisonPerLayerObj.layer1.name} Info</h3>
        <p>This layer compares <a href="https://aws.amazon.com/de/iot-core/" target="_blank"><strong>AWS IoT Core</strong></a> vs. <a href="https://azure.microsoft.com/de-de/products/iot-hub" target="_blank"><strong>Azure IoT Hub</strong></a></p>
      </div>
    </div>

    <!-- Layer 2 Hot Storage -->
    <div class="cost-card" onclick="flipCard(this)">
      <div class="card-front">
        <h3>Layer 2: ${
          comparisonPerLayerObj.layer2a.name
        } <span class="info-icon">ℹ️</span></h3>
        <p><strong>AWS:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer2a.aws.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
        <p><strong>Azure:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer2a.azure.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
      </div>
      <div class="card-back">
        <h3>Layer 2: ${comparisonPerLayerObj.layer2a.name} Info</h3>
        <p>This layer compares the data storage for frequently accessed data in <a href="https://aws.amazon.com/de/dynamodb/" target="_blank"><strong>AWS DynamoDB</strong></a> vs. <a href="https://azure.microsoft.com/de-de/products/cosmos-db" target="_blank"><strong>Azure CosmosDB</strong></a> considering possible transfer costs.</p>
      </div>
    </div>

        <!-- Layer 2 Cool Storage -->
    <div class="cost-card" onclick="flipCard(this)">
      <div class="card-front">
        <h3>Layer 2: ${
          comparisonPerLayerObj.layer2b.name
        } <span class="info-icon">ℹ️</span></h3>
        <p><strong>AWS:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer2b.aws.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
        <p><strong>Azure:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer2b.azure.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
      </div>
      <div class="card-back">
        <h3>Layer 2: ${comparisonPerLayerObj.layer2b.name} Info</h3>
        <p>This layer compares the data storage for inrequently accessed data in <a href="https://aws.amazon.com/de/s3/" target="_blank"><strong>AWS S3-Infrequent Access</strong></a> vs. <a href="https://azure.microsoft.com/en-us/products/storage/blobs" target="_blank"><strong>Azure BlobStorage (Cool Tier)</strong></a> considering possible transfer costs.</p>
      </div>
    </div>

    <!-- Layer 2 Archive Storage -->
    <div class="cost-card" onclick="flipCard(this)">
      <div class="card-front">
        <h3>Layer 2: ${
          comparisonPerLayerObj.layer2c.name
        } <span class="info-icon">ℹ️</span></h3>
        <p><strong>AWS:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer2c.aws.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
        <p><strong>Azure:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer2c.azure.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
      </div>
      <div class="card-back">
        <h3>Layer 2: ${comparisonPerLayerObj.layer2c.name} Info</h3>
        <p>This layer compares the data storage for archived data in <a href="https://aws.amazon.com/de/s3/storage-classes/glacier/" target="_blank"><strong>Amazon S3-Glacier Deep Archive</strong></a> vs. <a href="https://azure.microsoft.com/en-us/products/storage/blobs" target="_blank"><strong>Azure Blob Storage (Archive Tier)</strong></a>.</p>
      </div>
    </div>

    <!-- Layer 3 -->
    <div class="cost-card" onclick="flipCard(this)">
      <div class="card-front">
        <h3>Layer 3: ${
          comparisonPerLayerObj.layer3.name
        } <span class="info-icon">ℹ️</span></h3>
        <p><strong>AWS:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer3.aws.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
        <p><strong>Azure:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer3.azure.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
      </div>
      <div class="card-back">
        <h3>Layer 3: ${comparisonPerLayerObj.layer3.name} Info</h3>
          <p>This layer compares <a href="https://aws.amazon.com/de/lambda/" target="_blank"><strong>AWS Lambda</strong></a> vs. <a href="https://azure.microsoft.com/en-us/products/functions" target="_blank"><strong>Azure Functions</strong></a></p>
      </div>
    </div>

    <div class="cost-card" onclick="flipCard(this)">
      <div class="card-front">
        <h3>Layer 4: ${
          comparisonPerLayerObj.layer4.name
        } <span class="info-icon">ℹ️</span></h3>
        ${
          comparisonPerLayerObj.layer4.aws
            ? `<p><strong>AWS:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer4.aws.toLocaleString(
                "en-US",
                { minimumFractionDigits: 2, maximumFractionDigits: 2 }
              )}</span></p>`
            : ""
        }
        ${
          comparisonPerLayerObj.layer4.azure
            ? `<p><strong>Azure:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer4.azure.toLocaleString(
                "en-US",
                { minimumFractionDigits: 2, maximumFractionDigits: 2 }
              )}</span></p>`
            : ""
        }
      </div>
      <div class="card-back">
        <h3>Layer 4: ${comparisonPerLayerObj.layer4.name} Info</h3>
        <p>This layer uses either <a href="https://aws.amazon.com/iot-twinmaker/" target="_blank"><strong>AWS IoT TwinMaker</strong></a> or <a href="https://azure.microsoft.com/en-us/products/digital-twins" target="_blank"><strong>Azure Digital Twins</strong></a> depending on if a 3D model of the Digital Twin is necessary.</p>
      </div>
    </div>


        <!-- Layer 5 -->
    <div class="cost-card" onclick="flipCard(this)">
      <div class="card-front">
        <h3>Layer 5: ${
          comparisonPerLayerObj.layer5.name
        } <span class="info-icon">ℹ️</span></h3>
        <p><strong>AWS:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer5.aws.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
        <p><strong>Azure:</strong> <span class="total-cost">$${comparisonPerLayerObj.layer5.azure.toLocaleString(
          "en-US",
          { minimumFractionDigits: 2, maximumFractionDigits: 2 }
        )}</span></p>
      </div>
      <div class="card-back">
        <h3>Layer 5: ${comparisonPerLayerObj.layer5.name} Info</h3>
        <p>This layer compares <a href="https://aws.amazon.com/de/grafana/" target="_blank"><strong>Amazon Managed Grafana</strong></a> vs. <a href="https://azure.microsoft.com/de-de/products/managed-grafana" target="_blank"><strong>Azure Managed Grafana</strong></a></p>
      </div>
    </div>

    
  </div>`;

  document.getElementById("result").classList.remove("error");
  document.getElementById("result").innerHTML = resultHTML;
}

/**
 * Calculate costs from UI input and update HTML
 * @returns
 */
async function calculateCheapestCostsFromUI() {
  var params = await readParamsFromUi();
  if (!params) {
    return;
  }

  var results = await calculateCheapestCosts(params);

  updateHtml(results.awsCosts, results.azureCosts, results.cheapestPath);

  // test

  var testResults = await calculateCheapestCostsFromApiCall(params);
  console.log("test results:", testResults);
}

/**
 * Validate parameters schema for API call
 * @param {Params} obj 
 * @returns 
 */
async function hasValidParamsSchema(obj) {
  var schema = {
    numberOfDevices: "number",
    deviceSendingIntervalInMinutes: "number",
    averageSizeOfMessageInKb: "number",
    hotStorageDurationInMonths: "number",
    coolStorageDurationInMonths: "number",
    archiveStorageDurationInMonths: "number",
    needs3DModel: "string",
    entityCount: "number",
    amountOfActiveEditors: "number",
    amountOfActiveViewers: "number",
    dashboardRefreshesPerHour: "number",
    dashboardActiveHoursPerDay: "number",
  };

  return Object.entries(schema).every(
    ([key, type]) => key in obj && typeof obj[key] === type
  );
}

/**
 * Calculate costs from API call with parameters
 * @param {Params} params
 */
async function calculateCheapestCostsFromApiCall(params) {

  let paramsAreValid = await hasValidParamsSchema(params);
  console.log("Params:", params);
  console.log("Params are valid:", paramsAreValid);
  if (!paramsAreValid) {
    throw new Error("Invalid parameters schema");
  }

  var results = await calculateCheapestCosts(params);

  console.log("calculation result:", results.calculationResult);
  return results.calculationResult;
}
