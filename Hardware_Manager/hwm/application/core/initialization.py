""" @package hwm.application.core.initialization
Initializes the Hardware Manager application.
 
This module contains the methods responsible for initializing the Hardware Manager. This entails setting up the 
application state and starting the reactor loop.
"""

# Import the required modules
from pkg_resources import Requirement, resource_filename
from configuration import Configuration
from hwm.application.core import errors
import logging, sys, shutil, os

def initialize():
  """Initializes the hardware manager.
  
  Initializes the hardware manager by setting up the state and starting the event reactor.
  """
  
  # Set the default uncaught exception handler
  sys.excepthook = errors.uncaught_exception
  
  # Announce program start
  announce_start()
  
  # Check for user files
  verify_data_files()
  
  # Setup logging
  setup_logs()
  
  # Read the configuration files
  Configuration.read_configuration(self.data_directory+'/config/configuration.yml')
  #Configuration.read_configuration(self.data_directory+'config/pipelines.yaml')
  
  # Verify that all required configuration options are set
  Configuration.check_required_configuration()
  
  # Start the application
  start()
  
  # Exit the program
  sys.exit(0)

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
  print "|            Mercury2 - Hardware Manager            |"
  print "|                                                   |"
  print "| Developed by the Michigan Exploration Laboratory  |"
  print "| http://exploration.engin.umich.edu/blog/          |"
  print "|___________________________________________________|\n"
  print "Version: "+Configuration.version+"\n"

def verify_data_files():
  """Checks for the presence of required data file directories.
  
  This method verifies that required data files and data file directories exist in the proper directory (/var/local on 
  linux). If they don't (i.e. if this is the first time that the program has been run), the defaults will be copied from
  the package folder (in python2.7/dist-packages)"""
  
  # Check if the data directory exists
  if not os.path.exists(Configuration.data_directory):
    # Copy over the default data files/directories
    default_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"data")
    shutil.copytree(default_data_directory, Configuration.data_directory)
    if Configuration.verbose_startup:
      print "- Data directory not found, copied defaults to: "+Configuration.data_directory
  else:
    if Configuration.verbose_startup:
      print "- Data directory found at: "+Configuration.data_directory

def setup_logs():
  """Sets up the logger."""
  
  # Configure the logger
  logging.basicConfig(filename=Configuration.data_directory+'/logs/hardware_manager.log',
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
