# Import required modules
import logging, threading
from twisted.trial import unittest
from hwm.core.configuration import *
from hwm.hardware.pipelines import pipeline
from hwm.hardware.devices import manager as device_manager
from hwm.hardware.devices.drivers import driver
from hwm.command import parser, command
from hwm.command.handlers import system as command_handler
from hwm.network.security import permissions
from pkg_resources import Requirement, resource_filename

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
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_invalid_device.yml')
    self.assertRaises(pipeline.PipelineConfigInvalid, pipeline.Pipeline,
                    self.config.get('pipelines')[1],
                    self.device_manager,
                    self.command_parser)

    # Load a pipeline configuration that specifies multiple output devices for a single pipeline
    self._reset_config_entries()
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_multiple_output_devices.yml')
    self.assertRaises(pipeline.PipelineConfigInvalid, pipeline.Pipeline,
                    self.config.get('pipelines')[0],
                    self.device_manager,
                    self.command_parser)

  def test_setup_commands_errors(self):
    """ Tests that the Pipeline class correctly rejects pipeline configurations that contain setup command errors.
    """

    # Load a pipeline configuration that contains a pipeline setup command that uses a device that the pipeline doesn't
    # have access to
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_invalid_command_destination.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Run the setup commands
    setup_commands_deferred = test_pipeline.run_setup_commands()

    return self.assertFailure(setup_commands_deferred, pipeline.PipelineConfigInvalid)

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
    setup_commands_deferred = test_pipeline.run_setup_commands()
    setup_commands_deferred.addCallback(check_results)

    return setup_commands_deferred

  def test_setup_commands_successful(self):
    """ Checks that the Pipeline class can correctly run valid setup commands.
    """

    # Load a pipeline configuration that contains some valid setup commands
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[0], self.device_manager, self.command_parser)

    # Define a callback to check the results of the setup command execution
    def check_results(setup_command_results):
      # Make sure that the correct command response is present for both pipeline setup commands
      self.assertTrue('timestamp' in setup_command_results[0]['response']['result'])
      self.assertTrue('timestamp' in setup_command_results[1]['response']['result'])

    # Run the setup commands
    setup_commands_deferred = test_pipeline.run_setup_commands()
    setup_commands_deferred.addCallback(check_results)

    return setup_commands_deferred

  def test_setup_commands_failed(self):
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
    setup_commands_deferred = test_pipeline.run_setup_commands()
    setup_commands_deferred.addErrback(check_results)

    return setup_commands_deferred

  def test_locking_successful(self):
    """ Verifies that the Pipeline class can correctly lock a pipeline and its associated hardware.
    """

    # Load a valid pipeline configuration
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    test_pipeline = pipeline.Pipeline(self.config.get('pipelines')[2], self.device_manager, self.command_parser)

    # Lock the pipeline
    test_pipeline.reserve_pipeline()

    # Try re-locking the pipeline
    self.assertRaises(pipeline.PipelineInUse, test_pipeline.reserve_pipeline)

    # Make sure the devices were correctly locked
    for temp_device in test_pipeline.devices:
      self.assertRaises(driver.DeviceInUse, test_pipeline.devices[temp_device].reserve_device)

    # Unlock the pipeline and make sure that all of its devices were freed
    test_pipeline.free_pipeline()
    self.assertRaises(threading.ThreadError, test_pipeline.in_use.release)
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

    # Make sure that the 'test_device3' device in pipeline b (which is not used by pipeline a) was rolled back correctly 
    # after the locking error occured
    test_pipeline_b.devices['test_device3'].reserve_device()

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}
