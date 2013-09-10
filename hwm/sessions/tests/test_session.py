# Import required modules
import logging, time
from twisted.internet import defer
from twisted.trial import unittest
from mock import MagicMock
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
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    self.device_manager = device_manager.DeviceManager()
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json', 3600)
    self.command_parser = parser.CommandParser([command_handler.SystemCommandHandler('system')], permission_manager)
    
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

  def test_writing_to_telemetry_protocol(self):
    """ Tests that the Session class can write telemetry data passed to it to its registered telemetry protocols. 
    """

    # First create a test pipeline
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with
      test_reservation_config = self._load_reservation_config(reservation_schedule, 'RES.2')

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Create some mock telemetry protocols and register them with the session
      test_telem_protocol = MagicMock()
      test_telem_protocol_2 = MagicMock()
      test_session.register_telemetry_protocol(test_telem_protocol)
      test_session.register_telemetry_protocol(test_telem_protocol_2)

      # Write a test telemetry datum and verify that the protocols were correctly called
      test_timestamp = int(time.time())
      test_session.write_telemetry("session_test", "test_stream", test_timestamp, "waffles", test_header=True)
      test_telem_protocol.write_telemetry.assert_called_once_with("session_test", "test_stream", test_timestamp, 
                                                                  "waffles", binary=False, test_header=True)
      test_telem_protocol_2.write_telemetry.assert_called_once_with("session_test", "test_stream", test_timestamp,
                                                                    "waffles", binary=False, test_header=True)

    # Now load up a test schedule to work with
    schedule_update_deferred = self._load_test_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_writing_to_output_protocol(self):
    """ This test verifies that the Session class can correctly pass pipeline output from the Pipeline class to its 
    registered data protocols.
    """

    # First create a test pipeline
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with
      test_reservation_config = self._load_reservation_config(reservation_schedule, 'RES.2')

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Create some mock data protocols and register them with the session
      test_data_protocol = MagicMock()
      test_data_protocol_2 = MagicMock()
      test_session.register_data_protocol(test_data_protocol)
      test_session.register_data_protocol(test_data_protocol_2)

      # Write some output data and verify that it was passed to the registered streams
      test_session.write_output("waffles")
      test_data_protocol.write_output.assert_called_once_with("waffles")
      test_data_protocol_2.write_output.assert_called_once_with("waffles")

    # Now load up a test schedule to work with
    schedule_update_deferred = self._load_test_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_writing_to_input_stream(self):
    """ Checks that the Session class can correctly write input data that it receives to its associated pipeline.
    """

    # First create a valid test pipeline and mock its write_to_pipeline() method
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)
    test_pipeline.write = MagicMock()

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with
      test_reservation_config = self._load_reservation_config(reservation_schedule, 'RES.2')

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Write data to the session and verify that it correctly handed it off to the pipeline
      test_session.write("waffles")
      test_pipeline.write.assert_called_once_with("waffles")

    # Now load up a test schedule to work with
    schedule_update_deferred = self._load_test_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_telemetry_protocol_registration(self):
    """ Verifies that the Session class can correctly register telemetry protocols. The Session class uses telemetry
    protocols to pass pipeline telemetry data to the end user.
    """

    # First create a valid test pipeline
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with
      test_reservation_config = self._load_reservation_config(reservation_schedule, 'RES.2')

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Create and register some mock telemetry protocols
      test_telem_protocol = MagicMock()
      test_telem_protocol_2 = MagicMock()
      test_session.register_telemetry_protocol(test_telem_protocol)
      test_session.register_telemetry_protocol(test_telem_protocol_2)

      # Try to register the same protocol twice
      self.assertRaises(session.ProtocolAlreadyRegistered, test_session.register_telemetry_protocol, test_telem_protocol)

      # Make sure the protocols were added successfully
      self.assertEqual(test_session.telemetry_protocols[0], test_telem_protocol)
      self.assertEqual(test_session.telemetry_protocols[1], test_telem_protocol_2)

    # Now load up a test schedule to work with
    schedule_update_deferred = self._load_test_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_data_protocol_registration(self):
    """ Verifies that the Session class can correctly register data protocols. The Session class uses these data
    protocols to pass the primary pipeline output stream to the end user.
    """

    # First create a valid test pipeline
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with
      test_reservation_config = self._load_reservation_config(reservation_schedule, 'RES.2')

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Create and register some mock data protocols
      test_data_protocol = MagicMock()
      test_data_protocol_2 = MagicMock()
      test_session.register_data_protocol(test_data_protocol)
      test_session.register_data_protocol(test_data_protocol_2)

      # Try to register the same protocol twice
      self.assertRaises(session.ProtocolAlreadyRegistered, test_session.register_data_protocol, test_data_protocol)

      # Make sure both protocols were registered successfully
      self.assertEqual(test_session.data_protocols[0], test_data_protocol)
      self.assertEqual(test_session.data_protocols[1], test_data_protocol_2)

    # Now load up a test schedule to work with
    schedule_update_deferred = self._load_test_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_session_startup_pipeline_in_use(self):
    """ Makes sure that the Session class responds appropriately when a session's hardware pipeline can't be reserved.
    """

    # First create a valid test pipeline and immediately lock it
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)
    test_pipeline.reserve_pipeline()

    # Define a callback to check the results of the session start procedure
    def check_results(session_start_failure):
      # Check if the correct error was generated (caused by a locked pipeline)
      self.assertTrue(isinstance(session_start_failure.value, pipeline.PipelineInUse))

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with
      test_reservation_config = self._load_reservation_config(reservation_schedule, 'RES.2')

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Start the session
      session_start_deferred = test_session.start_session()
      session_start_deferred.addErrback(check_results)

      return session_start_deferred

    # Now load up a test schedule to work with
    schedule_update_deferred = self._load_test_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_session_startup_pipeline_setup_errors(self):
    """ Tests that the Session class correctly handles fatal pipeline setup errors when starting a new session.
    """

    # First create a pipeline that contains invalid pipeline setup commands (to force an error)
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[2], self.device_manager, self.command_parser)

    # Define a callback to check the results of the session start procedure
    def check_results(session_start_failure, test_session):
      # Check if the correct error was generated (caused by a failed pipeline setup command)
      self.assertTrue(isinstance(session_start_failure.value, parser.CommandFailed))

      # Make sure the session is not active
      self.assertTrue(not test_session.is_active)

      # Make sure that the pipeline was freed after the error
      self.assertTrue(not test_pipeline.is_active)
      for temp_device in test_pipeline.devices:
        # Try to lock the devices, if this fails then something wasn't unlocked correctly
        test_pipeline.devices[temp_device].reserve_device()

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with
      test_reservation_config = self._load_reservation_config(reservation_schedule, 'RES.5')

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Start the session
      session_start_deferred = test_session.start_session()
      session_start_deferred.addErrback(check_results, test_session)

      return session_start_deferred

    # Now load up a test schedule to work with
    schedule_update_deferred = self._load_test_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_session_startup_no_session_setup_commands(self):
    """ Tests that the Session class can correctly start a session that doesn't specify any setup commands.
    """

    # First create a pipeline to run the session on
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Define a callback to check the results of the session start procedure
    def check_results(session_start_results, test_session):
      self.assertEqual(session_start_results, None)

      # Make sure the session is active
      self.assertTrue(test_session.is_active)

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Find the reservation that we want to test with
      test_reservation_config = self._load_reservation_config(reservation_schedule, 'RES.3')

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Start the session
      session_start_deferred = test_session.start_session()
      session_start_deferred.addCallback(check_results, test_session)

      return session_start_deferred

    # Now load up a test schedule to work with
    schedule_update_deferred = self._load_test_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_session_startup_setup_commands_mixed_success(self):
    """ Tests that the Session class can correctly start a session based on a reservation that specifies some valid, and
    invalid, session setup commands. Because session setup command errors are considered non-fatal, invalid commands 
    should still leave the session in a running state. In addition, this test also verifies that the session correctly
    registers itself with its pipeline (which occurs right before the session setup commands are executed).
    """

    # First create a pipeline to run the session on
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Define a callback to check the results of the session start procedure
    def check_results(session_start_results, test_session):
      # Make sure that the session registered itself with its pipeline
      self.assertTrue(test_pipeline.current_session is test_session)

      # Make sure that the first setup command correctly executed
      self.assertTrue(session_start_results[0][0])
      self.assertTrue('timestamp' in session_start_results[0][1]['response']['result'])

      # Make sure that the second command failed as expected
      self.assertTrue(not session_start_results[1][0])
      self.assertTrue(isinstance(session_start_results[1][1].value, parser.CommandFailed))

      # Make sure the session is active
      self.assertTrue(test_session.is_active)

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Load the reservation that we want to test with
      test_reservation_config = self._load_reservation_config(reservation_schedule, 'RES.2')

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Start the session
      session_start_deferred = test_session.start_session()
      session_start_deferred.addCallback(check_results, test_session)

      return session_start_deferred

    # Now load up a test schedule to work with
    schedule_update_deferred = self._load_test_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def _load_test_schedule(self):
    """ Loads a valid test schedule and returns a deferred that will be fired once that schedule has been loaded and 
    parsed. This schedule is used to test the Session class.
    """

    # Load a valid test schedule
    schedule_manager = schedule.ScheduleManager(self.source_data_directory+'/sessions/tests/data/test_schedule_valid.json')
    schedule_update_deferred = schedule_manager.update_schedule()

    return schedule_update_deferred

  def _load_reservation_config(self, reservation_schedule, reservation_id):
    """ Returns the configuration dictionary for the specified reservation ID from the complete reservation schedule.
    This is used to pick out individual session configurations to test with.

    @throw Raises LookupError if the specified reservation ID can't be found in the reservation schedule.
    """

    # Parse out the specific reservation configuration
    test_reservation_config = None
    for temp_reservation in reservation_schedule['reservations']:
      if temp_reservation['reservation_id'] == reservation_id:
        test_reservation_config = temp_reservation
        return test_reservation_config

    raise LookupError("Specified reservation '"+reservation_id+"' was not found in the provided reservation schedule.")

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}
