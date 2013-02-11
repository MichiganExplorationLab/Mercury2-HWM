# Import required modules
import unittest, logging
from hwm.core.configuration import *
from hwm.hardware.pipelines import manager
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
