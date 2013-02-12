""" @package hwm.core.initialization
Initializes the Hardware Manager application.
 
This module contains the methods responsible for initializing the Hardware Manager. This entails setting up the 
application state and starting the reactor loop.
"""

# Import the required modules
import logging, sys, shutil, os
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from pkg_resources import Requirement, resource_filename
from configuration import Configuration
from hwm.core import errors
from hwm.sessions import coordinator, schedule
from hwm.hardware.pipelines import manager

def initialize():
  """Initializes the hardware manager.
  
  This method initializes the hardware manager by initializing the required resources (e.g. pipeline manager, schedule 
  manager, configuration, etc.) and starting the event reactor. This is the main entry location for the hardware 
  manager.
  """
  
  # Set the default uncaught exception handler
  sys.excepthook = errors.uncaught_exception
  
  # Announce program start
  announce_start()
  
  # Check for user files
  verify_data_files()
  
  # Setup logging
  setup_logs()
  
  # Setup the configuration
  setup_configuration()
  
  # Initialize the schedule coordinator
  if Configuration.get('offline-mode'):
    schedule_manager = schedule.ScheduleManager(Configuration.data_directory+Configuration.get('schedule-location-local'))
  else:
    schedule_manager = schedule.ScheduleManager(Configuration.get('schedule-location-network'))
  
  # Initialize the pipeline manager
  pipeline_manager = manager.PipelineManager()
  
  # Initialize the session coordinator
  session_coordinator = coordinator.SessionCoordinator(schedule_manager, pipeline_manager)
  
  # Set up the session coordinator looping call
  coordination_loop = LoopingCall(session_coordinator.coordinate)
  coordination_loop.start(1)
  
  # Start the reactor
  if Configuration.verbose_startup:
    print "- Started the event reactor."
  logging.info("Startup: Started the event reactor.")
  reactor.run()
  
  # Exit the program
  sys.exit(0)

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
    # Copy over the default data files/directories from the source copies
    default_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"data")
    shutil.copytree(default_data_directory, Configuration.data_directory)
    if Configuration.verbose_startup:
      print "- Data directory not found, copied defaults to: "+Configuration.data_directory
  else:
    if Configuration.verbose_startup:
      print "- Data directory found at: "+Configuration.data_directory

def setup_configuration():
  """Sets up the configuration object.
  
  This function sets up the configuration object (a singleton) by loading the required configuration files, validating 
  the required options, and populating the unspecified default options.
  """
  
  # Read the configuration files
  Configuration.read_configuration(Configuration.data_directory+'/config/configuration.yml')
  Configuration.read_configuration(Configuration.data_directory+'/config/pipelines.yml')
  
  # Verify that all required configuration options are set
  Configuration.process_configuration()

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
