import os
import json
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from django.conf import settings
from google.oauth2 import service_account

SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarService:
    def __init__(self):
        self.credentials_file = getattr(settings, 'GOOGLE_CALENDAR_CREDENTIALS_FILE', 'service_account.json')
        self.token_file = getattr(settings, 'GOOGLE_CALENDAR_TOKEN_FILE', 'token.json')
        self.calendar_id = getattr(settings, 'GOOGLE_CALENDAR_ID', 'primary')
        self.service = None
    
    def authenticate(self):
        """Authenticate using a Google Service Account (no browser needed)"""
        if not os.path.exists(self.credentials_file):
            raise FileNotFoundError(f"Google Calendar credentials file not found: {self.credentials_file}")

        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=SCOPES
            )
            self.service = build('calendar', 'v3', credentials=credentials)
            print("✅ Google Calendar service authenticated successfully (service account mode)")
            return self.service
        except Exception as e:
            print(f"❌ Calendar service authentication failed: {e}")
            raise

    def get_events(self, start_date, end_date=None):
        """
        Get calendar events for a specific date range

        Args:
            start_date (datetime.date): Start date to check
            end_date (datetime.date, optional): End date to check. If None, uses start_date

        Returns:
            list: List of calendar events
        """
        if not self.service:
            self.authenticate()

        if end_date is None:
            end_date = start_date

        # Convert dates to RFC3339 timestamp
        time_min = datetime.combine(start_date, datetime.min.time()).isoformat() + 'Z'
        time_max = datetime.combine(end_date, datetime.max.time()).isoformat() + 'Z'

        try:
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            return events

        except Exception as e:
            print(f"Error fetching calendar events: {e}")
            return []
    
    def get_busy_times(self, date):
        """
        Get busy time slots for a specific date - only for configurable blocking events
        
        Args:
            date (datetime.date): Date to check
        
        Returns:
            list: List of dictionaries with 'start_time' and 'end_time' keys
        """
        events = self.get_events(date)
        print(f'DEBUG: NEW CODE - events {len(events)} for {date}')
        busy_times = []
        
        # Get blocking events from settings
        blocking_events = getattr(settings, 'CALENDAR_BLOCKING_EVENTS', ['MGEN - F24'])
        
        for event in events:
            # Check if event title matches any blocking event
            event_title = event.get('summary', '').strip()
            print(f'event_title: {event_title}')

            # Check if this event should block booking times
            should_block = False
            for blocking_event in blocking_events:
                if blocking_event.upper() in event_title.upper():
                    should_block = True
                    print(f'Blocking event found: {event_title} matches {blocking_event}')
                    break
            
            if not should_block:
                continue
                
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # Handle all-day events
            if 'T' not in start:
                # All-day event, block the entire day
                busy_times.append({
                    'start_time': '00:00:00',
                    'end_time': '23:59:59',
                    'title': event_title,
                    'all_day': True
                })
            else:
                # Timed event
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                
                # Convert to local time if needed
                busy_times.append({
                    'start_time': start_dt.time().strftime('%H:%M:%S'),
                    'end_time': end_dt.time().strftime('%H:%M:%S'),
                    'title': event_title,
                    'all_day': False
                })
        
        return busy_times
    
    def is_time_available(self, date, start_time, end_time):
        """
        Check if a specific time slot is available (only checks configurable blocking events)
        
        Args:
            date (datetime.date): Date to check
            start_time (datetime.time): Start time
            end_time (datetime.time): End time
        
        Returns:
            bool: True if available, False if busy (blocked by blocking events)
        """
        busy_times = self.get_busy_times(date)  # This already filters for blocking events only
        
        for busy_slot in busy_times:
            if busy_slot['all_day']:
                return False
            
            busy_start = datetime.strptime(busy_slot['start_time'], '%H:%M:%S').time()
            busy_end = datetime.strptime(busy_slot['end_time'], '%H:%M:%S').time()
            
            # Check for overlap
            if start_time < busy_end and end_time > busy_start:
                return False
        
        return True
    
    def get_available_time_slots(self, date, business_start='00:00', business_end='23:00'):
        """
        Get available time slots for a specific date considering blocking events
        
        Args:
            date (datetime.date): Date to check
            business_start (str): Business opening time (format: 'HH:MM')
            business_end (str): Business closing time (format: 'HH:MM')
        
        Returns:
            list: List of available time slots (strings in 'HH:MM' format)
        """
        busy_times = self.get_busy_times(date)
        
        # Convert business hours to datetime objects for easier comparison
        business_start_time = datetime.strptime(business_start, '%H:%M').time()
        business_end_time = datetime.strptime(business_end, '%H:%M').time()
        
        available_slots = []
        
        # Generate all possible hourly slots
        current_time = datetime.combine(date, business_start_time)
        
        while current_time.time() < business_end_time:
            slot_time = current_time.time()
            
            # Check if this slot is available (not conflicting with any busy time)
            is_available = True
            for busy_slot in busy_times:
                if busy_slot['all_day']:
                    is_available = False
                    break
                
                busy_start = datetime.strptime(busy_slot['start_time'], '%H:%M:%S').time()
                busy_end = datetime.strptime(busy_slot['end_time'], '%H:%M:%S').time()
                
                # If slot time falls within a busy period, it's not available
                if busy_start <= slot_time < busy_end:
                    is_available = False
                    break
            
            if is_available:
                available_slots.append(slot_time.strftime('%H:%M'))
            
            # Move to next hour
            current_time += timedelta(hours=1)
        
        return available_slots
    
    def get_available_durations(self, date, start_time, max_duration=12, business_end='23:59'):
        """
        Get available booking durations for a specific start time considering blocking events
        
        Args:
            date (datetime.date): Date to check
            start_time (str): Start time in 'HH:MM' format
            max_duration (int): Maximum booking duration in hours
            business_end (str): Business closing time (format: 'HH:MM')
        
        Returns:
            list: List of available durations in hours (integers)
        """
        # Convert times to datetime objects
        start_dt = datetime.strptime(start_time, '%H:%M').time()
        business_end_time = datetime.strptime(business_end, '%H:%M').time()
        
        available_durations = []
        
        # Get busy times to check for conflicts
        busy_times = self.get_busy_times(date)
        
        # Find the next busy period after the start time
        next_conflict_time = None
        for busy_slot in busy_times:
            if busy_slot['all_day']:
                # All-day event blocks everything
                return []
            
            busy_start = datetime.strptime(busy_slot['start_time'], '%H:%M:%S').time()
            
            # Only consider events that start after our start time
            if busy_start > start_dt:
                if next_conflict_time is None or busy_start < next_conflict_time:
                    next_conflict_time = busy_start
        
        # Calculate maximum duration based on next conflict or business end
        if next_conflict_time:
            max_end_time = next_conflict_time
        else:
            max_end_time = business_end_time
        
        # Check each possible duration
        for duration in range(1, max_duration + 1):
            end_datetime = datetime.combine(date, start_dt) + timedelta(hours=duration)
            end_time = end_datetime.time()
            
            # Don't exceed the maximum allowed end time
            if end_time > max_end_time:
                break
            
            # Don't go past midnight (next day)
            if end_datetime.date() > date:
                break
            
            # Check if this duration conflicts with any busy time
            is_available = self.is_time_available(date, start_dt, end_time)
            
            if is_available:
                available_durations.append(duration)
            else:
                # If this duration conflicts, longer durations will also conflict
                break
        
        return available_durations
    
    def get_or_create_booking_calendar(self):
        """
        Get or create a separate calendar for poker bookings from website
        
        Returns:
            str: Calendar ID of the booking calendar
        """
        if not self.service:
            self.authenticate()
        
        calendar_name = "Poker Booking from Website"
        
        try:
            # First, check if the calendar already exists
            calendar_list = self.service.calendarList().list().execute()
            
            for calendar in calendar_list.get('items', []):
                if calendar.get('summary') == calendar_name:
                    print(f"Found existing booking calendar: {calendar['id']}")
                    return calendar['id']
            
            # Create new calendar if it doesn't exist
            calendar_body = {
                'summary': calendar_name,
                'description': 'Calendar for poker lounge bookings made through the website',
                'timeZone': 'Europe/Berlin'  # Adjust timezone as needed
            }
            
            created_calendar = self.service.calendars().insert(body=calendar_body).execute()
            calendar_id = created_calendar['id']
            
            print(f"Created new booking calendar: {calendar_id}")
            return calendar_id
            
        except Exception as e:
            print(f"Error creating/getting booking calendar: {e}")
            # Fallback to primary calendar if there's an issue
            return 'primary'
    
    def add_booking_event(self, booking_data):
        """
        Add a booking event to the poker booking calendar
        
        Args:
            booking_data (dict): Dictionary containing booking information
                - customer_name: Name of the customer
                - booking_date: Date of the booking (datetime.date)
                - start_time: Start time (datetime.time)
                - duration_hours: Duration in hours (int)
                - total_people: Number of people (int)
                - drinks: List of drinks (optional)
                - booking_id: Booking ID (optional)
        
        Returns:
            dict: Created event or None if failed
        """
        if not self.service:
            self.authenticate()
        
        try:
            # Get the booking calendar ID
            calendar_id = self.get_or_create_booking_calendar()
            
            # Prepare event data
            start_datetime = datetime.combine(
                booking_data['booking_date'], 
                booking_data['start_time']
            )
            end_datetime = start_datetime + timedelta(hours=booking_data['duration_hours'])
            
            # Create event title and description
            title = f"Poker Booking - {booking_data['customer_name']}"
            
            description_lines = [
                f"Customer: {booking_data['customer_name']}",
                f"Number of People: {booking_data['total_people']}",
                f"Duration: {booking_data['duration_hours']} hours"
            ]
            
            if booking_data.get('drinks'):
                drinks_list = ', '.join(booking_data['drinks'])
                description_lines.append(f"Drinks: {drinks_list}")
            
            if booking_data.get('booking_id'):
                description_lines.append(f"Booking ID: {booking_data['booking_id']}")
            
            description_lines.append("\\nBooked via website")
            description = "\\n".join(description_lines)
            
            # Create the event
            event_body = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'Europe/Berlin',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'Europe/Berlin',
                },
                'colorId': '11',  # Red color for easy identification
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 60},       # 1 hour before
                    ],
                },
            }
            
            # Insert the event
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()
            
            print(f"Created booking event: {created_event.get('htmlLink')}")
            return created_event
            
        except Exception as e:
            print(f"Error creating booking event: {e}")
            return None
    
    def delete_booking_event(self, booking_data):
        """
        Delete a booking event from the poker booking calendar
        
        Args:
            booking_data (dict): Dictionary containing booking information
                - customer_name: Name of the customer
                - booking_date: Date of the booking (datetime.date)
                - start_time: Start time (datetime.time)
                - booking_id: Booking ID (required for finding the event)
        
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if not self.service:
            self.authenticate()
        
        try:
            # Get the booking calendar ID
            calendar_id = self.get_or_create_booking_calendar()
            
            # Search for the event by title and date
            start_datetime = datetime.combine(
                booking_data['booking_date'], 
                booking_data['start_time']
            )
            end_datetime = datetime.combine(booking_data['booking_date'], datetime.max.time().replace(microsecond=0))
            
            # Create search parameters
            time_min = start_datetime.isoformat() + 'Z'
            time_max = end_datetime.isoformat() + 'Z'
            
            # Search for events on that day
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Find the specific booking event
            target_title = f"Poker Booking - {booking_data['customer_name']}"
            booking_id_str = str(booking_data.get('booking_id', ''))
            
            for event in events:
                event_title = event.get('summary', '')
                event_description = event.get('description', '')
                
                # Match by title and booking ID in description
                if (event_title == target_title and 
                    booking_id_str in event_description):
                    
                    # Delete the event
                    self.service.events().delete(
                        calendarId=calendar_id,
                        eventId=event['id']
                    ).execute()
                    
                    print(f"Deleted calendar event for booking {booking_data.get('booking_id')}")
                    return True
            
            print(f"Calendar event not found for booking {booking_data.get('booking_id')}")
            return False
            
        except Exception as e:
            print(f"Error deleting booking event: {e}")
            return False