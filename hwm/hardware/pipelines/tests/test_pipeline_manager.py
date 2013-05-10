# Import required modules
import logging
from twisted.trial import unittest
from hwm.core.configuration import *
from hwm.hardware.pipelines import manager, pipeline
from pkg_resources import Requirement, resource_filename

class TestPipelineManager(unittest.TestCase):
  """
  This collection of tests tests the hardware pipeline manager, which is responsible for managing access to the
  individual hardware pipelines.
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
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None
  
  def test_initialization_errors(self):
    """Verifies that the pipeline manager raises exceptions as appropriate during initialization.
    """
    
    # Attempt to initialize the pipeline manager without specifying a config file (no "pipelines" property set)
    self.assertRaises(manager.PipelinesNotDefined, manager.PipelineManager)
    
    # Load an empty pipeline configuration and ensure the correct error is raised
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_empty.yml')
    self.assertRaises(manager.PipelineConfigInvalid, manager.PipelineManager)
    
    # Make sure re-initialization fails
    self._reset_config_entries()
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    new_pipeline_manager = manager.PipelineManager()
    self.assertRaises(manager.PipelinesAlreadyInitialized, new_pipeline_manager._initialize_pipelines)
  
  def test_pipeline_invalid_config(self):
    """Tests that the pipeline manager correctly rejects some invalid pipeline configurations (as validated by 
    Pipeline._validate_configuration())."""
    
    # Load a configuration that contains a pipeline that doesn't specify any hardware
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_invalid.yml')
    self.assertRaises(manager.PipelineConfigInvalid, manager.PipelineManager)
    
    # Load a configuration that contains a pipeline that specifies multiple output devices
    self._reset_config_entries()
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_invalid_2.yml')
    self.assertRaises(manager.PipelineConfigInvalid, manager.PipelineManager)
  
  def test_pipeline_get(self):
    """Tests that the pipeline manager can correctly return a specified pipeline.
    """
    
    # Load a valid pipeline configuration
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    
    # Initialize the pipeline manager
    temp_pipeline_manager = manager.PipelineManager()
    
    # Try to load a missing pipeline
    self.assertRaises(manager.PipelineNotFound, temp_pipeline_manager.get_pipeline, 'missing_pipeline')
    
    # Try to load a valid pipeline
    temp_pipeline = temp_pipeline_manager.get_pipeline('test_pipeline2')
    self.assertEquals(temp_pipeline.id, 'test_pipeline2')
  
  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}
