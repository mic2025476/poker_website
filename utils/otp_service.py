import requests

GOOGLE_APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzjgFhr_1tSuMUTWMutUCpyOYWUcWpOGpY-GO-t_nz75S-13QQt0Wpd3xrFZMeae7OcJw/exec"

def send_otp(email: str) -> dict:
    """
    Call Google Apps Script endpoint to send OTP email.
    Returns JSON response.
    """
    try:
        response = requests.get(GOOGLE_APPS_SCRIPT_URL, params={"email": email}, timeout=10)
        response.raise_for_status()
        return response.json()  # must be JSON in Apps Script
    except Exception as e:
        return {"success": False, "error": str(e)}
