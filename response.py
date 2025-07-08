"""
Common response class for whole project
"""


class Response:
    """
    Common response class for API response
    """

    @classmethod
    def success(cls, data, message):
        """
        Common success method for API response
        """
        return {"success": True, "data": data, "message": message}

    @classmethod
    def success_without_data(cls, message):
        """
        Common success_without_data method for API response
        """
        return {"success": True, "message": message}

    @classmethod
    def error(cls, error):
        # Check if the error is a dictionary
        print(f'error {error}')
        if isinstance(error, dict):
            try:
                # Extract and format error messages as a single string
                error_message = " ".join(
                    [f"{key}: {', '.join(value)}" for key, value in error.items()]
                )
            except Exception as e:
                # Handle potential issues during the formatting
                error_message = f"Error formatting message: {str(e)}"
        else:
            error_message = error
        return {"success": False, "message": error_message}
