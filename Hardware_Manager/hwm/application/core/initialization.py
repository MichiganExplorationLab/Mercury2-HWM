""" @package hwm.application.core.initialization
Initializes the Hardware Manager application.
 
This module contains the methods responsible for initializing the Hardware Manager. This entails setting up the 
application state and starting the reactor loop.
"""

# Import the required modules
from configuration import Configuration
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
  Configuration.read_configuration('config/configuration.yml')
  #Configuration.read_configuration('pipelines.yaml')
  
  # Verify that all required configuration options are set
  Configuration.check_required_configuration()

def start():
  """Starts the hardware manager.
  
  Starts the hardware manager after initialization has been performed.
  """
  
  # Announce reactor start
  if Configuration.verbose_startup:
    print "- Starting the event reactor."

def announce_start():
  """Announces the application start to the console and application logs."""
  
  # Print a message to the terminal
  print " ___________________________________________________ "
  print "|        Mercury2 - Hardware Manager ("+Configuration.version+")        |"
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
  if Configuration.verbose_startup:
    print "- Setting up the logging system."
  
  # Log the program start
  logging.info("=======================================")
  logging.info("Startup: Starting the hardware manager.")
  logging.info("Startup: Setup the logging system.")
