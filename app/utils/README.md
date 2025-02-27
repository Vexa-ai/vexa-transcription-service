# Function Logger

A simple, lightweight logger that creates separate log files for specific functions or code locations.

## Features

- Creates separate log files for each function or specified location
- Captures variables with explicit key-value pairs
- Minimal setup required
- Can be used with a single line of code
- Supports both direct logging and decorator-based logging

## Usage

### Basic Usage - Single Line Logging

Import the logger and add a single line where you want to log:

```python
from app.utils.function_logger import function_logger

def my_function(param1, param2):
    # Your code here
    result = param1 + param2
    
    # Add this single line to log information
    function_logger.log("Custom message", param1=param1, param2=param2, result=result)
    
    # More code
```

### Decorator-Based Logging

You can also use the decorator approach to automatically log function calls and returns:

```python
from app.utils.function_logger import function_logger

@function_logger.decorator
def my_function(param1, param2):
    # Your code here
    return result
```

### Custom File Names

You can specify a custom file name for your logs:

```python
@function_logger.decorator(custom_file="custom_name")
def my_function():
    # Your code here
```

Or with direct logging:

```python
function_logger.log("Message", file_name="custom_name", function_name="custom_function", var1=value1)
```

### Class Method Logging

You can also log from class methods:

```python
class MyClass:
    def __init__(self, name):
        self.name = name
        
    def my_method(self, param):
        # Log with class instance information
        function_logger.log("Method called", class_name=self.name, param=param)
        # Method implementation
```

## Log File Location

By default, log files are stored in the `logs` directory at the root of your project. Each log file is named using the pattern `{file_name}_{function_name}.log`.

## Log Format

Each log entry includes:
- Timestamp
- Custom message
- Variables (as key-value pairs)
- Separator line

Example log entry:
```
[2023-02-26 15:30:45.123] Transcribing audio for meeting 12345
Variables:
  meeting_id: 12345
  transcription_model: None
--------------------------------------------------------------------------------
```

## Example

See `logger_example.py` for a complete example of how to use the function logger. 