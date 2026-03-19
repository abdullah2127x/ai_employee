"""Test enhanced logging manager"""

from utils.logging_manager import LoggingManager

# Initialize logger
logger = LoggingManager(enable_console=True, log_level="DEBUG")

print("=" * 60)
print("Testing Enhanced Logging Manager")
print("=" * 60)

# Test INFO
print("\n1. Testing INFO level:")
logger.write_to_timeline("Test info message", actor="test_component", level="INFO")

# Test WARNING
print("\n2. Testing WARNING level:")
logger.log_warning("This is a warning message", actor="test_component")

# Test ERROR with stack trace
print("\n3. Testing ERROR level with stack trace:")
try:
    # Create a deliberate error
    result = 10 / 0
except Exception as e:
    logger.log_error("Division by zero occurred", error=e, actor="test_component")

# Test CRITICAL
print("\n4. Testing CRITICAL level:")
try:
    raise RuntimeError("Critical system failure")
except Exception as e:
    logger.log_critical("System crash detected", error=e, actor="test_component")

# Test DEBUG
print("\n5. Testing DEBUG level:")
logger.log_debug("This is a debug message", actor="test_component")

# Test task logging
print("\n6. Testing task logging:")
logger.write_to_task_log(
    task_type="test",
    task_id="test_001",
    message="Task started",
    actor="test_component",
    level="INFO"
)

logger.write_to_task_log(
    task_type="test",
    task_id="test_001",
    message="Task completed successfully",
    actor="test_component",
    level="INFO"
)

print("\n✅ All tests complete!")
print(f"\nCheck the following files:")
print(f"  - Timeline: {logger.get_timeline_path()}")
print(f"  - Task Log: {logger.get_task_log_path('test', 'test_001')}")
print(f"  - Error Log: {logger.get_error_log_path()}")
