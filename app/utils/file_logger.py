import logging
import os
import inspect
from pathlib import Path
from datetime import datetime

class FileLogger:
    """
    A logger specifically designed for file operations and content tracking.
    Similar to FunctionLogger but optimized for file operations.
    
    Usage:
    1. Import the logger: `from app.utils.file_logger import file_logger`
    2. Add a single line where you want to log: `file_logger.log("Custom message", key1=value1, key2=value2)`
    """
    
    def __init__(self, base_log_dir="logs/files"):
        """Initialize the logger with a base directory for log files."""
        self.base_log_dir = base_log_dir
        # Create logs directory if it doesn't exist
        os.makedirs(self.base_log_dir, exist_ok=True)
    
    def log(self, message="", **kwargs):
        """
        Log a message with associated data to a file.
        
        Args:
            message: Custom message to include in the log
            **kwargs: Any variables you want to log (key=value pairs)
        """
        # Get caller information
        frame = inspect.currentframe().f_back
        function_name = frame.f_code.co_name
        file_name = Path(frame.f_code.co_filename).stem
        
        # Create log file name
        log_file_name = f"{file_name}_{function_name}.log"
        log_file_path = os.path.join(self.base_log_dir, log_file_name)
        
        # Format timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Format the log message
        log_entry = f"[{timestamp}] {message}\n"
        
        # Add variables if provided
        if kwargs:
            # Format the variables, handling potential large data structures
            filtered_vars = {}
            for k, v in kwargs.items():
                if not k.startswith('__') and not callable(v):
                    # Convert to string with length limit to prevent huge log files
                    str_val = str(v)
                    if len(str_val) > 1000:  # Limit long values
                        str_val = str_val[:1000] + "... [truncated]"
                    filtered_vars[k] = str_val
                    
            var_str = "\n".join([f"  {k}: {v}" for k, v in filtered_vars.items()])
            log_entry += f"Variables:\n{var_str}\n"
        
        log_entry += "-" * 80 + "\n"
        
        # Write to the log file
        with open(log_file_path, 'a') as f:
            f.write(log_entry)

# Create a singleton instance
file_logger = FileLogger() 