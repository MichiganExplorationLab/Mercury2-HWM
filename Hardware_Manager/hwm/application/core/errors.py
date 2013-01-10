""" @package hwm.application.core
Contains general error handling functions.

This module contains assorted error handling functions. These functions are typically used to handle top-level hardware
manager exceptions (such as a previously uncaught exceptions).
"""

# Import the required libraries
import sys, os, logging, traceback

def uncaught_exception(type, value, tb):
  """Handles previously uncaught exceptions.
  
  This method is used to handle top-level uncaught exceptions. It exits the program with an error code if such an 
  exception is encountered.
  
  @note This function logs all uncaught exceptions to the application logs, which are set up in 
        hwm.application.core.initialization. If the logs haven't been set up (i.e. the exception was generated early on)
        the default log settings will be used.
  
  @param type   The exception type.
  @param value  The exception descriptive text.
  @param tb     The complete traceback for the provided exception.
  """
  
  # Extract the traceback info
  extracted_tb = traceback.extract_tb(tb)
  file_name = os.path.split(extracted_tb[-1][0])[1]
  line_number = extracted_tb[-1][1]
  
  # Log the exception
  logging.error("Uncaught exception in '%s' line %d: %s, %s", file_name, line_number, type.__name__, value)
  
  # Output the exception to sterr
  print "\n[ERROR] Fatal error in '{}' line {}: {}, {}".format(file_name, line_number, type.__name__, value)
  
  # Exit the program with an error code
  sys.exit(1)
