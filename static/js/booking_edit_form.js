document.addEventListener('DOMContentLoaded', function () {
    // Helper function to populate time options based on the selected date,
    // with an optional defaultTime parameter.
    function populateTimeOptions(dateInput, timeSelect, defaultTime = null) {
        timeSelect.innerHTML = '<option value="">Select Time</option>';
        var selectedDate = dateInput.value;
        if (!selectedDate) return;

        // If defaultTime is provided, get its hour value (as a number)
        let defaultHour = defaultTime ? parseInt(defaultTime.split(":")[0]) : null;

        fetch('/bookings/get_unavailable_slots?date=' + selectedDate)
            .then(response => response.json())
            .then(data => {
                console.log('response.json()2222', data);
                window.globalDisabledHours = [];
                if (data.unavailable_slots && data.unavailable_slots.length > 0) {
                    data.unavailable_slots.forEach(slot => {
                        let startHour = parseInt(slot.start_time.split(":")[0]);
                        let endHour = parseInt(slot.end_time.split(":")[0]);
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
                    // Even if the default hour is in globalDisabledHours,
                    // it was skipped so it won't be disabled.
                    if (window.globalDisabledHours.indexOf(hour) !== -1) continue;
                    var option = document.createElement('option');
                    var hourStr = hour.toString().padStart(2, '0') + ":00";
                    option.value = hourStr;
                    option.text = hourStr;
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
            var candidateHours = window.globalDisabledHours.filter(h => h > selectedHour);
            console.log('candidateHours',candidateHours);
            if (candidateHours.length > 0) {
                var earliestDisabled = Math.min(...candidateHours);
                if (selectedHour + hours > earliestDisabled) {
                    var maxHours = earliestDisabled - selectedHour;
                    console.log('maxHours',maxHours);
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
        if (availableMessage !== "") {
            costSummaryDiv.innerText = availableMessage;
        } else if (hours > 0 && people > 0) {
            costSummaryDiv.innerText =
                "Total: €" + totalCost.toFixed(2) +
                " (Deposit €" + deposit.toFixed(2) +
                ", Pay at Venue €" + remainder.toFixed(2) + ")";
        } else {
            costSummaryDiv.innerText = "";
        }
    }
  
    // Helper function to format hour for display
    function formatHour(hour) {
        var displayHour = hour % 12 === 0 ? 12 : hour % 12;
        var ampm = hour < 12 ? "AM" : "PM";
        return displayHour + ":00 " + ampm;
    }
  
    // --- Event Delegation for Edit Booking Button ---
    document.addEventListener('click', function (e) {
        if (e.target.closest('.edit-booking')) {
            console.log('reached');
            e.preventDefault();
            const editBtn = e.target.closest('.edit-booking');
            const bookingId = editBtn.getAttribute('data-booking-id');
            const bookingCard = document.querySelector(`.booking-card[data-booking-id="${bookingId}"]`);
            const bookingDateTime = bookingCard.getAttribute('data-booking-date');
            const bookingDate = bookingDateTime.split(' ')[0];
            const bookingTime = bookingDateTime.split(' ')[1];
            const totalPeople = bookingCard.getAttribute('data-total-people');
            const hours = bookingCard.getAttribute('data-hours');
            const drinksCSV = bookingCard.getAttribute('data-drinks');
            const drinksArray = drinksCSV ? drinksCSV.split(',') : [];
  
            // Get edit form elements
            var editBookingDateInput = document.getElementById('editBookingDate');
            var editBookingTimeSelect = document.getElementById('editBookingTime');
            var editNumberOfPeopleInput = document.getElementById('editNumberOfPeople');
            var editNumberOfHoursInput = document.getElementById('editNumberOfHours');
            var costSummaryDiv = document.getElementById('editCostSummary');
  
            // Set values in edit form
            editBookingDateInput.value = bookingDate;
            // Call populateTimeOptions with bookingTime as defaultTime
            console.log('bookingTime', bookingTime);
            populateTimeOptions(editBookingDateInput, editBookingTimeSelect, bookingTime);
            editNumberOfPeopleInput.value = totalPeople;
            editNumberOfHoursInput.value = hours;
  
            // Mark checked drinks in edit form
            document.querySelectorAll('#editDrinksContainer input[name="drinks"]').forEach(function (checkbox) {
                checkbox.checked = drinksArray.includes(checkbox.value);
            });
  
            // Update cost summary for edit form
            updateCostSummary(editBookingDateInput, editBookingTimeSelect, editNumberOfHoursInput, editNumberOfPeopleInput, costSummaryDiv);
  
            // Toggle view: hide bookings list and show edit form
            document.getElementById('bookings-list-container').classList.add('d-none');
            document.getElementById('edit-booking-container').classList.remove('d-none');
            editBookingDateInput.addEventListener('change', function () {
                populateTimeOptions(editBookingDateInput, editBookingTimeSelect);
                paymentMessageDiv.innerText = "Note: Payment is made online (30% deposit). The remainder is due at the venue.";
                updateCostSummary(editBookingDateInput, editBookingTimeSelect, editNumberOfHoursInput, editNumberOfPeopleInput, costSummaryDiv);
            });
        
            editNumberOfHoursInput.addEventListener('input', function () {
                updateCostSummary(editBookingDateInput, editBookingTimeSelect, editNumberOfHoursInput, editNumberOfPeopleInput, costSummaryDiv);
            });
        
            editNumberOfPeopleInput.addEventListener('input', function () {
                updateCostSummary(editBookingDateInput, editBookingTimeSelect, editNumberOfHoursInput, editNumberOfPeopleInput, costSummaryDiv);
            });
        }
    });

    // Back button for edit view
    document.getElementById('back-to-bookings').addEventListener('click', function (e) {
        e.preventDefault();
        document.getElementById('edit-booking-container').classList.add('d-none');
        document.getElementById('bookings-list-container').classList.remove('d-none');
    });
});
