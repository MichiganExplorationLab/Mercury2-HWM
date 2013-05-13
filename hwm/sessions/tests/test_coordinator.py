# Import required modules
from twisted.trial import unittest
from hwm.core.configuration import *
from hwm.sessions import schedule, coordinator
from hwm.hardware.pipelines import manager as pipeline_manager, pipeline
from hwm.hardware.devices import manager as device_manager
from hwm.command import parser
from hwm.command.handlers import system as command_handler
from hwm.network.security import permissions
from pkg_resources import Requirement, resource_filename

class TestCoordinator(unittest.TestCase):
  """
  This test suite tests the functionality of the session coordinator.
  """
  
  def setUp(self):
    # Set a local reference to Configuration (how other modules should typically access Config)
    self.config = Configuration
    self.config.verbose_startup = False
    
    # Set the source data directory
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    
    # Create a valid command parser and device manager for testing
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_valid.yml')
    self.device_manager = device_manager.DeviceManager()
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json', 3600)
    self.command_parser = parser.CommandParser({'system': command_handler.SystemCommandHandler()}, permission_manager)
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self.config.options = {}
    self.config.user_options = {}
    
    # Reset the configuration reference
    self.config = None
    
    # Reset the other resource references
    self.device_manager = None
    self.command_parser = None
  
  def test_schedule_update(self):
    """This test checks that the session coordinator can correctly instruct the schedule manager to update its schedule.
    """
    
    # Load in a test configuration & set defaults
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    self.config._set_default_configuration()
    
    # Setup the pipeline manager
    test_pipelines = pipeline_manager.PipelineManager(self.device_manager, self.command_parser)
    
    # Setup the schedule manager
    test_schedule = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_valid.json')
    
    # Initialize the session coordinator instance
    session_coordinator = coordinator.SessionCoordinator(test_schedule, None, test_pipelines)
    
    # Define an inline callback to resume execution after the schedule has been updates
    def continue_test(loaded_schedule):
      # Verify that schedule's last update time has been updated. It is initialized to 0, so if the _update_schedule() 
      # function worked as intended then it'll be some integer > 0.
      self.assertTrue((test_schedule.last_updated > 0), "The session coordinator did not update the schedule correctly.")
    
    # Instruct the session manager to update the schedule
    schedule_update_deferred = session_coordinator._update_schedule()
    schedule_update_deferred.addCallback(continue_test)
    
    return schedule_update_deferred
  
  def test_active_reservation_session_creation(self):
    """This test verifies that the session coordinator can correctly create (and skip) usage sessions from the 
    reservation schedule.
    """
    
    # Load in a test configuration & set defaults
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    self.config._set_default_configuration()
    
    # Setup the pipeline manager
    test_pipelines = pipeline_manager.PipelineManager(self.device_manager, self.command_parser)
    
    # Setup the schedule manager
    test_schedule = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_valid.json')
    
    # Initialize the session coordinator
    session_coordinator = coordinator.SessionCoordinator(test_schedule, None, test_pipelines)
    
    # Define an inline callback to resume execution after the schedule has been loaded
    def continue_test(loaded_schedule):
      # Look for active reservations and create associated sessions
      session_coordinator._check_for_new_reservations()
      
      # Verify that either of the active reservations are in the session list
      self.assertTrue(('RES.2' in session_coordinator.active_sessions) or ('RES.3' in session_coordinator.active_sessions), "An active test reservation was not found in the session manager.")
      
      # Verify that RES.2 and RES.3 are not both in the session list (they use the same pipeline at the same time so one
      # must not be included.
      self.assertTrue(('RES.2' in session_coordinator.active_sessions) != ('RES.3' in session_coordinator.active_sessions), "Two sessions were allowed to share the same pipeline at the same time.")
      
      # Verify that RES.4 doesn't get added (uses an invalid pipeline)
      self.assertTrue('RES.4' not in session_coordinator.active_sessions, "A reservation that uses an invalid pipeline is in the session list.")
      
      # Verify that the expired reservation was not added
      self.assertTrue(('RES.1' not in session_coordinator.active_sessions), "An expired reservation was found in the session manager.")
      
      # Attempt to reserve a pipeline that RES.2 or RES.3 is using
      self.assertRaises(pipeline.PipelineInUse, test_pipelines.pipelines['test_pipeline'].reserve_pipeline)
    
    # Update the schedule
    schedule_update_deferred = test_schedule.update_schedule()
    schedule_update_deferred.addCallback(continue_test)
    
    return schedule_update_deferred
