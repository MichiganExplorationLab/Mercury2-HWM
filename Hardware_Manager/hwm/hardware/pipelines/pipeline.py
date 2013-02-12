""" @package hwm.hardware.pipelines.pipeline
Represents individual hardware pipelines.

This modules contains the class that represents individual hardware pipelines and associated helper functions.
"""

# Import required packages
import logging

class Pipeline:
  """Represents and provides access to hardware pipelines.
  
  This class represents and provides an interface to the hardware pipelines and associated hardware devices.
  """
  
  def __init__(self, pipeline_configuration):
    """Initializes the pipeline with the supplied configuration.
    
    @note The pipelines are initialized by the pipeline manager, not individually.
    @note This method may pass on exceptions from the pipeline configuration validator.
    
    @param pipeline_configuration  A dictionary containing the settings to initialize the pipeline with. This is 
                                   supplied by the pipeline manager and is loaded from the pipeline configuration file.
    """
    
    # Initialize pipeline attributes
    self.in_use = False
    self.configuration = pipeline_configuration
    
    # Validate the configuration
    self._validate_configuration()
  
  def _validate_configuration(self):
    """Validates the pipeline's supplied configuration.
    
    This method validates the pipeline's supplied configuration against the requirements.
    
    @throw Throws PipelineInvalidConfiguration is the supplied configuration is invalid.
    """

# Define the Pipeline exceptions
class PipelineInvalidConfiguration(Exception):
  pass    
