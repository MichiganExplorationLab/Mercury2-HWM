# Import required modules
import logging
from twisted.trial import unittest
from hwm.core.configuration import *
from hwm.hardware.pipelines import manager as pipeline_manager, pipeline
from hwm.hardware.devices import manager as device_manager
from hwm.command import parser
from hwm.command.handlers import system as command_handler
from hwm.network.security import permissions
from pkg_resources import Requirement, resource_filename

class TestPipelineManager(unittest.TestCase):
  """ This collection of tests tests the hardware pipeline manager, which is responsible for managing access to the
  individual hardware pipelines.
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
    """Verifies that the pipeline manager raises exceptions as appropriate during initialization.
    """
    
    # Attempt to initialize the pipeline manager without specifying a config file (no "pipelines" property set)
    self.assertRaises(pipeline_manager.PipelinesNotDefined, pipeline_manager.PipelineManager, self.device_manager, self.command_parser)
    
    # Load an empty pipeline configuration and ensure the correct error is raised
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_empty.yml')
    self.assertRaises(pipeline_manager.PipelineSchemaInvalid, pipeline_manager.PipelineManager, self.device_manager, self.command_parser)
    
    # Make sure re-initialization fails
    self._reset_config_entries()
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    new_pipeline_manager = pipeline_manager.PipelineManager(self.device_manager, self.command_parser)
    self.assertRaises(pipeline_manager.PipelinesAlreadyInitialized, new_pipeline_manager._initialize_pipelines)
  
  def test_pipeline_invalid_config(self):
    """ Tests that the pipeline manager correctly rejects some invalid pipeline configurations (as validated by 
    Pipeline._setup_pipeline()). This is also tested directly by the Pipeline unit test suite."""
    
    # Load a configuration that contains a pipeline that doesn't specify any hardware (a schema error)
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_no_hardware.yml')
    self.assertRaises(pipeline_manager.PipelineSchemaInvalid, pipeline_manager.PipelineManager, self.device_manager, self.command_parser)
    
    # Load a configuration that contains a pipeline that specifies multiple output devices
    self._reset_config_entries()
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_multiple_output_devices.yml')
    self.assertRaises(pipeline.PipelineConfigInvalid, pipeline_manager.PipelineManager, self.device_manager, self.command_parser)
    
    # Load a configuration that contains a pipeline that references a non-existent device
    self._reset_config_entries()
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_invalid_device.yml')
    self.assertRaises(pipeline.PipelineConfigInvalid, pipeline_manager.PipelineManager, self.device_manager, self.command_parser)
  
  def test_pipeline_get(self):
    """Tests that the pipeline manager can correctly return a specified pipeline.
    """
    
    # Load a valid pipeline configuration
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    
    # Initialize the pipeline manager
    temp_pipeline_manager = pipeline_manager.PipelineManager(self.device_manager, self.command_parser)
    
    # Try to load a missing pipeline
    self.assertRaises(pipeline_manager.PipelineNotFound, temp_pipeline_manager.get_pipeline, 'missing_pipeline')
    
    # Try to load a valid pipeline
    temp_pipeline = temp_pipeline_manager.get_pipeline('test_pipeline2')
    self.assertEquals(temp_pipeline.id, 'test_pipeline2')
  
  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}
