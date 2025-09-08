"use strict";

function calculateNumberOfQueriesToLayer4FromDashboard(
  dashboardRefreshesPerHour, 
  dashboardActiveHoursPerDay
) {
  const daysInMonth = 30; 
  return dashboardActiveHoursPerDay * dashboardRefreshesPerHour * daysInMonth; 
}

function calculateAWSIoTTwinMakerCost(
  entityCount,
  numberOfDevices,
  deviceSendingIntervalInMinutes, 
  dashboardRefreshesPerHour, 
  dashboardActiveHoursPerDay
) {
  const unifiedDataAccessAPICallsPrice =
    pricing.aws.iotTwinMaker.unifiedDataAccessAPICallsPrice;
  const entityPrice = pricing.aws.iotTwinMaker.entityPrice;
  const queryPrice = pricing.aws.iotTwinMaker.queryPrice;

  let totalMessagesPerMonth = Math.ceil(
    numberOfDevices * (1 / deviceSendingIntervalInMinutes) * 60 * 24 * 30
  );

  const numberOfQueries = calculateNumberOfQueriesToLayer4FromDashboard(dashboardRefreshesPerHour, dashboardActiveHoursPerDay); 

  const totalMonthlyCost =
    entityCount * entityPrice +
    totalMessagesPerMonth * unifiedDataAccessAPICallsPrice +
    numberOfQueries * queryPrice;
  return {
    provider: "AWS",
    totalMonthlyCost: totalMonthlyCost,
  };
}

function calculateAzureDigitalTwinsCost(
  numberOfDevices,
  deviceSendingIntervalInMinutes,
  messageSizeInKB, 
  dashboardRefreshesPerHour, 
  dashboardActiveHoursPerDay
) {
  const messagePrice = pricing.azure.azureDigitalTwins.messagePrice;
  const operationPrice = pricing.azure.azureDigitalTwins.operationPrice;
  const queryPrice = pricing.azure.azureDigitalTwins.queryPrice;

  let totalMessagesPerMonth = Math.ceil(
    numberOfDevices * (1 / deviceSendingIntervalInMinutes) * 60 * 24 * 30
  );

  const queryUnitTiers = pricing.azure.azureDigitalTwins.queryUnitTiers; 

  const queryUnits = queryUnitTiers.find(t => numberOfDevices >= t.lower && numberOfDevices <= (t.upper || Number.MAX_VALUE)).value;

  const numberOfQueries = calculateNumberOfQueriesToLayer4FromDashboard(dashboardRefreshesPerHour, dashboardActiveHoursPerDay); 
  const totalMonthlyCost =
    totalMessagesPerMonth * operationPrice + // assumption message is compressed before updating DT, otherwise costs double linearly or even more
    Math.ceil(messageSizeInKB) * numberOfQueries * operationPrice + queryUnits * queryPrice * numberOfQueries;
    //(numberOfDevices / 30) * 60 * 24 * 30 * queryPrice;
  return {
    provider: "Azure",
    totalMonthlyCost: totalMonthlyCost,
  };
}
