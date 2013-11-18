# Import required modules
import logging, time
from twisted.trial import unittest
from mock import MagicMock
from pkg_resources import Requirement, resource_filename
from hwm.core.configuration import *
from hwm.hardware.pipelines import pipeline, manager as pipeline_manager
from hwm.hardware.devices import manager as device_manager
from hwm.hardware.devices.drivers import driver
from hwm.command import parser, command
from hwm.command.handlers import system as command_handler
from hwm.network.security import permissions
from hwm.sessions import schedule, session

class TestPipeline(unittest.TestCase):
  """ This test suite is used to test the functionality of the Pipeline class, which is used to represent and provide
  access to hardware pipelines.
  """
  
  def setUp(self):
    # Set a local reference to Configuration (how other modules should typically access Config)
    self.config = Configuration
    self.config.verbose_startup = False
    
    # Set the source data directory
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    
    # Create a valid command parser and device manager for testing
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_valid.json', 3600)
    self.command_parser = parser.CommandParser([command_handler.SystemCommandHandler('system')], permission_manager)
    self._reset_device_manager(self.command_parser)
    self.pipeline_manager = MagicMock()
    self.command_parser.pipeline_manager = self.pipeline_manager
    
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
    self.pipeline_manager = None

  def test_loading_pipeline_device(self):
    """ Tests that the pipeline can return references to its devices.
    """

    # Create a test pipeline to work with
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Load a device
    temp_device = test_pipeline.get_device("test_device4")
    self.assertEqual(temp_device.id, "test_device4")

    # Try loading a non-existent device
    self.assertRaises(device_manager.DeviceNotFound, test_pipeline.get_device, "non-existent-device")

  def test_writing_pipeline_output(self):
    """ Checks that the Pipeline class can pass pipeline output to its currently registered session. The pipeline's 
    registered output device will normally use Pipeline.write_output() to pass its output to the pipeline (and in turn 
    to the session).
    """

    # Create a test pipeline to work with
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Create a mock session and register it with the Pipeline
    test_session = MagicMock()
    test_pipeline.register_session(test_session)

    # Write some output data to the pipeline and see if it was passed to the session
    test_pipeline.write_output("waffles")
    test_session.write_output.assert_called_once_with("waffles")

    # Unregister the session and try again (should have no effect)
    test_pipeline.current_session = None
    test_pipeline.write_output("waffles")

  def test_writing_telemetry_datum(self):
    """ This test verifies that the Pipeline class can correctly relay telemetry data to it's currently registered
    session. Drivers use Pipeline.write_telemetry() to send additional data (i.e. separate from the main pipeline
    datastream) and state to the Pipeline (and in turn to the Session).
    """

    # Create a test pipeline to work with
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Create a mock session and register it with the Pipeline
    test_session = MagicMock()
    test_pipeline.register_session(test_session)

    # Write a telemetry datum point and make sure it was passed to the session
    test_timestamp = int(time.time())
    test_pipeline.write_telemetry("pipeline_test", "test_stream", test_timestamp, "waffles", binary=True,
                                  test_header=True)
    test_session.write_telemetry.assert_called_once_with("pipeline_test", "test_stream", test_timestamp, "waffles",
                                                         binary=True, test_header=True)

    # Unregister the session and try writing telemetry data (should have no effect)
    test_pipeline.current_session = None
    test_pipeline.write_telemetry("pipeline_test", "test_stream", test_timestamp, "waffles", test_header=True)
    test_session.write_telemetry.assert_called_once_with("pipeline_test", "test_stream", test_timestamp, "waffles",
                                                         binary=True, test_header=True)

  def test_writing_to_pipeline(self):
    """ Verifies that upon receiving data from the session, the pipeline correctly routes it to its input device.
    """

    # Create a test pipeline to work with
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Mock the input device's write_to_device method
    test_pipeline.input_device.write = MagicMock()

    # Write to the pipeline and make sure it made it to the driver
    test_pipeline.write("waffles")
    test_pipeline.input_device.write.assert_called_once_with("waffles")

    # Remove the input device and try writing to the pipeline again (call should have no effect)
    old_input_device = test_pipeline.input_device
    test_pipeline.input_device = None
    test_pipeline.write("waffles")
    old_input_device.write.assert_called_once_with("waffles")

  def test_prepare_for_session_error(self):
    """ Tests that the prepare_for_session() method returns a failed deferred if one of its devices throws an 
    exception.
    """

    # Create a mock method that will raise an error
    def mock_prepare_for_session(session_pipeline):
      raise TestPipelineError

    # Create a test pipeline to work with and replace its device's prepare_for_session() methods with mock methods
    test_session = MagicMock()
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)
    test_pipeline.devices["test_device4"].prepare_for_session = mock_prepare_for_session

    # Define a callback to test the error
    def check_results(setup_error):
      self.assertTrue(isinstance(setup_error.value, TestPipelineError))

    # Call the pipeline's prepare_for_session() method and make sure it calls it on all of its devices
    test_deferred = test_pipeline.prepare_for_session(test_session)
    test_deferred.addErrback(check_results)

    return test_deferred
  
  def test_prepare_for_session(self):
    """ Verifies that the pipeline calls the prepare_for_session() method on each of its devices when asked, which is 
    used to give drivers an opportunity to load and setup services before a new session begins.
    """

    # Create a test pipeline to work with and replace its device's prepare_for_session() methods with mock methods
    test_session = MagicMock()
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)
    for device_id in test_pipeline.devices:
      test_pipeline.devices[device_id].prepare_for_session = MagicMock()

    # Call the pipeline's prepare_for_session() method and make sure it calls it on all of its devices
    test_deferred = test_pipeline.prepare_for_session(test_session)
    for device_id in test_pipeline.devices:
      test_pipeline.devices[device_id].prepare_for_session.assert_called_once_with(test_pipeline)

    return test_deferred

  def test_session_cleanup(self):
    """ This test makes sure that the pipeline can correctly clean itself up after the session that is using the 
    pipeline expires.
    """

    # Create a pipeline to test with
    test_session = MagicMock()
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)
    test_pipeline._set_active_services = MagicMock()
    for device_id in test_pipeline.devices:
      test_pipeline.devices[device_id].cleanup_after_session = MagicMock()

    def continue_test(session_prep_results):
      # Clean up after the session and verify results
      test_pipeline.cleanup_after_session()

      self.assertEqual(test_pipeline.produce_telemetry, False)
      self.assertTrue(len(test_pipeline.active_services) == 0)
      self.assertTrue(test_pipeline.current_session is None)
      for device_id in test_pipeline.devices:
        test_pipeline.devices[device_id].cleanup_after_session.assert_called_once_with()

    test_deferred = test_pipeline.prepare_for_session(test_session)
    test_deferred.addCallback(continue_test)

    return test_deferred

  def test_session_cleanup_error(self):
    """ This test makes sure that the pipeline can correctly handle errors when attempted to clean up an expired
    session.
    """

    # Create a mock cleanup method that throws an error
    def mock_cleanup_after_session():
      raise TypeError("Ya blew it.")

    # Create a pipeline to test with
    test_session = MagicMock()
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)
    test_pipeline._set_active_services = MagicMock()
    test_pipeline.devices["test_device"].cleanup_after_session = MagicMock()
    test_pipeline.devices["test_device4"].cleanup_after_session = MagicMock()
    test_pipeline.devices["test_device2"].cleanup_after_session = mock_cleanup_after_session

    def continue_test(session_prep_results):
      # Clean up after the session to make sure the exception was caught and verify the other devices were cleaned up
      test_pipeline.cleanup_after_session()

      test_pipeline.devices["test_device4"].cleanup_after_session.assert_called_once_with()
      test_pipeline.devices["test_device"].cleanup_after_session.assert_called_once_with()

    test_deferred = test_pipeline.prepare_for_session(test_session)
    test_deferred.addCallback(continue_test)

    return test_deferred

  def test_service_activation_and_lookup(self):
    """ This tests that the service activation and lookup methods are working as expected. In order for a service to be 
    query-able, it must be active (as specified by the configuration for the session using the pipeline).
    """

    # Create a test pipeline to work with
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Create some mock services and register them with the pipeline
    test_tracker_service = MagicMock()
    test_tracker_service.id = "sgp4"
    test_tracker_service.type = "tracker"
    test_pipeline.register_service(test_tracker_service)
    test_logger_service = MagicMock()
    test_logger_service.id = "basic"
    test_logger_service.type = "logger"
    test_pipeline.register_service(test_logger_service)
    test_cornballer_service = MagicMock()
    test_cornballer_service.id = "deluxe"
    test_cornballer_service.type = "cornballer"
    test_pipeline.register_service(test_cornballer_service)

    # Define a callback to continue the test after the schedule has been loaded
    def continue_test(reservation_schedule):
      # Load a reservation that specifies some active services
      test_reservation_config = self._load_reservation_config(reservation_schedule, 'RES.5')

      # Create a new session
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)

      # Register the session with the pipeline; this will also activate the reservation's services
      test_pipeline.register_session(test_session)

      # Make sure the active services can be loaded
      self.assertTrue(test_pipeline.load_service("tracker") is test_tracker_service)
      self.assertTrue(test_pipeline.load_service("logger") is test_logger_service)
      self.assertRaises(pipeline.ServiceTypeNotFound, test_pipeline.load_service, "cornballer")

      # Add an unknown active service type to the reservation configuration and re-register it
      test_pipeline.current_session = None
      test_reservation_config['active_services']['nonexistent_type'] = "nonexistent_service"
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)
      self.assertRaises(pipeline.ServiceInvalid, test_pipeline.register_session, test_session)

      # Add an unknown active service ID to the reservation configuration and re-register it
      test_pipeline.current_session = None
      test_reservation_config['active_services'].pop("nonexistent_type", None)
      test_reservation_config['active_services']['tracker'] = "nonexistent_service"
      test_session = session.Session(test_reservation_config, test_pipeline, self.command_parser)
      self.assertRaises(pipeline.ServiceInvalid, test_pipeline.register_session, test_session)

    # Load up a test schedule to work with
    schedule_update_deferred = self._load_test_schedule()
    schedule_update_deferred.addCallback(continue_test)

    return schedule_update_deferred

  def test_service_registration(self):
    """ Verifies that the Pipeline class can correctly register services. The service registration feature allows
    devices to offer services or script access to other devices in the pipeline.
    """ 

    # Load the pipeline configuration and create a test pipeline
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)
    test_service_type = 'waffle'

    # Create and register a mock service
    test_service = MagicMock()
    test_service.id = 'test_service'
    test_service.type = test_service_type
    test_pipeline.register_service(test_service)
    self.assertTrue(test_pipeline.services[test_service_type]['test_service'] is test_service)

    # Create and register a mock service with the same type but a different ID
    test_service_2 = MagicMock()
    test_service_2.id = 'test_service_2'
    test_service_2.type = test_service_type
    test_pipeline.register_service(test_service_2)
    self.assertTrue(test_pipeline.services[test_service_type]['test_service_2'] is test_service_2)

    # Try to register a third service with the same type and ID as an earlier service
    test_service_3 = MagicMock()
    test_service_3.id = 'test_service'
    test_service_3.type = test_service_type
    self.assertRaises(pipeline.ServiceAlreadyRegistered, test_pipeline.register_service, test_service_3)

  def test_session_registration(self):
    """ Tests that the Pipeline class can correctly register sessions. The Pipeline class uses registered sessions to
    relay the pipeline telemetry and data streams to the end user. This test uses a mock session without any active 
    services specified so that Pipeline._set_active_services() will be skipped.
    """

    # Load the pipeline configuration and create a test pipeline
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Create and register a mock session (which won't have any active services)
    test_session = MagicMock()
    test_pipeline.register_session(test_session)

    # Make sure double registrations are disallowed
    test_session_2 = MagicMock()
    self.assertRaises(pipeline.SessionAlreadyRegistered, test_pipeline.register_session, test_session_2)

  def test_initialization_errors(self):
    """ Tests that the pipeline generates the correct errors during the initialization process.
    """

    # Load a pipeline configuration with duplicate devices in a pipeline
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_duplicate_devices.yml')
    self.assertRaises(pipeline.PipelineConfigInvalid, pipeline.Pipeline,
                    self.config.get('pipelines')[0],
                    self.device_manager,
                    self.command_parser)

    # Load a pipeline configuration that specifies a non-existent device
    self._reset_config_entries()
    self._reset_device_manager(self.command_parser)
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_invalid_device.yml')
    self.assertRaises(pipeline.PipelineConfigInvalid, pipeline.Pipeline,
                    self.config.get('pipelines')[1],
                    self.device_manager,
                    self.command_parser)

    # Load a pipeline configuration that specifies multiple output devices for a single pipeline
    self._reset_config_entries()
    self._reset_device_manager(self.command_parser)
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_multiple_output_devices.yml')
    self.assertRaises(pipeline.PipelineConfigInvalid, pipeline.Pipeline,
                    self.config.get('pipelines')[0],
                    self.device_manager,
                    self.command_parser)

  def test_setup_commands_none_specified(self):
    """ Tests that the Pipeline class behaves correctly when it doesn't have any configured setup commands.
    """

    # Load a pipeline configuration that contains a pipeline that doesn't specify any setup commands
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[1], self.device_manager, self.command_parser)

    # Define a callback to check the results of the setup command execution
    def check_results(setup_command_results):
      self.assertEqual(setup_command_results, None)

    # Try to run the setup commands
    setup_commands_deferred = test_pipeline.run_setup_commands(True)
    setup_commands_deferred.addCallback(check_results)

    return setup_commands_deferred

  def test_setup_commands_failed_device_command(self):
    """ Checks that the Pipeline class correctly responds to failed pipeline setup device commands.
    """

    # Load a pipeline configuration that contains an invalid setup command (which will generate an error when executed)
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[3], self.device_manager, self.command_parser)

    # Define a callback to check the results of the setup command execution
    def check_results(setup_command_failure):
      # Make sure that returned error is correct
      self.assertTrue(isinstance(setup_command_failure.value.subFailure.value, parser.CommandFailed))

    # Run the setup commands
    setup_commands_deferred = test_pipeline.run_setup_commands(True)
    setup_commands_deferred.addErrback(check_results)

    return setup_commands_deferred

  def test_setup_commands_successful(self):
    """ Checks that the Pipeline class can correctly run valid setup commands.
    """

    # Load a pipeline configuration that contains some device commands and setup the pipeline manager
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    self.pipeline_manager = pipeline_manager.PipelineManager(self.device_manager, self.command_parser)
    test_pipeline = self.pipeline_manager.get_pipeline("test_pipeline")

    # Define a callback to check the results of the setup command execution
    def check_results(setup_command_results):
      # Make sure that the correct command response is present for both pipeline setup commands
      self.assertTrue('timestamp' in setup_command_results[0]['response']['result'])
      self.assertTrue('device_timestamp' in setup_command_results[1]['response']['result'])

    # Run the setup commands
    setup_commands_deferred = test_pipeline.run_setup_commands(True)
    setup_commands_deferred.addCallback(check_results)

    return setup_commands_deferred

  def test_setup_commands_failed_system_command(self):
    """ Checks that the Pipeline class correctly responds to failed pipeline setup commands.
    """

    # Load a pipeline configuration that contains an invalid setup command (which will generate an error when executed)
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[2], self.device_manager, self.command_parser)

    # Define a callback to check the results of the setup command execution
    def check_results(setup_command_failure):
      # Make sure that returned error is correct
      self.assertTrue(isinstance(setup_command_failure.value.subFailure.value, parser.CommandFailed))

    # Run the setup commands
    setup_commands_deferred = test_pipeline.run_setup_commands(True)
    setup_commands_deferred.addErrback(check_results)

    return setup_commands_deferred

  def test_locking_successful(self):
    """ Verifies that the Pipeline class can correctly lock a pipeline and its associated hardware. It also verifies
    that the pipeline registers itself with its devices.
    """

    # Load a valid pipeline configuration
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[2], self.device_manager, self.command_parser)

    # Make sure the pipeline registered itself with its device (occurs in Pipeline._setup_pipeline())
    self.assertTrue(test_pipeline.output_device.associated_pipelines['test_pipeline3'] is test_pipeline)

    # Lock the pipeline
    test_pipeline.reserve_pipeline()

    # Try re-locking the pipeline
    self.assertRaises(pipeline.PipelineInUse, test_pipeline.reserve_pipeline)

    # Make sure the pipeline is active
    self.assertTrue(test_pipeline.is_active)

    # Make sure the devices were correctly locked
    for temp_device in test_pipeline.devices:
      self.assertRaises(driver.DeviceInUse, test_pipeline.devices[temp_device].reserve_device)

    # Unlock the pipeline and make sure that all of its devices were freed
    test_pipeline.free_pipeline()
    self.assertTrue(not test_pipeline.is_active)
    for temp_device in test_pipeline.devices:
      test_pipeline.devices[temp_device].reserve_device()

  def test_locking_failed_rollback(self):
    """ Verifies that, in the event of a pipeline locking conflict (i.e. the pipeline is free but a device it uses
    isn't), the Pipeline class correctly rolls back any hardware locks it may have acquired before the error occured.
    """

    # Load a valid pipeline configuration
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline_a = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)
    test_pipeline_b = pipeline.Pipeline(self.config.get('pipelines')[1], self.device_manager, self.command_parser)

    # Lock the first pipeline
    test_pipeline_a.reserve_pipeline()

    # Make sure the second pipeline can't be locked
    self.assertRaises(pipeline.PipelineInUse, test_pipeline_b.reserve_pipeline)

    # Make sure the correct pipelines are active
    self.assertTrue(test_pipeline_a.is_active)
    self.assertTrue(not test_pipeline_b.is_active)

    # Make sure that the 'test_device3' device in pipeline b (which is not used by pipeline a) was rolled back correctly 
    # after the locking error occured
    test_pipeline_b.devices['test_device3'].reserve_device()

  def _load_test_schedule(self):
    """ Loads a valid test schedule and returns a deferred that will be fired once that schedule has been loaded and 
    parsed. This schedule is used to test the Pipeline class.
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

  def _reset_device_manager(self, command_parser):
    """ Resets the device manager instance. This is required if multiple pipeline configurations are tested in the same
    test method because the device pipeline registrations don't get reset when the pipeline manager does.

    @param command_parser  The active command parser instance.
    """

    # Load a valid device configuration and setup the device manager
    self.config.read_configuration(self.source_data_directory+'/hardware/devices/tests/data/devices_configuration_valid.yml')
    self.device_manager = device_manager.DeviceManager(command_parser)

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

class TestPipelineError(Exception):
  pass
