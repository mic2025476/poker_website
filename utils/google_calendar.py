import os
import json
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from django.conf import settings
from google.oauth2 import service_account
import time
from zoneinfo import ZoneInfo
from functools import lru_cache
from django.core.cache import cache
from googleapiclient.errors import HttpError


SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarService:
    def _call_with_backoff(self, fn, *, max_attempts=6):
        """
        Call a Google API function with exponential backoff.
        - Retries 403 rateLimitExceeded and 429.
        - Backs off 1,2,4,8,16,32s.
        """
        delay = 1
        for attempt in range(1, max_attempts + 1):
            try:
                return fn()
            except HttpError as e:
                status = getattr(e.resp, "status", None)
                msg = str(e)
                if status in (403, 429) and ("rateLimitExceeded" in msg or "userRateLimitExceeded" in msg):
                    if attempt == max_attempts:
                        raise
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise

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
        Get calendar events for a specific date range. Cached ~2 minutes.
        """
        if not self.service:
            self.authenticate()

        if end_date is None:
            end_date = start_date

        # RFC3339 UTC window
        tz = ZoneInfo("Europe/Berlin")
        time_min = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=tz).isoformat()
        time_max = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=tz).isoformat()

        cache_key = f"gcal:events:{self.calendar_id}:{time_min}:{time_max}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        def _list():
            return self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime',
                maxResults=2500,
                # Reduce payload to essentials
                fields="items(id,summary,start(date,dateTime),end(date,dateTime))"
            ).execute()

        try:
            events_result = self._call_with_backoff(_list)
            events = events_result.get('items', [])
            cache.set(cache_key, events, timeout=120)  # 2 minutes
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
        blocking_events = getattr(settings, 'CALENDAR_BLOCKING_EVENTS', ['Poker Booking from Website'])
        
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
    
    def is_time_available(self, date, start_time, end_time, busy_times=None):
        """
        Check if a specific time slot is available (only blocking events).
        """
        if busy_times is None:
            busy_times = self.get_busy_times(date)

        for busy_slot in busy_times:
            if busy_slot['all_day']:
                return False

            busy_start = datetime.strptime(busy_slot['start_time'], '%H:%M:%S').time()
            busy_end = datetime.strptime(busy_slot['end_time'], '%H:%M:%S').time()

            if start_time < busy_end and end_time > busy_start:
                return False
        return True

    def get_available_time_slots(self, date, business_start='00:00', business_end='23:00'):
        busy_times = self.get_busy_times(date)  # ONE fetch (cached)

        business_start_time = datetime.strptime(business_start, '%H:%M').time()
        business_end_time = datetime.strptime(business_end, '%H:%M').time()

        available_slots = []
        current_time = datetime.combine(date, business_start_time)

        while current_time.time() < business_end_time:
            slot_time = current_time.time()
            is_available = self.is_time_available(date, slot_time,
                                                (datetime.combine(date, slot_time) + timedelta(hours=1)).time(),
                                                busy_times=busy_times)
            if is_available:
                available_slots.append(slot_time.strftime('%H:%M'))
            current_time += timedelta(hours=1)

        return available_slots

    
    def get_available_durations(self, date, start_time, max_duration=12, business_end='23:59'):
        start_dt = datetime.strptime(start_time, '%H:%M').time()
        business_end_time = datetime.strptime(business_end, '%H:%M').time()
        busy_times = self.get_busy_times(date)  # ONE fetch (cached)

        # All-day block?
        for b in busy_times:
            if b['all_day']:
                return []

        # Find next conflict after start
        next_conflict_time = None
        for b in busy_times:
            b_start = datetime.strptime(b['start_time'], '%H:%M:%S').time()
            if b_start > start_dt and (next_conflict_time is None or b_start < next_conflict_time):
                next_conflict_time = b_start

        max_end_time = next_conflict_time or business_end_time

        available_durations = []
        for duration in range(1, max_duration + 1):
            end_dt = (datetime.combine(date, start_dt) + timedelta(hours=duration)).time()
            if end_dt > max_end_time:
                break
            if self.is_time_available(date, start_dt, end_dt, busy_times=busy_times):
                available_durations.append(duration)
            else:
                break
        return available_durations

    @lru_cache(maxsize=1)
    def get_or_create_booking_calendar(self):
        """
        Get or create the booking calendar. Cached in-process.
        Also cached in Django cache for 24h to be safe across workers.
        """
        if not self.service:
            self.authenticate()

        calendar_name = "Poker Booking from Website"

        # Cross-worker cache first
        cache_key = "gcal:booking_calendar_id"
        cached_id = cache.get(cache_key)
        if cached_id:
            return cached_id

        def _list_cals():
            return self.service.calendarList().list(
                fields="items(id,summary)"
            ).execute()

        try:
            cl = self._call_with_backoff(_list_cals)
            for cal in cl.get('items', []):
                if cal.get('summary') == calendar_name:
                    cache.set(cache_key, cal['id'], timeout=24*3600)
                    return cal['id']

            # Create if not found
            def _insert():
                return self.service.calendars().insert(body={
                    'summary': calendar_name,
                    'description': 'Calendar for poker lounge bookings made through the website',
                    'timeZone': 'Europe/Berlin'
                }).execute()

            created = self._call_with_backoff(_insert)
            cid = created['id']
            cache.set(cache_key, cid, timeout=24*3600)
            return cid

        except Exception as e:
            print(f"Error creating/getting booking calendar: {e}")
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
            tz = ZoneInfo("Europe/Berlin")
            # Prepare event data
            start_datetime = datetime.combine(
                booking_data['booking_date'],
                booking_data['start_time'],
            ).replace(tzinfo=tz)

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
            print(f"Inserting event into calendar: {calendar_id} {event_body}")
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
            
            tz = ZoneInfo("Europe/Berlin")

            start_datetime = datetime.combine(
                booking_data['booking_date'],
                booking_data['start_time'],
            ).replace(tzinfo=tz)

            end_datetime = datetime.combine(
                booking_data['booking_date'],
                datetime.max.time().replace(microsecond=0),
            ).replace(tzinfo=tz)

            time_min = start_datetime.isoformat()
            time_max = end_datetime.isoformat()
            
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