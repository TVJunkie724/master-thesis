"use strict";

function updateSliderValue(slider) {
  let value = slider.value;
  let output = slider.nextElementSibling;
  if (output) {
    output.textContent = value;
  }
}

// Initialize Bootstrap Tooltips, Sliders, and Default State
document.addEventListener("DOMContentLoaded", function () {
  // Initialize Bootstrap Tooltips
  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
  var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl)
  })

  // Initialize Sliders
  const sliders = document.querySelectorAll('input[type="range"]');
  sliders.forEach(slider => {
    updateSliderValue(slider);
  });

  // Initialize Entity Input Visibility
  toggleEntityInput();
  toggleEventsInput();
  toggleOrchestrationInput();

  // Add event listeners for toggles
  document.getElementById("useEventChecking").addEventListener("change", toggleEventsInput);
  document.getElementById("triggerNotificationWorkflow").addEventListener("change", toggleOrchestrationInput);

  // Select Preset 1 by default
  const firstPreset = document.querySelector('.preset-btn');
  if (firstPreset) {
    firstPreset.click();
  }

  // Add event listeners to clear preset highlight on manual input
  const inputs = document.querySelectorAll('input, select');
  inputs.forEach(input => {
    input.addEventListener('input', () => {
      document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.classList.remove('active', 'btn-primary');
        btn.classList.add('btn-outline-primary');
      });
    });
  });
});

function fillScenario(
  btnElement,
  devices,
  interval,
  messageSize,
  hotStorageMonths,
  coolStorageMonths,
  archiveStorageMonths,
  needs3DModel,
  numberOfEntities,
  average3DModelSizeInMB,
  amountOfActiveEditors,
  amountOfActiveViewers,
  dashboardRefreshesPerHour,
  dashboardActiveHoursPerDay,
  useEventChecking,
  eventsPerMessage,
  returnFeedbackToDevice,
  triggerNotificationWorkflow,
  orchestrationActionsPerMessage,
  integrateErrorHandling,
  apiCallsPerDashboardRefresh
) {
  document.getElementById("devices").value = devices;
  document.getElementById("interval").value = interval;
  document.getElementById("messageSize").value = messageSize;
  document.getElementById("hotStorageDurationInMonths").value = hotStorageMonths;
  document.getElementById("coolStorageDurationInMonths").value = coolStorageMonths;
  document.getElementById("archiveStorageDurationInMonths").value = archiveStorageMonths;

  if (needs3DModel === "yes") {
    document.getElementById("modelYes").checked = true;
    document.getElementById("modelNo").checked = false;
    document.getElementById("entityInputContainer").classList.add("visible");
  } else {
    document.getElementById("modelYes").checked = false;
    document.getElementById("modelNo").checked = true;
    document.getElementById("entityInputContainer").classList.remove("visible");
  }

  document.getElementById("monthlyEditors").value = amountOfActiveEditors;
  document.getElementById("monthlyViewers").value = amountOfActiveViewers;
  document.getElementById("entityCount").value = numberOfEntities;
  document.getElementById("average3DModelSizeInMB").value = average3DModelSizeInMB;
  document.getElementById("dashboardRefreshesPerHour").value = dashboardRefreshesPerHour;
  document.getElementById("dashboardActiveHoursPerDay").value = dashboardActiveHoursPerDay;

  // New Fields
  document.getElementById("useEventChecking").checked = useEventChecking;
  document.getElementById("eventsPerMessage").value = eventsPerMessage;
  document.getElementById("returnFeedbackToDevice").checked = returnFeedbackToDevice;
  document.getElementById("triggerNotificationWorkflow").checked = triggerNotificationWorkflow;
  document.getElementById("orchestrationActionsPerMessage").value = orchestrationActionsPerMessage;
  (document.getElementById("integrateErrorHandling") || {}).checked = integrateErrorHandling;
  document.getElementById("apiCallsPerDashboardRefresh").value = apiCallsPerDashboardRefresh;

  // Update slider UI
  updateSliderValue(document.getElementById("hotStorageDurationInMonths"));
  updateSliderValue(document.getElementById("coolStorageDurationInMonths"));
  updateSliderValue(document.getElementById("archiveStorageDurationInMonths"));
  updateSliderValue(document.getElementById("dashboardActiveHoursPerDay"));

  // Highlight active preset button
  document.querySelectorAll('.preset-btn').forEach(btn => btn.classList.remove('active', 'btn-primary'));
  document.querySelectorAll('.preset-btn').forEach(btn => btn.classList.add('btn-outline-primary'));

  if (btnElement) {
    btnElement.classList.remove('btn-outline-primary');
    btnElement.classList.add('active', 'btn-primary');
  }

  // Re-run toggleEntityInput to ensure UI state matches
  toggleEntityInput();
  toggleEventsInput();
  toggleOrchestrationInput();
}

function flipCard(card) {
  // Toggle the flipped class on the container
  // The onclick is on the .cost-card-container div
  if (card.classList.contains('cost-card-container')) {
    card.classList.toggle("flipped");
  } else {
    // Fallback if called on child
    card.closest('.cost-card-container').classList.toggle("flipped");
  }
}

// Ensure entity input toggles based on selection
function toggleEntityInput() {
  const needs3DModelInput = document.querySelector('input[name="needs3DModel"]:checked');
  if (!needs3DModelInput) return;

  const needs3DModel = needs3DModelInput.value;
  const entityInputContainer = document.getElementById("entityInputContainer");

  // Show input if "Yes" is selected, hide if "No" is selected
  if (needs3DModel === "yes") {
    entityInputContainer.classList.remove("d-none");
    entityInputContainer.classList.add("d-block");

    // Enforce min value of 1 if currently 0 or empty
    const entityCountInput = document.getElementById("entityCount");
    if (entityCountInput && (!entityCountInput.value || parseInt(entityCountInput.value) < 1)) {
      entityCountInput.value = 1;
    }
  } else {
    entityInputContainer.classList.remove("d-block");
    entityInputContainer.classList.add("d-none");
  }
}

function toggleEventsInput() {
  const checkbox = document.getElementById("useEventChecking");
  const container = document.getElementById("eventsPerMessageContainer");
  if (checkbox && container) {
    if (checkbox.checked) {
      container.classList.remove("d-none");
      container.classList.add("d-block");
    } else {
      container.classList.remove("d-block");
      container.classList.add("d-none");
    }
  }
}

function toggleOrchestrationInput() {
  const checkbox = document.getElementById("triggerNotificationWorkflow");
  const container = document.getElementById("orchestrationActionsPerMessageContainer");
  if (checkbox && container) {
    if (checkbox.checked) {
      container.classList.remove("d-none");
      container.classList.add("d-block");
    } else {
      container.classList.remove("d-block");
      container.classList.add("d-none");
    }
  }
}
