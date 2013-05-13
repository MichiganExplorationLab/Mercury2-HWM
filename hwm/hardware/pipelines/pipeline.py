""" @package hwm.hardware.pipelines.pipeline
Represents individual hardware pipelines.

This modules contains the class that is used to represent individual hardware pipelines.
"""

# Import required packages
import logging
from hwm.hardware.devices import manager as device_manager

class Pipeline:
  """ Represents and provides access to a hardware pipeline.
  
  This class provides an interface to the hardware pipeline and associated hardware devices.
  """
  
  def __init__(self, pipeline_configuration, device_manager, command_parser):
    """ Initializes the pipeline with the supplied configuration.
    
    @throw May pass on any exceptions raised during the pipeline setup procedure (see _setup_pipeline()).
    
    @param pipeline_configuration  A dictionary containing the settings to initialize the pipeline with. This is 
                                   supplied by the pipeline manager and is loaded from the pipeline configuration file.
    """
    
    # Initialize pipeline attributes
    self.device_manager = device_manager
    self.command_parser = command_parser
    self.pipeline_configuration = pipeline_configuration
    self.in_use = False
    self.id = pipeline_configuration['id']
    self.mode = pipeline_configuration['mode']
    self.setup_commands = pipeline_configuration['setup_commands'] if 'setup_commands' in pipeline_configuration else None
    self.devices = {}
    self.input_device = None
    self.output_device = None
    
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
    - Duplicate devices
    - Pipeline setup commands that don't use a system device handler or a device handler belonging to the pipeline
    
    @throw May throw PipelineConfigInvalid if any errors are detected.
    """
    
    # Validation flags
    input_device_found = False
    output_device_found = False
    curr_device_driver = None
    
    # Loop through the pipeline's hardware
    for temp_device in self.pipeline_configuration['hardware']:
      # Check if the hardware device is a duplicate
      if temp_device['device_id'] in self.devices:
        logging.error("The '"+temp_device['device_id']+"' device in the '"+self.id+"' pipeline was declared twice in "+
                      "the configuration.")
        raise PipelineConfigInvalid("The '"+self.id+"' pipeline configuration specified a device "+
                                                     "twice: '"+temp_device['device_id']+"'")
      
      # Verify that the device exists and store it
      try:
        curr_device_driver = self.device_manager.get_device_driver(temp_device['device_id'])
      except device_manager.DeviceNotFound:
        logging.error("The '"+temp_device['device_id']+"' device in the '"+self.id+"' pipeline could not be located.")
        raise PipelineConfigInvalid("The '"+self.id+"' pipeline configuration specified a "+
                                                     "non-existent device: '"+temp_device['device_id']+"'")
      self.devices[temp_device['device_id']] = curr_device_driver
      
      # Make sure there is only a single input and output device
      if 'pipeline_input' in temp_device:
        if input_device_found:
          logging.error("The '"+self.id+"' pipeline configuration contained multiple input devices.")
          raise PipelineConfigInvalid("The '"+self.id+"' pipeline configuration contained multiple input devices.")
        else:
          self.input_device = curr_device_driver
          input_device_found = True
      
      if 'pipeline_output' in temp_device:
        if output_device_found:
          logging.error("The '"+self.id+"' pipeline configuration contained multiple output devices.")
          raise PipelineConfigInvalid("The '"+self.id+"' pipeline configuration contained multiple output devices.")
        else:
          self.output_device = curr_device_driver
          output_device_found = True
  
    # Loop through the pipeline setup commands and make sure they reference a system command handler or a command handler
    # for a device used by the pipeline
    if self.setup_commands is not None:
      for temp_command in self.setup_commands:
        if (temp_command['destination'] not in self.command_parser.system_command_handlers and
            temp_command['destination'] not in self.devices):
          logging.error("The '"+self.id+"' pipeline configuration contained setup commands that used command handlers "+
                        "that the pipeline does not have access to.")
          raise PipelineConfigInvalid("The '"+self.id+"' pipeline configuration contained setup commands that used "+
                                      "command handlers that the pipeline does not have access to.")
  
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
class PipelineConfigInvalid(Exception):
  pass
class PipelineInUse(Exception):
  pass
