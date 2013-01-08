""" @package hwm.application.core
Initializes the Hardware Manager application.
 
This module contains the methods responsible for initializing the Hardware Manager. This entails setting up the 
application state and starting the reactor loop.
"""

# Import the required modules
from app_state import ManagerState

def initialize():
  """Initializes the hardware manager.
  
  Initializes the hardware manager by setting up the state and starting the event reactor.
  """
  
  # Announce program start
  announce_start()
  
  # Read the configuration files
  ManagerState.read_configuration('configuration.yaml');
  #ManagerState.read_configuration('pipelines.yaml');

def start():
  """Starts the hardware manager.
  
  Starts the hardware manager after initialization has been performed.
  """
  
  print "\n# Starting the event reactor."

def announce_start():
  """Announces the application start to the console and application logs."""
  
  # Print a message to the terminal
  print " ___________________________________________________ "
  print "|        Mercury2 - Hardware Manager ("+ManagerState.version+")        |"
  print "|                                                   |"
  print "| Developed by the Michigan Exploration Laboratory  |"
  print "| http://exploration.engin.umich.edu/blog/          |"
  print "|___________________________________________________|"
  print "\n# Starting the Hardware Manager." 
  
  # Update the log
