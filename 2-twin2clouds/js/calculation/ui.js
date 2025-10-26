"use strict";

function updateSliderStyle(slider) {
  let min = slider.min;
  let max = slider.max;
  let value = slider.value;

  // Calculate percentage of slider filled
  let percentage = ((value - min) / (max - min)) * 100;

  // Apply gradient effect: blue up to slider position, gray for the rest
  slider.style.background = `linear-gradient(90deg, #007bff ${percentage}%, #ddd ${percentage}%)`;
  let output = slider.nextElementSibling;
  output.textContent = value;
  output.style.left = `calc(${percentage}% - 12px)`;
}

// Ensure the slider starts with the correct style on page load
document.addEventListener("DOMContentLoaded", function () {
  const hotSlider = document.getElementById("hotStorageDurationInMonths");
  const coolSlider = document.getElementById("coolStorageDurationInMonths");
  const archiveSlider = document.getElementById(
    "archiveStorageDurationInMonths"
  );
  const dashboardActiveHoursPerDaySlider = document.getElementById("dashboardActiveHoursPerDay");
  updateSliderStyle(hotSlider);
  updateSliderStyle(coolSlider);
  updateSliderStyle(archiveSlider);
  updateSliderStyle(dashboardActiveHoursPerDaySlider); 
});

function fillScenario(
  devices,
  interval,
  messageSize,
  hotStorageMonths,
  coolStorageMonths,
  archiveStorageMonths,
  needs3DModel,
  numberOfEntities,
  amountOfActiveEditors,
  amountOfActiveViewers, 
  dashboardRefreshesPerHour, 
  dashboardActiveHoursPerDay
) {
  document.getElementById("devices").value = devices;
  document.getElementById("interval").value = interval;
  document.getElementById("messageSize").value = messageSize;
  document.getElementById("hotStorageDurationInMonths").value =
    hotStorageMonths;
  document.getElementById("coolStorageDurationInMonths").value =
    coolStorageMonths;
  document.getElementById("archiveStorageDurationInMonths").value =
    archiveStorageMonths;
  if (needs3DModel === "yes") {
    document.getElementById("modelYes").checked = true;
    document.getElementById("modelNo").checked = false;
    entityInputContainer.classList.add("visible");
  } else {
    document.getElementById("modelYes").checked = false;
    document.getElementById("modelNo").checked = true;
    entityInputContainer.classList.remove("visible");
  }
  document.getElementById("monthlyEditors").value = amountOfActiveEditors;
  document.getElementById("monthlyViewers").value = amountOfActiveViewers;

  document.getElementById("entityCount").value = numberOfEntities;

  document.getElementById("dashboardRefreshesPerHour").value = dashboardRefreshesPerHour; 
  document.getElementById("dashboardActiveHoursPerDay").value = dashboardActiveHoursPerDay; 


  // Update slider UI
  updateSliderStyle(document.getElementById("hotStorageDurationInMonths"));
  updateSliderStyle(document.getElementById("coolStorageDurationInMonths"));
  updateSliderStyle(document.getElementById("archiveStorageDurationInMonths"));
  updateSliderStyle(document.getElementById("dashboardActiveHoursPerDay"));
}

function flipCard(card) {
  card.classList.toggle("flipped");
}

// Ensure entity input toggles based on selection
function toggleEntityInput() {
  const needs3DModel = document.querySelector(
    'input[name="needs3DModel"]:checked'
  ).value;
  const entityInputContainer = document.getElementById("entityInputContainer");

  // Show input if "Yes" is selected, hide if "No" is selected
  if (needs3DModel === "yes") {
    entityInputContainer.classList.add("visible");
  } else {
    entityInputContainer.classList.remove("visible");
  }
}

// Ensure the correct state on page load
document.addEventListener("DOMContentLoaded", toggleEntityInput);
