""" @package hwm.hardware.pipelines.pipeline
Represents individual hardware pipelines.

This modules contains the class that is used to represent individual hardware pipelines.
"""

# Import required packages
import logging
from hwm.hardware.pipelines import manager as pipeline_manager

class Pipeline:
  """ Represents and provides access to a hardware pipeline.
  
  This class provides an interface to the hardware pipeline and associated hardware devices.
  """
  
  def __init__(self, pipeline_configuration):
    """ Initializes the pipeline with the supplied configuration.
    
    @throw May pass on any exceptions raised during the pipeline setup procedure (see _setup_pipeline()).
    
    @param pipeline_configuration  A dictionary containing the settings to initialize the pipeline with. This is 
                                   supplied by the pipeline manager and is loaded from the pipeline configuration file.
    """
    
    # Initialize pipeline attributes
    self.in_use = False
    self.configuration = pipeline_configuration
    self.id = pipeline_configuration['id']
    
    # Perform additional checks on the pipeline
    self._setup_pipeline()
  
  def _setup_pipeline(self):
    """ Sets up the pipeline and performs additional validations.
    
    This method performs additional initial validations on the pipeline. It will not check for schema errors because the
    PipelineManager should have already checked the pipeline configuration schema by the time this pipeline was 
    initialized. In addition, this method also stores references to the pipeline's hardware drivers.
    
    Currently, this method checks for the following:
    - Multiple pipeline input devices
    - Multiple pipeline output devices
    - Non-existent devices
    - Pipeline setup commands that don't use a system device handler or a device handler belonging to the pipeline
    
    @throw May throw PipelineConfigInvalid if any errors are detected.
    """
    
    # Local variables
    input_device_found = False
    output_device_found = False
    
    # Loop through the pipeline's hardware
    for temp_device in temp_pipeline['hardware']:
      # Verify that the device exists
      try:
        self.devices.get_device_driver(temp_device['device_id'])
      except device_manager.DeviceNotFound:
        logging.error("The '"+temp_device['device_id']+"' device in the '"+temp_pipeline['id']+
                      "' pipeline could not be located.")
        raise PipelineConfigInvalid("The '"+temp_pipeline['id']+"' pipeline configuration specified a non-existent "+
                                    "device: '"+temp_device['device_id']+"'")
      
      
      
      # Make sure there is only a single input and output device
      if 'pipeline_input' in temp_device:
        if input_device_found:
          logging.error("The '"+temp_pipeline['id']+"' pipeline contained multiple input devices.")
          raise PipelineConfigInvalid("The '"+temp_pipeline['id']+"' pipeline contained multiple input devices.")
        else:
          input_device_found = True
      
      if 'pipeline_output' in temp_device:
        if output_device_found:
          logging.error("The '"+temp_pipeline['id']+"' pipeline contained multiple output devices.")
          raise PipelineConfigInvalid("The '"+temp_pipeline['id']+"' pipeline contained multiple output devices.")
        else:
          output_device_found = True
  
  def reserve_pipeline(self):
    """ Locks the pipeline.
    
    This method is used primarily by the session coordinator to ensure that a pipeline is never used concurrently by two
    different sessions. However, to enable some more design flexibility, this is enforced purely by convention (unlike a
    mutex).
    
    @throw Raises PipelineInUse if the pipeline is currently being used and can't be locked.
    """
    
    # Check if the pipeline is being used
    if self.in_use:
      raise PipelineInUse("The pipeline requested is all ready in use and can not be reserved.")
    
    # Lock the pipeline
    self.in_use = True
  
  def free_pipeline(self):
    """ Frees the pipeline.
    
    This method is used to free a pipeline. This typically occurs at the conclusion of a usage session.
    """
    
    # Free the pipeline
    self.in_use = False

# Define the Pipeline exceptions
class PipelineInUse(Exception):
  pass
