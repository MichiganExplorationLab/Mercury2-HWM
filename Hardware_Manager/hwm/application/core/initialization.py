""" @package hwm.application.core
Initializes the Hardware Manager application.
 
This module contains the methods responsible for initializing the Hardware Manager. This entails setting up the 
application state and starting the reactor loop.
"""

# Import the required modules
from app_state import ManagerState
import logging

def initialize():
  """Initializes the hardware manager.
  
  Initializes the hardware manager by setting up the state and starting the event reactor.
  """
  
  # Announce program start
  announce_start()
  
  # Setup logging
  setup_logs()
  
  # Read the configuration files
  ManagerState.read_configuration('config/configuration.yml');
  #ManagerState.read_configuration('pipelines.yaml');

def start():
  """Starts the hardware manager.
  
  Starts the hardware manager after initialization has been performed.
  """
  
  # Announce reactor start
  if ManagerState.verbose_startup:
    print "- Starting the event reactor."

def announce_start():
  """Announces the application start to the console and application logs."""
  
  # Print a message to the terminal
  print " ___________________________________________________ "
  print "|        Mercury2 - Hardware Manager ("+ManagerState.version+")        |"
  print "|                                                   |"
  print "| Developed by the Michigan Exploration Laboratory  |"
  print "| http://exploration.engin.umich.edu/blog/          |"
  print "|___________________________________________________|\n"

def setup_logs():
  """Sets up the logger."""
  
  # Configure the logger
  logging.basicConfig(filename='logs/hardware_manager.log',
                      format='%(asctime)s - %(levelname)s - %(message)s',
                      datefmt='%m/%d/%Y %H:%M:%S',
                      level=logging.DEBUG)
  
  # Announce the logging system setup
  if ManagerState.verbose_startup:
    print "- Setting up the logging system."
  
  # Log the program start
  logging.info("Startup: Starting the hardware manager.")
  logging.info("Startup: Setup the logging system.")
