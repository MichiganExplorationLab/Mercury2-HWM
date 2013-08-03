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
    self.active_services = {}
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
          This behavior is encouraged by the default Driver interface (Driver.write_device_output()). If this convention
          isn't followed, the pipeline output may end up getting jumbled.
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
    @note Pipelines may have multiple services of the same type registered to them. During the session setup process, 
          the Pipeline will configure which service should be active for each service type. It is this service that will
          be returned when a device queries for a service of that type. All available services are stored in 
          self.services whereas the active services are stored in self.active_services.

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

  def load_service(self, service_type):
    """ Returns the active service for the specified service type.
    
    This method queries the pipeline's active service dictionary and returns the callable for the specified service 
    type. Drivers will use this method to load services when sessions begin.
    
    @throw Raises ServiceTypeNotFound if there are currently not any active services for the specified type.

    @note The registered services that should be active at any given time are specified by the reservation schedule and 
          set in self._set_active_services() at the beginning of each session.
    
    @param service_type  A string indicating the desired service type.
    @return Returns the service callable.
    """

    # Check if a service for the specified type is available
    if service_type in self.active_services:
      return self.active_services[service_type]
    else:
      raise ServiceTypeNotFound("An active service of the '"+service_type+"' variety was not found in the '"+
                                self.id+"' pipeline.")

  def register_session(self, session):
    """ Registers the provided session with this pipeline.

    This method registers the session with the pipeline for the purpose of sending data such as the main pipeline output
    and pipeline telemetry to the session (and to the data/telemetry streams in turn). It also calls a method that 
    enables the session's active services.

    @note Only one session can be registered to the pipeline at a time. This is because pipelines can only be used by a 
          single session (or reservation) at a time. Because the session coordinator ends old sessions before it creates
          new ones, this shouldn't be a problem for back to back reservations.
    @note This method should be the first thing called after a session can be considered "active". That is to say, after
          the pipeline setup commands have been executed but before the session setup commands get executed.
    
    @throw Raises SessionAlreadyRegistered in the event that a session is registered to a pipeline that already has a 
           registered session. Sessions must be deregistered before a new one can be registered.
    @throw May pass on ServiceInvalid exceptions if the session configuration specifies an invalid service (i.e. 
           a non-existent service or service type).

    @param session  The Session instance that should currently be associated with the pipeline.
    """

    # Make sure that the pipeline doesn't already have a registered session.
    if self.current_session is not None:
      raise SessionAlreadyRegistered("The specified session couldn't be registered with the '"+self.id+"' pipeline "+
                                     "because it is already associated with an existing session.")

    self.current_session = session

    # Set the active services for the pipeline
    self._set_active_services()

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

    # Set the pipeline as in use
    self.in_use = True
  
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
    """ Indicates that the pipeline is currently active.

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

  def _set_active_services(self):
    """ Sets the pipeline's active services.

    This method sets the active services for the pipeline based on the provided session's configuration. For example, if
    the pipeline's devices offer multiple "tracker" services, this method will set the active one based on what's
    specified in the session configuration.

    @note The active_services dictionary gets reset every time a session is registered (because which services are
          active always depends on the session configuration). This method should only be called from 
          self.register_session().

    @throw Raises ServiceInvalid if the session configuration specifies a service that isn't registered to the pipeline
           or if it specifies a service type that isn't available to the pipeline.
    """

    # Reset the dictionary
    self.active_services = {}

    # Look through the session configuration and set the active services
    if 'active_services' in self.current_session.configuration:
      for service_type in self.current_session.configuration['active_services']:
        # Try to locate the service callable in self.services
        if service_type in self.services:
          if self.current_session.configuration['active_services'][service_type] in self.services[service_type]:
            # Service is available, store it in active_services (only one service per type)
            temp_service_id = self.current_session.configuration['active_services'][service_type]
            self.active_services[service_type] = self.services[service_type][temp_service_id]
          else:
            # Specific service not found in the pipeline
            raise ServiceInvalid("The '"+self.current_session.id+"' session configuration specified a service '"+
                                 self.current_session.configuration['active_services'][service_type]+"' that isn't "+
                                 "registered to the pipeline.")
        else:
          # Service type not found in the pipeline
          raise ServiceInvalid("The '"+self.current_session.id+"' session configuration specified a service type '"+
                               service_type+"' that isn't available to the pipeline.")

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
class ServiceTypeNotFound(PipelineError):
  pass
