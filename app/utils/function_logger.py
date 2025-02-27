import logging
import os
import inspect
import functools
from pathlib import Path
from datetime import datetime

class FunctionLogger:
    """
    A simple logger that creates separate log files for specific functions or code locations.
    
    Usage:
    1. Import the logger: `from app.utils.function_logger import function_logger`
    2. Add a single line where you want to log: `function_logger.log("Custom message", key1=value1, key2=value2)`
    """
    
    def __init__(self, base_log_dir="logs"):
        """Initialize the logger with a base directory for log files."""
        self.base_log_dir = base_log_dir
        # Create logs directory if it doesn't exist
        os.makedirs(self.base_log_dir, exist_ok=True)
    
    def log(self, message="", file_name=None, function_name=None, **kwargs):
        """
        Log a message to a file specific to the calling function or specified file/function.
        
        Args:
            message: Custom message to include in the log
            file_name: Optional specific file name for the log
            function_name: Optional specific function name for the log
            **kwargs: Any variables you want to log (key=value pairs)
        """
        # Get caller information if not provided
        if function_name is None or file_name is None:
            frame = inspect.currentframe().f_back
            if function_name is None:
                function_name = frame.f_code.co_name
            if file_name is None:
                # Get the file name without extension
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
            # Format the variables
            filtered_vars = {k: str(v) for k, v in kwargs.items() 
                            if not k.startswith('__') and not callable(v)}
            var_str = "\n".join([f"  {k}: {v}" for k, v in filtered_vars.items()])
            log_entry += f"Variables:\n{var_str}\n"
        
        log_entry += "-" * 80 + "\n"
        
        # Write to the log file
        with open(log_file_path, 'a') as f:
            f.write(log_entry)
    
    def decorator(self, func=None, *, custom_file=None):
        """
        Decorator to automatically log function calls and returns.
        
        Usage:
            @function_logger.decorator
            def my_function(arg1, arg2):
                ...
                
            @function_logger.decorator(custom_file="custom_name")
            def another_function():
                ...
        """
        def decorator_wrapper(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                # Get function name and file
                fn_name = fn.__name__
                file_name = custom_file or Path(inspect.getfile(fn)).stem
                
                # Log function call
                call_vars = dict(zip(fn.__code__.co_varnames, args))
                call_vars.update(kwargs)
                
                # Filter out 'self' for class methods
                if 'self' in call_vars:
                    del call_vars['self']
                
                self.log(f"CALL: {fn_name}", file_name=file_name, function_name=fn_name, **call_vars)
                
                # Execute function
                result = fn(*args, **kwargs)
                
                # Log function return
                self.log(f"RETURN: {fn_name}", file_name=file_name, function_name=fn_name, result=result)
                
                return result
            return wrapper
        
        # Handle both @decorator and @decorator() syntax
        if func is not None:
            return decorator_wrapper(func)
        return decorator_wrapper

# Create a singleton instance
function_logger = FunctionLogger() 