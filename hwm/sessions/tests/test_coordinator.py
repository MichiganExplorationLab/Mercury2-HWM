# Import required modules
from twisted.trial import unittest
from hwm.core.configuration import *
from mock import MagicMock
from hwm.sessions import schedule, coordinator
from hwm.hardware.pipelines import manager as pipeline_manager, pipeline
from hwm.hardware.devices import manager as device_manager
from hwm.command import parser
from hwm.command.handlers import system as command_handler
from hwm.network.security import permissions
from pkg_resources import Requirement, resource_filename

class TestCoordinator(unittest.TestCase):
  """ This test suite tests the functionality of the SessionCoordinator class, which is responsible for setting up new
  sessions based on the reservation schedule and managing other periodic tasks.
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
    self.command_parser = parser.CommandParser([command_handler.SystemCommandHandler('system')], permission_manager)
    self.command_parser.pipeline_manager = MagicMock()
    
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
    """ This test checks that the session coordinator can instruct the schedule manager to update its schedule.
    """
    
    # Load in some valid configuration and set the defaults using validate_configuration()
    self.config.read_configuration(self.source_data_directory+'/core/tests/data/test_config_basic.yml')
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    self.config.validate_configuration()
    
    # Setup the pipeline manager
    test_pipelines = pipeline_manager.PipelineManager(self.device_manager, self.command_parser)
    
    # Setup the schedule manager
    test_schedule = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_valid.json')
    
    # Initialize the session coordinator instance
    session_coordinator = coordinator.SessionCoordinator(test_schedule,
                                                         self.device_manager,
                                                         test_pipelines,
                                                         self.command_parser)
    
    # Define an inline callback to resume execution after the schedule has been updates
    def continue_test(loaded_schedule):
      # Verify that schedule's last update time has been updated. It is initialized to 0, so if the _update_schedule() 
      # function worked as intended then it'll be some integer > 0.
      self.assertTrue((test_schedule.last_updated > 0), "The session coordinator did not update the schedule correctly.")
      self.assertTrue(len(test_schedule.schedule) > 0, "The session coordinator did not update the schedule correctly.")
    
    # Instruct the session manager to update the schedule
    schedule_update_deferred = session_coordinator._update_schedule()
    schedule_update_deferred.addCallback(continue_test)
    
    return schedule_update_deferred
  
  def test_reservation_session_creation(self):
    """ This test verifies that the session coordinator can correctly create usage sessions from the reservation 
    schedule. It also tests that it correctly handles conflicting reservations. That is, reservations that concurrently
    use the same pipeline or hardware devices. Finally, it also tests that the session coordinator can return a list of
    a given user's active sessions.
    """
    
    # Load in some valid configuration and set the defaults using validate_configuration()
    self.config.read_configuration(self.source_data_directory+'/core/tests/data/test_config_basic.yml')
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    self.config.validate_configuration()
    
    # Setup the pipeline manager
    test_pipelines = pipeline_manager.PipelineManager(self.device_manager, self.command_parser)
    
    # Setup the schedule manager
    test_schedule = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_valid.json')
    
    # Initialize the session coordinator
    session_coordinator = coordinator.SessionCoordinator(test_schedule,
                                                         self.device_manager,
                                                         test_pipelines,
                                                         self.command_parser)
    
    # Define an inline callback to resume execution after the schedule has been loaded
    def continue_test(loaded_schedule):
      # Try loading the user's reservations before they have been activated
      active_sessions = session_coordinator.load_user_sessions(1)
      self.assertTrue(len(active_sessions)==0)

      # Look for active reservations and create associated sessions
      session_coordinator._check_for_new_reservations()
      
      # Make sure that RES.5 failed (it uses a pipeline that contains errors in its setup commands)
      self.assertTrue('RES.5' in session_coordinator.closed_sessions and
                      'RES.5' not in session_coordinator.active_sessions,
                      "RES.5, which uses a pipeline that contains fatal setup command errors, was not marked as "+
                      "closed as expected.")

      # Verify that either RES.2 or RES.3 is active (these reservations use the same pipeline at the same time, so only
      # one can be active at a time)
      self.assertTrue((('RES.2' in session_coordinator.active_sessions) and ('RES.3' in session_coordinator.closed_sessions)) or
                      (('RES.2' in session_coordinator.closed_sessions) and ('RES.3' in session_coordinator.active_sessions)),
                      "The conflicting active reservations (RES.2 or RES.3) defined in the test schedule aren't where "+
                      "they should be (one should be active and one should be closed due to the conflict error).")
      
      # Verify that RES.4 didn't get started (uses an invalid pipeline)
      self.assertTrue(('RES.4' not in session_coordinator.active_sessions) and
                      ('RES.4' in session_coordinator.closed_sessions),
                      "RES.4, which uses a non-existent pipeline, was not marked closed as expected.")
      
      # Verify that the expired reservation (RES.1) was not started
      self.assertTrue(('RES.1' not in session_coordinator.active_sessions),
                      "RES.1, which is expired, was started when it should have been ignored.")
      
      # Attempt to reserve the pipeline that RES.2 or RES.3 is using (tests that it was correctly locked)
      self.assertRaises(pipeline.PipelineInUse, test_pipelines.pipelines['test_pipeline'].reserve_pipeline)

      # Load test_admin's active sessions (either RES.2 or RES.3)
      active_sessions = session_coordinator.load_user_sessions(1)
      self.assertTrue(len(active_sessions)==1)
      self.assertTrue(active_sessions[0].id=="RES.2" or active_sessions[0].id=="RES.3")
    
    # Update the schedule to load in the reservations
    schedule_update_deferred = test_schedule.update_schedule()
    schedule_update_deferred.addCallback(continue_test)
    
    return schedule_update_deferred
