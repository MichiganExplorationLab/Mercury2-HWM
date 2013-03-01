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
  
  def reserve_pipeline(self):
    """Locks the pipeline.
    
    When called, this method checks if the pipeline is currently being used. If it is, an exception is generated. If it
    isn't then the pipeline is locked.
    """
    
    # Check if the pipeline is being used
    if self.in_use:
      raise PipelineInUse("The pipeline requested is all ready in use and can not be reserved.")
    
    # Lock the pipeline
    self.in_use = True
  
  def _validate_configuration(self):
    """Validates the pipeline's supplied configuration.
    
    This method validates the pipeline's supplied configuration against the requirements.
    
    @throw Throws PipelineInvalidConfiguration is the supplied configuration is invalid.
    """
    
    # Define the required pipeline fields
    required_fields = ['id',
                       'hardware']
    
    # Validate the required fields
    for required_field in required_fields:
      if (self.configuration[required_field] is None) or (len(self.configuration[required_field]) == 0):
        logging.error("Invalid pipeline configuration detected (required fields missing).")
        raise PipelineInvalidConfiguration("Required field missing from pipeline configuration: "+required_field)
    
    # Store specific pipeline parameters
    self.id = self.configuration['id']

# Define the Pipeline exceptions
class PipelineInvalidConfiguration(Exception):
  pass
class PipelineInUse(Exception):
  pass
