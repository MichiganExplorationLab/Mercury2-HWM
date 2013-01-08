# Mercury2 Hardware Manager
# Version: 0.1.0
# Website: http://exploration.engin.umich.edu/blog/
# Created by the Michigan Exploration Laboratory
#
# Enables standardized ground station control over a network for a variety of hardware devices. Interacts with the User
# Interface component of the Mercury2 system to allow for schedule management and a control interface. This bootstrap 
# file is responsible for initializing the application.

# Import the required libraries
from hwm.application.core import initialization

# Verify that the app isn't being run as a module
if __name__ == '__main__':
  # Catch all otherwise uncaught exceptions and pass them to the error handler
  
  # Call the initialization script
  initialization.initialize()
  
  # Start the application
  initialization.start()
