""" @package hwm.core.initialization
Initializes the Hardware Manager application.
 
This module contains the methods responsible for initializing the Hardware Manager. This entails setting up the 
application state and starting the reactor loop.
"""

# Import the required modules
import logging, sys, shutil, os
from OpenSSL import SSL
from twisted.internet import reactor, ssl
from twisted.internet.task import LoopingCall
from twisted.web.server import Site
from pkg_resources import Requirement, resource_filename
from configuration import Configuration
from hwm.core import errors
from hwm.sessions import coordinator, schedule
from hwm.hardware.pipelines import manager
from hwm.network.command import parser as command_parser_system, connection as command_connection
from hwm.network.command.handlers import system as command_handler_system
from hwm.network.security import verification

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
  
  # Initialize the schedule coordinator
  if Configuration.get('offline-mode'):
    schedule_manager = schedule.ScheduleManager(Configuration.data_directory+Configuration.get('schedule-location-local'))
  else:
    schedule_manager = schedule.ScheduleManager(Configuration.get('schedule-location-network'))
  
  # Initialize the pipeline manager
  pipeline_manager = manager.PipelineManager()
  
  # Initialize the session coordinator
  session_coordinator = coordinator.SessionCoordinator(schedule_manager, pipeline_manager)
  
  # Initialize the command and telemetry network listeners
  _setup_network_listeners();
  
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
  """Checks for the presence of required data file directories.
  
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

def _setup_network_listeners():
  """ Initializes the various network listeners used by the hardware manager.
  
  This method initializes the network listeners required to accept ground station commands and relay ground station 
  data streams.
  """
  
  # Initialize the system command handlers
  system_command_handler = command_handler_system.SystemCommandHandler()
  
  # Initialize the command parser
  command_parser = command_parser_system.CommandParser(system_command_handler)
  
  # Create an SSL context for the server
  server_context_factory = ssl.DefaultOpenSSLContextFactory(Configuration.get('ssl-private-key-location'), Configuration.get('ssl-public-cert-location'))
  server_context = server_context_factory.getContext()
  server_context.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT, verification.authentication_callback)
  
  # Create a new Site factory
  command_factory = Site(command_connection.CommandResource(command_parser))
  
  # Create the listeners
  reactor.listenSSL(Configuration.get('network-command-port'), command_factory, server_context_factory)

def _setup_configuration():
  """Sets up the configuration object.
  
  This function sets up the configuration object (a singleton) by loading the required configuration files, validating 
  the required options, and populating the unspecified default options.
  """
  
  # Read the configuration files
  Configuration.read_configuration(Configuration.data_directory+'/config/configuration.yml')
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
