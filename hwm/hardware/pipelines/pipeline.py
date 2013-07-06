""" @package hwm.hardware.pipelines.pipeline
Represents individual hardware pipelines.

This modules contains the class that is used to represent individual hardware pipelines.
"""

# Import required packages
import logging, threading
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
    self.in_use = False
    self.devices = {}
    self.services = {}
    self.current_session = None
    self.input_device = None
    self.output_device = None
    
    # Perform additional checks on the pipeline
    self._setup_pipeline()

  def write_to_pipeline(self, input_data):
    """ Writes the specified data chunk to the pipeline's input device.

    This method writes the provided data chunk to the pipeline's input device, if it has one. If the pipeline doesn't 
    have an input device, the data will simply be dropped and ignored. Typically, this data will come from the Session
    that is currently using this pipeline.

    @note The specified data chunk will be passed to the pipeline's input device via its write_to_device() method. 

    @param input_data  A data chunk of arbitrary size that is to be written to the pipeline's input device.
    """

    # Write the data to the input device (if available)
    if self.input_device is not None:
      self.input_device.write_to_device(input_data)

  def write_pipeline_output(self, output_data):
    """ Pushes the specified data to the pipeline's output stream.
    
    This method writes the specified data chunk to the pipeline's main output stream by passing it to the registered
    session's write_to_output_stream() method.

    @note Typically, only a single device in a pipeline should make calls to this method (the pipeline's output device).
          This behavior is encouraged by the default Driver interface. If this convention isn't followed, the pipeline
          output may end up getting jumbled.
    @note If no session is currently registered to the pipeline any data passed to this method will be discarded.

    @param output_data  A data chunk of arbitrary size that is to be written to the pipeline's main output stream.
    """

    if self.current_session is not None:
      self.current_session.write_to_output_stream(output_data)

  def write_telemetry_datum(self, source_id, stream, timestamp, telemetry_datum, **extra_headers):
    """ Passes the provided telemetry datum to the session registered to this pipeline.

    Sends the provided telemetry datum and its headers to the session currently using this pipeline. The session will
    be responsible for routing the telemetry to its appropriate destination (typically a Twisted Protocol).

    @note If no session is currently associated with the pipeline, calls to this method will just be ignored (and the 
          data discarded).

    @param source_id        The ID of the device or pipeline that generated the telemetry datum.
    @param stream           A string identifying which of the device's telemetry streams the datum should be associated 
                            with.
    @param timestamp        A unix timestamp signifying when the telemetry point was assembled.
    @param telemetry_datum  The actual telemetry datum. Can take many forms (e.g. a JSON string or binary webcam image).
    @param **extra_headers  A dictionary containing extra keyword arguments that should be included as additional
                            headers when sending the telemetry datum.
    """

    # Send the telemetry datum to the registered session
    if self.current_session is not None:
      self.current_session.write_telemetry_datum(source_id, stream, timestamp, telemetry_datum, **extra_headers)

  def register_service(self, service):
    """ Registers services with the pipeline.
    
    This method registers the specified service with the pipeline. Unsurprisingly, services offer some service to the 
    pipeline and its devices. If another device in the pipeline knows which interface a particular service implements, 
    it can query the pipeline for the service callable and use it via the methods defined in the service's interface.

    @note Services may define their own interfaces not derived from one of the standard ones but devices won't be able 
          to use them unless they were specifically designed to be able to do so.
    @note Devices may register multiple services of the same type. During the session setup process, the Pipeline will
          configure which service should be active for each service type. It is this service that will be returned when 
          a device queries for a service of that type.

    @throws Raises ServiceAlreadyRegistered in the event that a device tries to register the same service twice.

    @param service  A callable (typically a class) that provides an interface for interacting with the service.  
    """

    # Make sure the service hasn't been registered already
    if (service.type in self.services) and (service.id in self.services[service.type]):
      raise ServiceAlreadyRegistered("The '"+service.id+"' service has already been registered with the '"+
                                     self.id+"' pipeline.")

    # Store the service
    if service.type not in self.services:
      self.services[service.type] = {}

    self.services[service.type][service.id] = service

  def register_session(self, session):
    """ Registers the provided session with this pipeline.

    This method registers the session with the pipeline for the purpose of sending data such as the main pipeline output
    and pipeline telemetry to the session (and to the data/telemetry streams in turn).

    @note Only one session can be registered to the pipeline at a time. This is because pipelines can only be used by a 
          single session (or reservation) at a time. Because the session coordinator ends old sessions before it creates
          new ones, this shouldn't be a problem for back to back reservations.
    
    @throw Raises SessionAlreadyRegistered in the event that a session is registered to a pipeline that already has a 
           registered session.

    @param session  The Session instance that should currently be associated with the pipeline.
    """

    # Make sure that the pipeline doesn't already have a registered session.
    if self.current_session not None:
      raise SessionAlreadyRegistered("The specified session couldn't be registered with the '"+self.id+"' pipeline "+
                                     "because it is already associated with an existing session.")

    self.current_session = session

  def run_setup_commands(self):
    """ Runs the pipeline setup commands.
    
    This method runs the pipeline setup commands, which are responsible for putting the pipeline in its intended state
    before use by a session.
    
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
    by two different sessions (unless a device is configured to allow for concurrent access).
    
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
  
  def free_pipeline(self):
    """ Frees the pipeline.
    
    This method is used to free the hardware pipeline. This typically occurs at the conclusion of a usage session, but 
    it can also occur in the event that a session that is currently using the pipeline experiences a fatal error.

    @note This method will only unlock hardware devices if the pipeline is in use. This will prevent the pipeline from 
          unlocking devices that are being used by other pipelines that share some of the same hardware devices.
    """
    
    # Free the pipeline's hardware devices if the pipeline is in use
    if self.in_use:
      for device_id in self.devices:
        self.devices[device_id].free_device()

      self.in_use = False

  @property
  def is_active(self):
    """ Indicates if the pipeline is currently active.

    This property checks if the pipeline is currently being used by a session. This method is commonly used to determine
    if a given device should write data to the pipeline or not.

    @note This method is used instead of accessing self.in_use directly because it prevents drivers from changing the 
          pipeline's state accidentally.  

    @return Returns True if the pipeline is currently being used and False otherwise.
    """

    if self.in_use:
      return True
    else:
      return False

  def _setup_pipeline(self):
    """ Sets up the pipeline and performs additional validations.
    
    This method performs additional initial validations on the pipeline and does some initial setup such as driver
    registration. It will not check for schema errors because the PipelineManager should have already checked the 
    pipeline configuration schema by the time this pipeline was initialized.
    
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

      # Register the pipeline with the its output device
      curr_device_driver.register_pipeline(self)

# Define the Pipeline exceptions
class PipelineError(Exception):
  pass
class PipelineConfigInvalid(PipelineError):
  pass
class PipelineInUse(PipelineError):
  pass
class SessionAlreadyRegistered(PipelineError):
  pass
class ServiceInvalid(PipelineError):
  pass
class ServiceAlreadyRegistered(PipelineError):
  pass
