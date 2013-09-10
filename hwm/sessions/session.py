""" @package hwm.sessions.session
Provides a representation for hardware manager usage sessions.

This module contains a class that is used to represent user access sessions (as specified in the reservation schedule).
"""

# Import required modules
import logging
from twisted.internet import defer
from hwm.hardware.pipelines import pipeline

class Session:
  """ Represents a user hardware pipeline usage session.
  
  This class is used to represent hardware pipeline reservations, which are specified by the reservation schedule. 
  Session instances are managed by the SessionCoordinator, which is responsible for creating and destroying sessions
  as needed.
  """
  
  def __init__(self, reservation_configuration, session_pipeline, command_parser):
    """ Initializes the new session.
    
    @note The provided pipeline is not locked when it is passed in. self.start_session needs to be called to lock up the
          pipeline and perform other session setup tasks.
    
    @param reservation_configuration  A dictionary containing the configuration settings for the reservation associated
                                      with this session.
    @param session_pipeline           The Pipeline that this session will use.
    @param command_parser             The CommandParser that will be used to execute the session setup commands.
    """
    
    # Set the session attributes
    self.active_pipeline = session_pipeline
    self.command_parser = command_parser
    self.configuration = reservation_configuration
    self.id = reservation_configuration['reservation_id']
    self.user_id = reservation_configuration['user_id']
    if 'setup_commands' in reservation_configuration:
      self.setup_commands = reservation_configuration['setup_commands']
    else:
      self.setup_commands = None
    self.data_protocols = []
    self.telemetry_protocols = []

    # Private session attributes
    self._active = False

  def write_telemetry(self, source_id, stream, timestamp, telemetry_datum, binary=False, **extra_headers):
    """ Writes the provided telemetry datum to the registered telemetry protocols.
    
    This method passes the provided telemetry datum and headers to all registered telemetry protocols. It will be called
    by this session's associated pipeline and facilitates the sending of pipeline telemetry (state, additional data 
    streams, etc.) from the pipeline (and its devices) to the pipeline user via the registered telemetry protocols 
    write_telemetry() methods.
    
    @note Because the telemetry stream uses HTTP, it's actually more of a packet stream than a true data stream (like 
          the main pipeline stream). The Twisted protocol that sends the pipeline telemetry to the end user uses 
          addressed HTTP packets to ensure that multiple unrelated data streams can be multi-plexed over the same socket
          without conflict. Thus, each call to this method will be with a complete "packet" of pipeline telemetry (i.e. 
          a JSON state string or single webcam frame). What ever receives these HTTP packets on the other side of the 
          socket will be responsible for assembling and displaying them in a coherent way.

    @param source_id        The ID of the device or pipeline that generated the telemetry datum.
    @param stream           A string identifying which of the device's telemetry streams the datum should be associated 
                            with.
    @param timestamp        A unix timestamp specifying when the telemetry point was assembled.
    @param telemetry_datum  The actual telemetry datum. Can take many forms (e.g. a dictionary or binary webcam image).
    @param binary           Whether or not the telemetry payload consists of binary data. If set to true, the data will
                            be encoded before being sent to the user.
    @param **extra_headers  A dictionary containing extra keyword arguments that should be included as additional
                            headers when sending the telemetry datum.
    """

    # Pass along the telementry datum
    for telemetry_protocol in self.telemetry_protocols:
      telemetry_protocol.write_telemetry(source_id, stream, timestamp, telemetry_datum, binary=binary, **extra_headers)

  def write_output(self, output_data):
    """ Writes the provided data chunk to the registered data protocols. 
    
    This method writes the provided chunk of data (pipeline output) to all registered data protocols. This method will 
    typically be called by the pipeline associated with this session and facilitates passing pipeline output from the 
    Pipeline class to the end user.

    @note Whenever the pipeline generates any output data, this method will call the write_output() method for
          every data protocol registered to this session. The data passed to this method will be of arbitrary size.

    @param output_data  A chunk of pipeline output of arbitrary size.
    """

    # Pass the data along to the registered data protocols
    for data_protocol in self.data_protocols:
      data_protocol.write_output(output_data)
 
  def write(self, input_data):
    """ Writes the chunk of data to the pipeline.

    This method writes the supplied chunk of data to the input stream of the pipeline associated with this session via 
    its write() method. This is one step in the process of getting the pipeline input data from the end user to the 
    pipeline's input device (typically a radio).

    @note Even though sessions can register multiple data protocols, only one protocol should write to this method at a 
          time. This convention is followed by the default PipelineData protocol, which will only write to the session
          if that particular connection is allowed to do so.
    
    @param input_data  A data chunk of arbitrary size that is to be written to the pipeline's input stream. Normally,
                       this comes from a Twisted protocol instance linked to the end user.
    """

    # Pass the data along to the pipeline
    self.active_pipeline.write(input_data)

  def register_data_protocol(self, data_protocol):
    """ Registers the provided data protocol with the session.

    This method is used to register a pipeline data protocol with the session. The session uses its registered data
    protocols to route the pipeline output and input streams to and from the end user.

    @note Multiple data protocols can be registered to the session. Any data that the pipeline generates will be routed
          to all registered data protocols. This allows for simultaneous connections to the same session. However, if
          multiple data protocols attempt to write to the session at the same time the data may be interlaced randomly 
          (because of the stream based nature of the system).
    
    @throw Throws ProtocolAlreadyRegistered in the event that the data protocol has already been registered.
    
    @param data_protocol  A Twisted Protocol class used to relay the pipeline's data stream to and from the session 
                          user.
    """

    # Check if the protocol is already registered
    if data_protocol in self.data_protocols:
      raise ProtocolAlreadyRegistered("The specified data protocol has already been registered with the session.")

    self.data_protocols.append(data_protocol)
  
  def register_telemetry_protocol(self, telemetry_protocol):
    """ Registers the provided telemetry protocol with the session.

    This method registers the supplied telemetry protocol with the session. The session will use this reference to pass 
    extra data (i.e. not the main pipeline output) from the pipeline to the end user. This data will consist of things 
    like extra data streams (e.g. a webcam feed) and live pipeline device state. This stream will be directed, with the 
    data flowing from the pipeline to the end user (through this session).

    @note This method allows multiple telemetry protocols to be registered with the session. Whenever the pipeline
          generates any telemetry, it will automatically be sent to each registered telemetry protocol.

    @throw Raises ProtocolAlreadyRegistered in the event that the telemetry protocol has already been registered.

    @param telem_protocol  A Twisted Protocol class used to relay the pipeline's telemetry stream to the pipeline user.
    """

    # Check if the protocol is already registered
    if telemetry_protocol in self.telemetry_protocols:
      raise ProtocolAlreadyRegistered("The specified telemetry protocol has already been registered with the session.")

    self.telemetry_protocols.append(telemetry_protocol)

  def get_pipeline_telemetry_producer(self):
    """ Returns the telemetry producer for the session's pipeline.

    This method returns the PipelineTelemetryProducer belonging to the session's pipeline. This is typically used by the
    telemetry protocol to regulate the production of pipeline telemetry. 

    @return Returns the PipelineTelemetryProducer instance belonging to the session's pipeline.
    """

    return self.active_pipeline.telemetry_producer

  def start_session(self):
    """ Sets up the session for use.
    
    This method sets up a new session by:
    - Reserving the pipeline hardware
    - Executing the pipeline setup commands
    - Executing the session setup commands
    - Activating the session
    
    @throws May fire the errback callback chain on the returned deferred if there is a problem reserving the pipeline or
            executing the pipeline setup commands. This will cause the session coordinator to log the error and end the 
            session. Session setup command errors don't generate session-fatal errors and are simply noted by the 
            session coordinator. This is done because these errors will often be recoverable with additional input from 
            the session user.
    
    @note All of the pipeline setup commands will always be executed before any of the session setup commands are.
    @note If a session-fatal error occurs, the self._session_setup_error callback will automatically clean up the 
          session (e.g. freeing locks). Whatever calls this function (i.e. SessionCoordinator) doesn't need to worry 
          about it.
    
    @return Returns a deferred that will be fired with the results of session setup commands (an array containing the 
            results for each setup command). 
    """
    
    # Lock the pipeline and pipeline hardware
    try:
      self.active_pipeline.reserve_pipeline()
    except pipeline.PipelineInUse:
      return defer.fail(pipeline.PipelineInUse("The pipeline requested for reservation '"+self.id+"' could not be "+
                                               "locked: "+self.active_pipeline.id))
    
    # Execute the pipeline setup commands
    pipeline_setup_deferred = self.active_pipeline.run_setup_commands()
    pipeline_setup_deferred.addCallback(self._run_setup_commands)
    pipeline_setup_deferred.addCallback(self._activate_session)
    pipeline_setup_deferred.addErrback(self._session_setup_error)
    
    return pipeline_setup_deferred

  @property
  def is_active(self):
    """ Indicates if the Session is active.

    This property checks if the session is currently active. That is, if it has already completed its setup process and 
    is ready for user interaction.

    @return Returns True if the Session is currently active and False otherwise.
    """

    return self._active
  
  def _run_setup_commands(self, pipeline_setup_commands_results):
    """ Runs the session setup commands.
    
    This callback runs the session setup commands after the pipeline setup commands have all been executed successfully.
    The session setup commands are responsible for putting the pipeline in the desired initial configuration based on 
    this session's associated reservation. For example, setup commands can be used by the pipeline user to set the 
    initial radio frequency.

    @note Before running the session setup commands, this method also registers itself with the pipeline. This must
          happen after the pipeline setup commands have been executed (this callback is automatically called after that 
          occurs).
    @note Session setup command failures will never trigger the errback chain because they are often recoverable with 
          additional input from the user, unlike pipeline setup commands. 
    
    @param pipeline_setup_commands_results  An array containing the results of the pipeline setup commands. May be None
                                            if there were no pipeline setup commands.
    @return Returns a DeferredList that will be fired with the results of the session setup commands. If this session
            doesn't specify any session setup commands, a pre-fired (with None) deferred will be returned.
    """
    
    running_setup_commands = []

    # Register the session with its pipeline
    self.active_pipeline.register_session(self)

    # Run the session setup commands
    if self.setup_commands is not None:
      for temp_command in self.setup_commands:
        temp_command_deferred = self.command_parser.parse_command(temp_command, user_id = self.user_id)
        running_setup_commands.append(temp_command_deferred)

      # Aggregate the setup command deferreds into a DeferredList
      return defer.DeferredList(running_setup_commands, consumeErrors = True)
    else:
      # No session setup commands to run
      return defer.succeed(None)

  def _activate_session(self, setup_command_results):
    """ Marks the session as active.

    This callback marks the session as active after its setup commands have been executed.

    @param setup_command_results  An array containing the results of the Session setup commands.
    @return Passes along the unmodified setup command results originally passed to this callback.
    """

    # Activate the session
    self._active = True

    return setup_command_results
  
  def _session_setup_error(self, failure):
    """ Cleans up after session-fatal errors and passes the failure along.

    This callback handles some session-fatal errors that may have occured when setting up the session. For example, it 
    will be called if a pipeline setup command fails to execute. It cleans up after errors by rolling back any state 
    changes that may have been made (such as pipeline/hardware locks).

    @note Because session setup command errors aren't fatal, they won't trigger this callback.
    @note This callback returns the original Failure after it has cleaned up the session. This will allow the session
          coordinator to detect that the session has failed and take the appropriate actions.
    @note Because DeferredList wraps Failures in a FirstError instance, the failure will be flattened before being
          returned so it will always be consistent for the session coordinator.

    @param failure  A Failure object encapsulating the error (or FirstError if it was a DeferredList that failed).
    @return Returns the Failure object encapsulating the fatal exception.
    """

    # Free up the pipeline by releasing any pipeline/hardware locks that may have been made. This callback only ever 
    # runs after the pipeline has been successfully reserved by this session, thus there is no possibility of unlocking
    # a pipeline that another session is using.
    self.active_pipeline.free_pipeline()

    # Check if the fatal error is a FirstError type, indicating it came from a DeferredList and needs to be flattened
    if isinstance(failure.value, defer.FirstError):
      return failure.value.subFailure
    else:
      # Just a normal exception, re-raise it
      return failure

# Define session related exceptions
class SessionError(Exception):
  pass
class ProtocolAlreadyRegistered(SessionError):
  pass
