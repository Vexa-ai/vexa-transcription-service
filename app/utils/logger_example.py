"""Example script demonstrating how to use the function logger."""

from app.utils.function_logger import function_logger

# Example 1: Using the direct log method
def process_data(data):
    """Process some data and log the results."""
    # Your processing logic here
    result = data * 2
    
    # Add a single line to log information - now with direct key-value pairs
    function_logger.log("Processing data", input_data=data, result=result)
    
    return result

# Example 2: Using the decorator approach
@function_logger.decorator
def calculate_sum(a, b):
    """Calculate the sum of two numbers."""
    result = a + b
    return result

# Example 3: Using the decorator with a custom file name
@function_logger.decorator(custom_file="math_operations")
def multiply(a, b):
    """Multiply two numbers."""
    result = a * b
    return result

# Example 4: Class method logging
class Calculator:
    def __init__(self, name):
        self.name = name
    
    def add(self, a, b):
        result = a + b
        # Log with class instance information
        function_logger.log("Adding numbers", calculator_name=self.name, a=a, b=b, result=result)
        return result

if __name__ == "__main__":
    # Run the examples
    process_data(42)
    calculate_sum(10, 20)
    multiply(5, 6)
    
    # Class method example
    calc = Calculator("MyCalculator")
    calc.add(15, 25)
    
    print("Check the logs directory for the generated log files:")
    print("- processor_process_data.log")
    print("- logger_example_calculate_sum.log")
    print("- math_operations_multiply.log")
    print("- logger_example_add.log") 