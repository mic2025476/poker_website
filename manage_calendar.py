#!/usr/bin/env python
"""
Management script for Google Calendar integration setup
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'poker_lounge.settings')
django.setup()

from utils.google_calendar import GoogleCalendarService
from datetime import datetime, date

def setup_calendar():
    """Setup Google Calendar authentication"""
    print("Setting up Google Calendar integration...")
    print("Make sure you have:")
    print("1. Created a Google Cloud project")
    print("2. Enabled Google Calendar API")
    print("3. Downloaded credentials.json file to project root")
    print("4. Set GOOGLE_CALENDAR_ID in settings.py (or use 'primary')")
    print()
    
    calendar_service = GoogleCalendarService()
    
    try:
        service = calendar_service.authenticate()
        print("✓ Authentication successful!")
        
        # Test by getting today's events
        today = date.today()
        events = calendar_service.get_events(today)
        print(f"✓ Found {len(events)} events for today")
        
        if events:
            print("Today's events:")
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                print(f"  - {event.get('summary', 'No title')}: {start}")
        
        return True
        
    except FileNotFoundError:
        print("✗ credentials.json file not found!")
        print("Please download it from Google Cloud Console and place it in the project root.")
        return False
        
    except Exception as e:
        print(f"✗ Error setting up calendar: {e}")
        return False

def test_calendar():
    """Test calendar integration"""
    print("Testing Google Calendar integration...")
    
    calendar_service = GoogleCalendarService()
    
    try:
        today = date.today()
        busy_times = calendar_service.get_busy_times(today)
        
        print(f"✓ Found {len(busy_times)} busy time slots for today:")
        for slot in busy_times:
            print(f"  - {slot['start_time']} to {slot['end_time']}: {slot['title']}")
        
        # Test availability check
        test_time_start = datetime.now().time()
        test_time_end = datetime.now().replace(hour=23, minute=59).time()
        is_available = calendar_service.is_time_available(today, test_time_start, test_time_end)
        print(f"✓ Time slot availability test: {'Available' if is_available else 'Busy'}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing calendar: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "setup":
            setup_calendar()
        elif command == "test":
            test_calendar()
        else:
            print("Usage: python manage_calendar.py [setup|test]")
    else:
        print("Usage: python manage_calendar.py [setup|test]")
        print("  setup - Setup Google Calendar authentication")
        print("  test  - Test calendar integration")