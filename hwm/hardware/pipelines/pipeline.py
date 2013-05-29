""" @package hwm.hardware.pipelines.pipeline
Represents individual hardware pipelines.

This modules contains the class that is used to represent individual hardware pipelines.
"""

# Import required packages
import logging
from twisted.internet import defer
from hwm.hardware.devices import manager as device_manager
from hwm.hardware.devices.drivers import driver

class Pipeline:
  """ Represents and provides access to a hardware pipeline.
  
  This class provides an interface to the hardware pipeline and associated hardware devices.
  """
  
  def __init__(self, pipeline_configuration, device_manager, command_parser):
    """ Initializes the pipeline with the supplied configuration.
    
    @throw May pass on any exceptions raised during the pipeline setup procedure (see _setup_pipeline()).
    
    @param pipeline_configuration  A dictionary containing the configuration settings for this pipeline. This is 
                                   supplied by the pipeline manager and is loaded from the pipeline configuration file.
    @param device_manager          A reference to the DeviceManager that will be used to load the pipeline hardware.
    @param command_parser          A reference to the CommandParser that will be used to run pipeline setup commands.
    """
    
    # Initialize pipeline attributes
    self.device_manager = device_manager
    self.command_parser = command_parser
    self.pipeline_configuration = pipeline_configuration
    self.id = pipeline_configuration['id']
    self.mode = pipeline_configuration['mode']
    self.setup_commands = pipeline_configuration['setup_commands'] if 'setup_commands' in pipeline_configuration else None
    self.devices = {}
    self.in_use = False
    self.input_device = None
    self.output_device = None
    
    # Perform additional checks on the pipeline
    self._setup_pipeline()

  def run_setup_commands(self):
    """ Runs the pipeline setup commands.
    
    This method runs the pipeline setup commands, which are responsible for putting the pipeline in its intended state
    before setting up the session.

    @return If successful, this method will return a DeferredList containing the results of the pipeline setup commands.
            If any of the commands fail additional validations (destination restrictions, etc.), a pre-fired failed
            deferred will be returned. Finally, if this pipeline doesn't have any setup commands None will be returned
            via a pre-fired successful deferred.
    """

    running_setup_commands = []

    # Run the pipeline setup commands 
    if self.setup_commands is not None:
      for temp_command in self.setup_commands:
        # First, make sure the command belongs to a system command handler or to a device used by this pipeline
        if (temp_command['destination'] not in self.command_parser.system_command_handlers() and
            temp_command['destination'] not in self.devices):
          return defer.fail(PipelineConfigInvalid("The '"+self.id+"' pipeline configuration contained a setup command "+
                                                  "'"+temp_command['command']+"' with a destination that the pipeline "+
                                                  "does not have access to: "+temp_command['destination']))
        
        # Execute the command and add it to the list
        temp_command_deferred = self.command_parser.parse_command(temp_command, kernel_mode = True)
        running_setup_commands.append(temp_command_deferred)

      # Aggregate the command deferreds into a single DeferredList
      return defer.gatherResults(running_setup_commands, consumeErrors = True)
    else:
      # No pipeline setup commands to run
      return defer.succeed(None)
  
  def reserve_pipeline(self):
    """ Locks the pipeline and its hardware.
    
    This method is used primarily by sessions to ensure that a pipeline and its hardware are never used concurrently
    by two different sessions.
    
    @note If a pipeline can not be reserved because one or more of its hardware devices is currently locked, it will 
          rollback any locks that it may have acquired already.
    
    @throw Raises PipelineInUse if the pipeline or any of its hardware is currently being used and can't be locked.
    """
    
    successfully_locked_devices = []

    # Check if the pipeline is being used
    if self.in_use:
      raise PipelineInUse("The requested pipeline is all ready in use and can not be reserved.")
    
    # Lock all of the pipeline's hardware
    for device_id in self.devices:
      # Attempt to lock the device
      try:
        self.devices[device_id].reserve_device()
        successfully_locked_devices.append(device_id)
      except driver.DeviceInUse:
        # A device in the pipeline is currently being used, rollback hardware locks acquired thus far
        for locked_device in successfully_locked_devices:
          self.devices[locked_device].free_device()

        raise PipelineInUse("One or more of the devices in the '"+self.id+"' pipeline is currently being used so the "+
                            "pipeline can't be reserved.")
    
    # Lock the pipeline
    self.in_use = True
  
  def free_pipeline(self):
    """ Frees the pipeline.
    
    This method is used to free the hardware pipeline. This typically occurs at the conclusion of a usage session, but 
    it can also occur in the event that a session that is currently using the pipeline experiences a fatal error.

    @note This method will only unlock hardware devices if the pipeline is in use. This will prevent the pipeline from 
          unlocking devices that are being used by other pipelines that share some of the same hardware devices.
    """
    
    # Free the pipeline's hardware devices
    if self.in_use:
      for device_id in self.devices:
        self.devices[device_id].free_device()
    
    # The pipeline is free
    self.in_use = False

  def _setup_pipeline(self):
    """ Sets up the pipeline and performs additional validations.
    
    This method performs additional initial validations on the pipeline. It will not check for schema errors because the
    PipelineManager should have already checked the pipeline configuration schema by the time this pipeline was 
    initialized. In addition, this method also stores references to the pipeline's hardware drivers for later use.
    
    Currently, this method checks for the following:
    - Multiple pipeline input devices
    - Multiple pipeline output devices
    - Non-existent pipeline devices
    - Duplicate pipeline devices
    
    @throw Throws PipelineConfigInvalid if any errors are detected.
    """
    
    # Validation flags
    input_device_found = False
    output_device_found = False
    
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
        logging.error("The '"+temp_device['device_id']+"' device in the '"+self.id+"' pipeline configuration could "+
                      "not be located.")
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

# Define the Pipeline exceptions
class PipelineConfigInvalid(Exception):
  pass
class PipelineInUse(Exception):
  pass
