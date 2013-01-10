# Mercury2 Hardware Manager
#
# Website: http://exploration.engin.umich.edu/blog/
# Created by the Michigan Exploration Laboratory
#
# Enables standardized ground station control over a network for a variety of hardware devices. Interacts with the User
# Interface component of the Mercury2 system to allow for schedule management and a control interface. This bootstrap 
# file is responsible for starting the application.

# Import the required libraries
from hwm.application.core import initialization
from hwm.application.core import errors
import sys

# Verify that the app isn't being run as a module
if __name__ == '__main__':
  # Set the default uncaught exception handler
  sys.excepthook = errors.uncaught_exception
  
  # Initialize the application
  initialization.initialize()
  
  # Start the application
  initialization.start()
  
  # Exit the program
  sys.exit(0)
