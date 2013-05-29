# Import required modules
import logging
from twisted.internet import defer
from twisted.trial import unittest
from hwm.sessions import schedule, session
from hwm.core.configuration import *
from hwm.hardware.pipelines import pipeline
from hwm.hardware.devices import manager as device_manager
from hwm.hardware.devices.drivers import driver
from hwm.command import parser, command
from hwm.command.handlers import system as command_handler
from hwm.network.security import permissions
from pkg_resources import Requirement, resource_filename

class TestSession(unittest.TestCase):
  """ This test suite is used to test the functionality of the Session class, which is used to represent user hardware
  pipeline reservations.
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
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None
    
    # Reset the other resource references
    self.device_manager = None
    self.command_parser = None

  def test_session_startup_pipeline_in_use(self):
    """ Makes sure that the Session class responds appropriately when a session's hardware pipeline can't be reserved.
    """

    # First create a valid test pipeline and immediately lock it
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)
    test_pipeline.reserve_pipeline()

    # Define a callback to check the results of the session start procedure
    def check_results(session_start_failure):
      # Check if the correct error was generated (caused by a locked pipeline)
      self.assertTrue(isinstance(session_start_failure.value, pipeline.PipelineInUse))

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with (RES.2)
      test_reservation_config = None
      for temp_reservation in reservation_schedule['reservations']:
        if temp_reservation['reservation_id'] == 'RES.2':
          test_reservation_config = temp_reservation
          break

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Start the session
      session_start_deferred = test_session.start_session()
      session_start_deferred.addErrback(check_results)

      return session_start_deferred

    # Now load up a test schedule to work with
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_valid.json')
    schedule_update_deferred = schedule_manager.update_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_session_startup_pipeline_setup_errors(self):
    """ Tests that the Session class correctly handles fatal pipeline setup errors when starting a new session.
    """

    # First create a pipeline that contains invalid pipeline setup commands (to force an error)
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[2], self.device_manager, self.command_parser)

    # Define a callback to check the results of the session start procedure
    def check_results(session_start_failure):
      # Check if the correct error was generated (caused by a failed pipeline setup command)
      self.assertTrue(isinstance(session_start_failure.value, parser.CommandFailed))

      # Make sure that the pipeline was freed after the error
      self.assertTrue(not test_pipeline.in_use)
      for temp_device in test_pipeline.devices:
        # Try to lock the devices, if this fails then something wasn't unlocked correctly
        test_pipeline.devices[temp_device].reserve_device()

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with (RES.5)
      test_reservation_config = None
      for temp_reservation in reservation_schedule['reservations']:
        if temp_reservation['reservation_id'] == 'RES.5':
          test_reservation_config = temp_reservation
          break

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Start the session
      session_start_deferred = test_session.start_session()
      session_start_deferred.addErrback(check_results)

      return session_start_deferred

    # Now load up a test schedule to work with
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_valid.json')
    schedule_update_deferred = schedule_manager.update_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_session_startup_no_session_setup_commands(self):
    """ Tests that the Session class can correctly start a session that doesn't specify any setup commands.
    """

    # First create a pipeline to run the session on
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Define a callback to check the results of the session start procedure
    def check_results(session_start_results):
      self.assertEqual(session_start_results, None)

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with (RES.3)
      test_reservation_config = None
      for temp_reservation in reservation_schedule['reservations']:
        if temp_reservation['reservation_id'] == 'RES.3':
          test_reservation_config = temp_reservation
          break

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Start the session
      session_start_deferred = test_session.start_session()
      session_start_deferred.addCallback(check_results)

      return session_start_deferred

    # Now load up a test schedule to work with
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_valid.json')
    schedule_update_deferred = schedule_manager.update_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_session_startup_setup_commands_mixed_success(self):
    """ Tests that the Session class can correctly start a session based on a reservation that specifies some valid, and
    invalid, session setup commands. Because session setup command errors are considered non-fatal, invalid commands 
    should still leave the session in a running state.
    """

    # First create a pipeline to run the session on
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Define a callback to check the results of the session start procedure
    def check_results(session_start_results):
      # Make sure that the first setup command correctly executed
      self.assertTrue(session_start_results[0][0])
      self.assertTrue('timestamp' in session_start_results[0][1]['response']['result'])

      # Make sure that the second command failed as expected
      self.assertTrue(not session_start_results[1][0])
      self.assertTrue(isinstance(session_start_results[1][1].value, parser.CommandFailed))

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with (RES.2)
      test_reservation_config = None
      for temp_reservation in reservation_schedule['reservations']:
        if temp_reservation['reservation_id'] == 'RES.2':
          test_reservation_config = temp_reservation
          break

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Start the session
      session_start_deferred = test_session.start_session()
      session_start_deferred.addCallback(check_results)

      return session_start_deferred

    # Now load up a test schedule to work with
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_valid.json')
    schedule_update_deferred = schedule_manager.update_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}
