document.addEventListener('DOMContentLoaded', function () {
    var bookingDateInput = document.getElementById('bookingDate');
    var bookingTimeSelect = document.getElementById('bookingTime');
    var numberOfHoursInput = document.getElementById('bookingDuration'); // Changed from numberOfHours to bookingDuration
    var numberOfPeopleInput = document.getElementById('numberOfPeople');
    var costSummaryDiv = document.getElementById('costSummary');
    var paymentMessageDiv = document.getElementById('paymentMessage');
// top of file (near other globals)
window.unavailableSlotsForDay = [];  // [{start_time,end_time}, ...]

    // Add null checks to prevent errors
    if (!bookingDateInput || !bookingTimeSelect || !numberOfHoursInput) {
        console.log('Required booking form elements not found - skipping legacy booking_form.js setup');
        return;
    }

    // Set minimum date for booking input (today)
    var today = new Date().toISOString().split("T")[0];
    bookingDateInput.min = today;

    function checkDateAvailability(dateInput, timeSelect) {
    var selectedDate = dateInput.value;
    if (!selectedDate) {
        timeSelect.innerHTML = '<option value="">Select Time</option>';
        return;
    }

    fetch('/bookings/get_unavailable_slots?date=' + selectedDate)
        .then(response => response.json())
        .then(data => {
        console.log('Date availability check:', data);

        // store today’s blocks globally
        window.unavailableSlotsForDay = Array.isArray(data.unavailable_slots) ? data.unavailable_slots : [];

        timeSelect.disabled = false;
        populateTimeOptions(dateInput, timeSelect);
        })
        .catch(err => {
        console.error('Error checking date availability:', err);
        window.unavailableSlotsForDay = [];
        timeSelect.disabled = false;
        populateTimeOptions(dateInput, timeSelect);
        });
    }

function updateHoursForSelectedTime(timeSelect, hoursEl) {
  console.log('[updateHours] start for time:', timeSelect.value);

  const isSelect = hoursEl && hoursEl.tagName === 'SELECT';
  const isNumberInput = hoursEl && hoursEl.tagName === 'INPUT' && hoursEl.type === 'number';

  // reset UI
  if (isSelect) {
    hoursEl.innerHTML = '<option value="">Select Hours</option>';
  } else if (isNumberInput) {
    hoursEl.value = '';
    hoursEl.removeAttribute('max');
    hoursEl.setAttribute('min', '1');
  }

  const startStr = timeSelect.value;
  if (!startStr) {
    if (isSelect) hoursEl.disabled = true;
    if (isNumberInput) { hoursEl.disabled = true; }
    console.log('[updateHours] no start time -> disabled');
    return;
  }

  const startHour = parseInt(startStr.split(':')[0], 10);

  // build blocked hours
  const blockedHours = new Set();
  (window.unavailableSlotsForDay || []).forEach(slot => {
    let s = parseInt(slot.start_time.split(':')[0], 10);
    let e = parseInt(slot.end_time.split(':')[0], 10);
    if (e === 0) e = 24;
    for (let h = s; h < e; h++) blockedHours.add(h);
  });
  console.log('[updateHours] blocked hours:', [...blockedHours]);

  if (blockedHours.has(startHour)) {
    console.log('[updateHours] start hour is blocked -> none');
    if (isSelect) {
      hoursEl.innerHTML = '<option value="">No hours available</option>';
    }
    hoursEl.disabled = true;
    return;
  }

  const BUSINESS_END_HOUR = 24;

  // first blocked hour after start
  let firstBlocked = BUSINESS_END_HOUR;
  for (let h = startHour + 1; h <= 24; h++) {
    if (blockedHours.has(h)) { firstBlocked = h; break; }
  }

  const maxHours = Math.min(firstBlocked, BUSINESS_END_HOUR) - startHour;
  console.log('[updateHours] firstBlocked:', firstBlocked, 'maxHours:', maxHours);

  if (maxHours < 1) {
    if (isSelect) {
      hoursEl.innerHTML = '<option value="">No hours available</option>';
    }
    hoursEl.disabled = true;
    return;
  }

  if (isSelect) {
    for (let d = 1; d <= maxHours; d++) {
      const opt = document.createElement('option');
      opt.value = String(d);
      opt.textContent = d + (d === 1 ? ' hour' : ' hours');
      hoursEl.appendChild(opt);
    }
    hoursEl.disabled = false;
    hoursEl.value = ''; // force explicit pick
  } else if (isNumberInput) {
    hoursEl.setAttribute('min', '1');
    hoursEl.setAttribute('max', String(maxHours));
    hoursEl.step = '1';
    hoursEl.disabled = false;
    // Optional: clamp an already-entered value
    if (hoursEl.value) {
      const v = Math.max(1, Math.min(maxHours, parseInt(hoursEl.value, 10)));
      hoursEl.value = String(v);
    }
  }

  console.log('[updateHours] options/max built 1..' + maxHours);
}


function populateTimeOptions(dateInput, timeSelect, defaultTime = null) {
  // Reset time select
  timeSelect.innerHTML = '<option value="">Select Time</option>';

  const selectedDate = dateInput.value;
  if (!selectedDate) return;

  // Detect what kind of control bookingDuration is
  const hoursEl = numberOfHoursInput;
  const isHoursSelect = hoursEl && hoursEl.tagName === 'SELECT';
  const isHoursNumber = hoursEl && hoursEl.tagName === 'INPUT' && hoursEl.type === 'number';

  // Reset hours control ONCE (not inside the hour loop!)
  if (hoursEl) {
    if (isHoursSelect) {
      hoursEl.innerHTML = '<option value="">Select Hours</option>';
      hoursEl.disabled = true;
    } else if (isHoursNumber) {
      hoursEl.value = '';
      hoursEl.removeAttribute('max');
      hoursEl.setAttribute('min', '1');
      hoursEl.disabled = true;
    }
  }

  // If defaultTime provided, extract its hour
  const defaultHour = defaultTime ? parseInt(defaultTime.split(':')[0], 10) : null;

  // Figure out “now” rules (don’t show times in the past for today)
  const now = new Date();
  const todayStr = now.toISOString().slice(0, 10);
  const currentHour = (selectedDate === todayStr) ? now.getHours() : -1;

  fetch('/bookings/get_unavailable_slots?date=' + selectedDate)
    .then(res => res.json())
    .then(data => {
      console.log('unavailable_slots:', data.unavailable_slots);

      // Build disabled hours array for the day
      window.globalDisabledHours = [];
      if (Array.isArray(data.unavailable_slots)) {
        data.unavailable_slots.forEach(slot => {
          let s = parseInt(slot.start_time.split(':')[0], 10);
          let e = parseInt(slot.end_time.split(':')[0], 10);
          if (e === 0) e = 24; // treat midnight as end-of-day
          for (let h = s; h < e; h++) {
            if (defaultHour !== null && h === defaultHour) continue; // allow default time
            if (!window.globalDisabledHours.includes(h)) window.globalDisabledHours.push(h);
          }
        });
      }

      // Populate time options (skip past times for today, and blocked hours)
      for (let hour = 0; hour < 24; hour++) {
        if (hour <= currentHour) continue;
        if (window.globalDisabledHours.indexOf(hour) !== -1) continue;

        const hourStr = String(hour).padStart(2, '0') + ':00';
        const opt = document.createElement('option');
        opt.value = hourStr;
        opt.text = hourStr;
        timeSelect.appendChild(opt);
      }

      // Apply default time after options are built
      if (defaultTime) {
        console.log('Setting default time to:', defaultTime);
        timeSelect.value = defaultTime;
      }

      console.log('[populate] built time options; current value =', timeSelect.value);

      // Now that time options exist, build the hours choices/max
      updateHoursForSelectedTime(timeSelect, hoursEl);
    })
    .catch(err => {
      console.error('Failed to load unavailable slots:', err);

      // Fallback: just show future hours for today
      for (let hour = 0; hour < 24; hour++) {
        if (hour <= currentHour) continue;
        const hourStr = String(hour).padStart(2, '0') + ':00';
        const opt = document.createElement('option');
        opt.value = hourStr;
        opt.text = hourStr;
        timeSelect.appendChild(opt);
      }

      if (defaultTime) timeSelect.value = defaultTime;

      // Even on error, try to build hour limits from empty blocks
      window.globalDisabledHours = [];
      updateHoursForSelectedTime(timeSelect, hoursEl);
    });
}

    
  
    // Helper function to update the cost summary
    function updateCostSummary(dateInput, timeSelect, hoursInput, peopleInput, costSummaryDiv) {
        // Skip if costSummaryDiv doesn't exist (pricing summary was removed)
        if (!costSummaryDiv) {
            console.log('Cost summary div not found - skipping pricing update');
            return;
        }

        console.log('called')
        var hours = parseFloat(hoursInput.value) || 0;
        var people = parseFloat(peopleInput.value) || 0;
        var rate = 2;
        var totalCost = hours * people * rate;
        var deposit = totalCost * 0.30;
        var remainder = totalCost - deposit;
        var availableMessage = "";
        var selectedDate = dateInput.value;
        if (selectedDate && timeSelect.value) {
            var selectedHour = parseInt(timeSelect.value.split(":")[0]);
            // Check if the entered hours exceed the remaining hours in the day
            var maxPossibleHours = 24 - selectedHour;
            if (hours > maxPossibleHours) {
                availableMessage = "You can book for a maximum of " + maxPossibleHours + " hour(s) today (starting from " + timeSelect.value + ").";
            } else {
                // Check for the next disabled hours from the selected hour
                var candidateHours = window.globalDisabledHours.filter(h => h > selectedHour);
                if (candidateHours.length > 0) {
                    var earliestDisabled = Math.min(...candidateHours);
                    if (selectedHour + hours > earliestDisabled) {
                        var maxHours = earliestDisabled - selectedHour;
                        availableMessage = "Available only for " + maxHours + " hour(s) until " + formatHour(earliestDisabled) + ".";
                        var nextAvailable = earliestDisabled;
                        while (window.globalDisabledHours.indexOf(nextAvailable) !== -1 && nextAvailable < 24) {
                            nextAvailable++;
                        }
                        if (nextAvailable < 24) {
                            availableMessage += " Then available from " + formatHour(nextAvailable) + ".";
                        }
                    }
                }
            }
        }
        console.log('availableMessage',availableMessage);
        if (availableMessage !== "") {
            costSummaryDiv.innerText = availableMessage;
            costSummaryDiv.style.color = 'red';
            console.log('costSummaryDiv',costSummaryDiv);
        } else if (hours > 0 && people > 0) {
            costSummaryDiv.innerText =
                "Total: €" + totalCost.toFixed(2) +
                " (Deposit €" + deposit.toFixed(2) +
                ", Pay at Venue €" + remainder.toFixed(2) + ")";
                costSummaryDiv.style.color = 'grey';
        } else {
            costSummaryDiv.innerText = "";
        }
    }
    

    function formatHour(hour) {
        var displayHour = hour % 12 === 0 ? 12 : hour % 12;
        var ampm = hour < 12 ? "AM" : "PM";
        return displayHour + ":00 " + ampm;
    }
    if (bookingDateInput) {
        bookingDateInput.addEventListener('change', function () {
            checkDateAvailability(bookingDateInput, bookingTimeSelect);
            if (paymentMessageDiv) {
                paymentMessageDiv.innerText = "Note: Payment is made online (30% deposit). The remainder is due at the venue.";
            }
            updateCostSummary(bookingDateInput, bookingTimeSelect, numberOfHoursInput, numberOfPeopleInput, costSummaryDiv);
        });
    }

    if (numberOfHoursInput) {
        numberOfHoursInput.addEventListener('change', function () { // Changed from 'input' to 'change' for dropdown
            updateCostSummary(bookingDateInput, bookingTimeSelect, numberOfHoursInput, numberOfPeopleInput, costSummaryDiv);
        });
    }

        if (bookingTimeSelect) {
        bookingTimeSelect.addEventListener('change', function () {
            console.log('[change] time picked:', bookingTimeSelect.value);
            updateHoursForSelectedTime(bookingTimeSelect, numberOfHoursInput);
            updateCostSummary(bookingDateInput, bookingTimeSelect, numberOfHoursInput, numberOfPeopleInput, costSummaryDiv);
        });
        }
    
    if (numberOfPeopleInput) {
        numberOfPeopleInput.addEventListener('input', function () {
            updateCostSummary(bookingDateInput, bookingTimeSelect, numberOfHoursInput, numberOfPeopleInput, costSummaryDiv);
        });
    }
});
