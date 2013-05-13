""" @package hwm.core.initialization
Initializes the Hardware Manager application.
 
This module contains the methods responsible for initializing and starting the Hardware Manager. This entails setting 
up the application state and starting the reactor loop.
"""

# Import the required system modules
import logging, sys, shutil, os
from OpenSSL import SSL
from twisted.internet import reactor, ssl
from twisted.internet.task import LoopingCall
from twisted.web.server import Site
from pkg_resources import Requirement, resource_filename

# HWM modules
from hwm.core import errors
from hwm.core.configuration import Configuration
from hwm.sessions import coordinator, schedule as schedule
from hwm.hardware.devices import manager as devices
from hwm.hardware.pipelines import manager as pipelines
from hwm.command import parser as command_parser_mod, connection as command_connection
from hwm.command.handlers import system as system_command_handler
from hwm.network.security import verification, permissions

def initialize():
  """Initializes the hardware manager.
  
  This method initializes the hardware manager by initializing the required resources (e.g. pipeline manager, schedule 
  manager, configuration, etc.) and starting the event reactor. This is the main entry location for the hardware 
  manager.
  """
  
  # Set the default uncaught exception handler
  sys.excepthook = errors.uncaught_exception
  
  # Announce program start
  _announce_start()
  
  # Check for user data (config, etc.) files
  _verify_data_files()
  
  # Setup logging
  _setup_logs()
  
  # Setup the configuration
  _setup_configuration()
  
  # Initialize the main reservation schedule
  schedule_manager = _setup_schedule_manager()
  
  # Initialize the device manager
  device_manager = devices.DeviceManager()
  
  # Setup the command parser
  command_parser = _setup_command_system(device_manager);
  
  # Initialize the pipeline manager
  pipeline_manager = pipelines.PipelineManager(device_manager, command_parser)
  
  # Initialize the session coordinator
  session_coordinator = coordinator.SessionCoordinator(schedule_manager, device_manager, pipeline_manager)
  
  # Initialize the required network listeners
  _setup_network_listeners(command_parser);
  
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

def _announce_start():
  """Announces the application start to the console and application logs."""
  
  # Print a message to the terminal
  print " ___________________________________________________ "
  print "|            Mercury2 - Hardware Manager            |"
  print "|                                                   |"
  print "| Developed by the Michigan Exploration Laboratory  |"
  print "| http://exploration.engin.umich.edu/blog/          |"
  print "|___________________________________________________|\n"
  print "Version: "+Configuration.version+"\n"

def _verify_data_files():
  """ Checks for the presence of required data file directories.
  
  This method verifies that required data files and data file directories exist in the proper directory (/var/local on 
  linux). If they don't (i.e. if this is the first time that the program has been run), the defaults will be copied from
  the package folder (in python2.7/dist-packages).
  """
  
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

def _setup_schedule_manager():
  """ Initializes the schedule manager.
  
  This function initializes the schedule manager based on the location of the schedule (either local or remote).
  
  @return Returns an instance to the new ScheduleManager instance.
  """
  
  # Setup the schedule manager
  if Configuration.get('offline-mode'):
    schedule_manager = schedule.ScheduleManager(Configuration.get('schedule-location-local'))
  else:
    schedule_manager = schedule.ScheduleManager(Configuration.get('schedule-location-network'))
  
  return schedule_manager

def _setup_command_system(device_manager):
  """ Sets up the command system.
  
  This function sets up the CommandParser class which is responsible for parsing, validating, and executing commands
  (either from the network or internal scripts). It also, consequently, initializes the permission system which tracks
  user command execution permissions.
  
  @param device_manager  A DeviceManager instance that has been initialized with the station hardware configuration.
                         The command parser requires this so that it can load device command handlers when needed.
  @return Returns a reference to the new CommandParser instance.
  """
  
  # Initialize the command resources
  system_command_handlers = {}
  system_command_handlers['system'] = system_command_handler.SystemCommandHandler()
  if Configuration.get('offline-mode'):
    permission_manager = permissions.PermissionManager(Configuration.get('permissions-location-local'),
                                                       Configuration.get('permissions-update-period'))
  else:
    permission_manager = permissions.PermissionManager(Configuration.get('permissions-location-network'),
                                                       Configuration.get('permissions-update-period'))
  command_parser = command_parser_mod.CommandParser(system_command_handlers, permission_manager)
  
  return command_parser

def _setup_network_listeners(command_parser):
  """ Initializes the various network listeners used by the hardware manager.
  
  This method initializes the network listeners required to accept ground station commands and relay ground station 
  data streams.
  
  @param command_parser  An instance of CommandParser which will be used to handle commands received over the network.
  """
    
  # Create an SSL context for the various listeners
  server_context_factory = verification.create_ssl_context_factory()
  
  # Setup the command listener
  command_factory = Site(command_connection.CommandResource(command_parser))
  reactor.listenSSL(Configuration.get('network-command-port'), command_factory, server_context_factory)

def _setup_configuration():
  """Sets up the configuration object.
  
  This function sets up the configuration object (a singleton) by loading the required configuration files, validating 
  the required options, and populating the unspecified default options.
  """
  
  # Read the configuration files
  Configuration.read_configuration(Configuration.data_directory+'/config/configuration.yml')
  Configuration.read_configuration(Configuration.data_directory+'/config/devices.yml')
  Configuration.read_configuration(Configuration.data_directory+'/config/pipelines.yml')
  
  # Verify that all required configuration options are set
  Configuration.process_configuration()

def _setup_logs():
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
  logging.info("Startup: Starting the hardware manager.")
  logging.info("Startup: Setup the logging system.")
