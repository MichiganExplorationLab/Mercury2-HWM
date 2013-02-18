# Import required modules
import unittest, logging
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
    self.config.options = {}
    self.config.user_options = {}
    
    # Reset the configuration reference
    self.config = None
  
  def test_initialization_errors(self):
    """Verifies that the pipeline manager raises exceptions as appropriate during initialization.
    """
    
    # Attempt to initialize the pipeline manager without specifying a config file
    self.assertRaises(manager.PipelinesNotDefined, manager.PipelineManager)
    
    # Load an empty pipeline configuration and ensure the correct error is raised
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_empty.yml')
    self.assertRaises(manager.PipelinesNotDefined, manager.PipelineManager)
  
  def test_reinitialization_errors(self):
    """Tests that the pipeline manager raises the expected exceptions if the pipeline initialization function is called 
    a second time.
    """
    
    # Load a valid pipeline configuration
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_valid.yml')
    
    # Initialize the pipeline manager
    temp_pipeline_manager = manager.PipelineManager()
    
    # Verify the re-initialization error
    self.assertRaises(manager.PipelinesAllReadyInitialized, temp_pipeline_manager._initialize_pipelines)
  
  def test_pipeline_invalid_config(self):
    """Tests that the pipeline manager correctly rejects an invalid pipeline configuration (as validated by 
    Pipeline._validate_configuration())."""
    
    # Load the invalid pipeline configuration
    self.config.read_configuration(self.source_data_directory+'/hardware/pipelines/tests/data/pipeline_configuration_invalid.yml')
    
    # Verify the correct exception is thrown
    self.assertRaises(pipeline.PipelineInvalidConfiguration, manager.PipelineManager)
  
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
    temp_pipeline = temp_pipeline_manager.get_pipeline('test_pipeline')
