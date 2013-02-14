# Import required modules
from twisted.trial import unittest
from hwm.core.configuration import *
from hwm.sessions import schedule, coordinator
from hwm.hardware.pipelines import manager
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
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self.config.options = {}
    self.config.user_options = {}
    
    # Reset the configuration reference
    self.config = None
  
  def test_session_creation(self):
    """This test verifies that the session coordinator can correctly create (and skip) usage sessions from the 
    reservation schedule.
    """
    
    # Setup forward definitions
    test_schedule = None
    
    # Load in a test configuration & set defaults
    self.config.read_configuration(self.source_data_directory+'/sessions/tests/data/test_coordinator_config.yml')
    self.config._set_default_configuration()
    
    # Setup the pipeline manager
    test_pipelines = manager.PipelineManager()
    
    # Define an inline callback to resume execution after the schedule has been loaded
    def continue_test(loaded_schedule):
      # Initialize the session coordinator
      session_coordinator = coordinator.SessionCoordinator(test_schedule, test_pipelines)
      
      # Look for active reservations and create associated sessions
      session_coordinator.coordinate()
      
      # Verify that the correct reservation was activated
      self.assertTrue(('RES.2' in session_coordinator.active_sessions), "The active test reservation was not found in the session manager.")
      
      # Verify that the expired reservation was not added
      self.assertTrue(('RES.1' not in session_coordinator.active_sessions), "An expired reservation was found in the session manager.")
    
    # Setup the schedule manager & load the schedule
    test_schedule = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_coordinator_schedule.json')
    schedule_update_deferred = test_schedule.update_schedule()
    schedule_update_deferred.addCallback(continue_test)
    
    return schedule_update_deferred
