"use strict";

/**
 * This module contains functions to calculate the costs for data visualization services 
 * @param {*} amountOfActiveEditors 
 * @param {*} amountOfActiveViewers 
 * @returns 
 */
function calculateAmazonManagedGrafanaCost(
  amountOfActiveEditors,
  amountOfActiveViewers
) {
  const editorPrice = global.pricing.aws.awsManagedGrafana.editorPrice;
  const viewerPrice = global.pricing.aws.awsManagedGrafana.viewerPrice;

  const totalMonthlyCost =
    amountOfActiveEditors * editorPrice + amountOfActiveViewers * viewerPrice;

  return {
    provider: "AWS",
    totalMonthlyCost: totalMonthlyCost,
  };
}

/**
 * This function calculates the costs for Azure Managed Grafana
 * @param {*} amountOfMonthlyUsers 
 * @returns 
 */
function calculateAzureManagedGrafanaCost(amountOfMonthlyUsers) {
  const userPrice = global.pricing.azure.azureManagedGrafana.userPrice;
  const hourlyPrice = global.pricing.azure.azureManagedGrafana.hourlyPrice;
  const monthlyPrice = hourlyPrice * 730;

  const totalMonthlyCost = amountOfMonthlyUsers * userPrice + monthlyPrice;

  return {
    provider: "Azure",
    totalMonthlyCost: totalMonthlyCost,
  };
}

module.exports = {
  calculateAmazonManagedGrafanaCost,
  calculateAzureManagedGrafanaCost,
};