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
from txws import WebSocketFactory
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
from hwm.network.protocols import data, telemetry

def initialize():
  """ Initializes the Mercury2 Hardware Manager.
  
  This method sets up the hardware manager by initializing the required resources (e.g. pipeline manager, schedule 
  manager, configuration, etc.) and starting the event reactor. This is the main entry location for the hardware 
  manager.
  
  @note Any unhandled errors that occur before the event reactor is started will cause the program to exit.
  """
  
  # Set the default uncaught exception handler
  sys.excepthook = errors.uncaught_exception
  
  # Announce program start
  _announce_start()
  
  # Setup logging
  _setup_logs()
  
  # Setup the configuration
  _setup_configuration()
  
  # Initialize the main reservation schedule
  schedule_manager = _setup_schedule_manager()
  
  # Initialize the device manager
  device_manager = devices.DeviceManager()
  
  # Setup the command parser
  command_parser = _setup_command_system(device_manager)
  
  # Initialize the pipeline manager
  pipeline_manager = pipelines.PipelineManager(device_manager,
                                               command_parser)
  
  # Initialize the session coordinator
  session_coordinator = coordinator.SessionCoordinator(schedule_manager,
                                                       device_manager,
                                                       pipeline_manager,
                                                       command_parser)
  
  # Initialize the required network listeners
  _setup_network_listeners(command_parser, session_coordinator);
  
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

def initial_setup():
  """ Performs initial setup operations, such as copying default configuration files, if needed.
  
  This function performs various initial setup procedures such as copying the default configuration files, and setting 
  up the application system directories.

  @note This function only needs to be called once right after the hardware manager is installed. Any subsequent calls
        will only copy files that don't already exist on the system (to prevent custom configuration files from being 
        overridden).
  """
  
  # Copy the default configuration directory
  if not os.path.exists(Configuration.config_directory):
    default_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"resources/config")
    shutil.copytree(default_data_directory, Configuration.config_directory)
    if Configuration.verbose_startup:
      print ("- An existing Mercury2 HWM configuration directory was not found, copied defaults to: "+
             Configuration.config_directory)
  else:
    if Configuration.verbose_startup:
      print ("- Default configuration files not copied, an existing Mercury2 HWM configuration directory was found "+
             "at: "+Configuration.config_directory)

  # Setup the data directory
  if not os.path.exists(Configuration.data_directory):
    os.makedirs(Configuration.data_directory)
    os.makedirs(Configuration.data_directory+"permissions")
    os.makedirs(Configuration.data_directory+"schedules")
    os.makedirs(Configuration.data_directory+"stream_dumps")
    if Configuration.verbose_startup:
      print "- Existing Mercury2 HWM data directory not found, created at: "+Configuration.data_directory

  # Setup the log directory
  if not os.path.exists(Configuration.log_directory):
    os.makedirs(Configuration.log_directory)
    if Configuration.verbose_startup:
      print "- Existing Mercury2 HWM log directory not found, created at: "+Configuration.log_directory

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
  system_command_handlers = []
  system_command_handlers.append(system_command_handler.SystemCommandHandler('system'))
  if Configuration.get('offline-mode'):
    permission_manager = permissions.PermissionManager(Configuration.get('permissions-location-local'),
                                                       Configuration.get('permissions-update-period'))
  else:
    permission_manager = permissions.PermissionManager(Configuration.get('permissions-location-network'),
                                                       Configuration.get('permissions-update-period'))
  command_parser = command_parser_mod.CommandParser(system_command_handlers, permission_manager)
  
  return command_parser

def _setup_network_listeners(command_parser, session_coordinator):
  """ Initializes the various network listeners used by the hardware manager.
  
  This method initializes the network listeners required to accept ground station commands and relay pipeline data 
  streams.
  
  @param command_parser       An instance of CommandParser which will be used to handle commands received over the 
                              network.
  @param session_coordinator  A SessionCoordinator instance that will be passed to the pipeline protocol factories which
                              will allow them to associate connections with existing sessions. 
  """
    
  # Create a TLS context factory for the various listeners
  tls_context_factory = verification.create_tls_context_factory()
  
  # Setup the command listener
  command_factory = Site(command_connection.CommandResource(command_parser))
  reactor.listenSSL(Configuration.get('command-port'),
                    command_factory,
                    tls_context_factory)

  # Setup the pipeline data & telemetry stream listeners
  pipeline_data_factory = data.PipelineDataFactory(session_coordinator)
  reactor.listenSSL(Configuration.get('pipeline-data-port'),
                    pipeline_data_factory,
                    tls_context_factory)
  pipeline_telemetry_factory = telemetry.PipelineTelemetryFactory(session_coordinator)
  reactor.listenSSL(Configuration.get('pipeline-telemetry-port'),
                    WebSocketFactory(pipeline_telemetry_factory), 
                    tls_context_factory)

def _setup_configuration():
  """ Sets up the HWM configuration class.
  
  This function initializes the HWM configuration class (a singleton) by loading the required configuration files into
  it and validating the loaded configuration against the configuration schema (which defines which options are required
  and any formatting constraints).

  @throws May pass on ConfigInvalid exceptions if the loaded configuration set is invalid or incomplete.
  """
  
  # Read the configuration files
  Configuration.read_configuration(Configuration.config_directory+'configuration.yml')
  Configuration.read_configuration(Configuration.config_directory+'devices.yml')
  Configuration.read_configuration(Configuration.config_directory+'pipelines.yml')
  
  # Verify that all required configuration options are set
  Configuration.validate_configuration()

def _setup_logs():
  """Sets up the logger."""
  
  # Configure the logger
  logging.basicConfig(filename=Configuration.log_directory+'hardware_manager.log',
                      format='%(asctime)s - %(levelname)s - %(message)s',
                      datefmt='%m/%d/%Y %H:%M:%S',
                      level=logging.DEBUG)
  
  # Announce the logging system setup
  if Configuration.verbose_startup:
    print "- Setting up the logging system."
  
  # Log the program start
  logging.info("Startup: Starting the hardware manager.")
  logging.info("Startup: Setup the logging system.")
