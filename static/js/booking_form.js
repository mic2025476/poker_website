document.addEventListener('DOMContentLoaded', function () {
    var bookingDateInput = document.getElementById('bookingDate');
    var bookingTimeSelect = document.getElementById('bookingTime');
    var numberOfHoursInput = document.getElementById('bookingDuration'); // Changed from numberOfHours to bookingDuration
    var numberOfPeopleInput = document.getElementById('numberOfPeople');
    var costSummaryDiv = document.getElementById('costSummary');
    var paymentMessageDiv = document.getElementById('paymentMessage');
    
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
                
                // Always proceed with normal time population (let the smart booking logic handle conflicts)
                timeSelect.disabled = false;
                populateTimeOptions(dateInput, timeSelect);
            })
            .catch(err => {
                console.error('Error checking date availability:', err);
                // On error, proceed with normal time population
                timeSelect.disabled = false;
                populateTimeOptions(dateInput, timeSelect);
            });
    }

    function populateTimeOptions(dateInput, timeSelect, defaultTime = null) {
        timeSelect.innerHTML = '<option value="">Select Time</option>';
        var selectedDate = dateInput.value;
        if (!selectedDate) return;
    
        // If defaultTime is provided, get its hour value (as a number)
        let defaultHour = defaultTime ? parseInt(defaultTime.split(":")[0]) : null;
    
        // Check if selected date is today's date; if so, get the current hour (0-23)
        var now = new Date();
        var todayStr = now.toISOString().slice(0, 10); // format "YYYY-MM-DD"
        var currentHour = (selectedDate === todayStr) ? now.getHours() : -1; 
        console.log('currentHour',currentHour);
        console.log('todayStr',todayStr);
        fetch('/bookings/get_unavailable_slots?date=' + selectedDate)
            .then(response => response.json())
            .then(data => {
                console.log('response.json()1113333', data.unavailable_slots);
                console.log('11111');
                window.globalDisabledHours = [];
                if (data.unavailable_slots && data.unavailable_slots.length > 0) {
                    console.log('svdsvsdv');
                    data.unavailable_slots.forEach(slot => {
                        let startHour = parseInt(slot.start_time.split(":")[0]);
                        let endHour = parseInt(slot.end_time.split(":")[0]);
                        if (endHour === 0) endHour = 24;
                        console.log('startHour',startHour);
                        console.log('endHour',endHour);
                        for (let h = startHour; h < endHour; h++) {
                            // Skip pushing the default hour if provided
                            if (defaultHour !== null && h === defaultHour) continue;
                            if (!window.globalDisabledHours.includes(h)) {
                                window.globalDisabledHours.push(h);
                            }
                        }
                    });
                }
                for (var hour = 0; hour < 24; hour++) {
                    // If today, skip time options that are in the past (i.e., less than or equal to the current hour)
                    if (hour <= currentHour) continue;
                    // Even if the default hour is in globalDisabledHours, it was skipped so it won't be disabled.
                    if (window.globalDisabledHours.indexOf(hour) !== -1) continue;
                    var option = document.createElement('option');
                    var hourStr = hour.toString().padStart(2, '0') + ":00";
                    option.value = hourStr;
                    option.text = hourStr;
                    console.log('option',option);
                    timeSelect.appendChild(option);
                }
                // If a default time was provided, set it after options are populated
                if (defaultTime) {
                    console.log('Setting default time to:', defaultTime);
                    timeSelect.value = defaultTime;
                }
            })
            .catch(err => {
                console.error(err);
                for (var hour = 0; hour < 24; hour++) {
                    // If today, skip past times
                    if (hour <= currentHour) continue;
                    var option = document.createElement('option');
                    var hourStr = hour.toString().padStart(2, '0') + ":00";
                    var displayHour = hour % 12 === 0 ? 12 : hour % 12;
                    var ampm = hour < 12 ? "AM" : "PM";
                    option.value = hourStr;
                    option.text = displayHour + ":00 " + ampm;
                    timeSelect.appendChild(option);
                }
                if (defaultTime) {
                    timeSelect.value = defaultTime;
                }
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
        bookingTimeSelect.addEventListener('change', function () { // Changed from 'input' to 'change' for dropdown
            updateCostSummary(bookingDateInput, bookingTimeSelect, numberOfHoursInput, numberOfPeopleInput, costSummaryDiv);
        });
    }
    
    if (numberOfPeopleInput) {
        numberOfPeopleInput.addEventListener('input', function () {
            updateCostSummary(bookingDateInput, bookingTimeSelect, numberOfHoursInput, numberOfPeopleInput, costSummaryDiv);
        });
    }
});
