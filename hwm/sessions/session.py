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
    self.active = False

    self.data_streams = []
    self.telem_streams = []

  def write_telemetry_datum(self, source_id, stream, timestamp, telemetry_datum, **extra_headers):
    """ Writes the provided telemetry datum to the registered telemetry streams.
    
    This method passes the provided telemetry datum and headers to all registered pipeline telemetry streams. It will be
    called by this session's associated pipeline and facilitates the sending of pipeline telemetry (state, additional 
    data streams, etc.) from the pipeline (and its devices) to the end user via the telemetry's streams 
    write_telemetry_datum() method.
    
    @note Because the telemetry stream uses HTTP, it's actually more of a packet stream than a true data stream (like 
          the main pipeline stream). The Twisted protocol that sends the pipeline telemetry to the end user uses 
          addressed HTTP packets to ensure that multiple unrelated data streams can be multi-plexed over the same socket
          without conflict. Thus, each call to this method will be with a complete "packet" of pipeline telemetry (i.e. 
          a JSON state string or single webcam frame). What ever receives these HTTP packets on the other side of the 
          socket will be responsible for assembling and displaying them in a coherent way.

    @param source_id        The ID of the device or pipeline that generated the telemetry datum.
    @param stream           A string identifying which of the device's telemetry streams the datum should be associated 
                            with.
    @param timestamp        A unix timestamp signifying when the telemetry was assembled.
    @param telemetry_datum  The actual telemetry datum. Can take many forms (e.g. a JSON string or binary webcam image).
    @param **extra_headers  A dictionary containing extra keyword arguments that should be included as additional
                            headers when sending the telemetry datum.
    """

    # Pass along the telementry datum
    for telemetry_stream in self.telem_streams:
      telemetry_stream.write_telemetry_datum(source_id, stream, timestamp, telemetry_datum, **extra_headers)

  def write_to_output_stream(self, output_data):
    """ Writes the provided data chunk to the registered data streams. 
    
    This method writes the provided chunk of data (pipeline output) to all registered data streams. This method will 
    typically be called by the pipeline associated with this session and facilitates passing pipeline output from the 
    Pipeline class to the end user.

    @note Whenever the pipeline generates any output data, this method will call the write_to_output_stream() method for
          every data stream registered to this session. The data passed to this method will be of arbitrary size.

    @param output_data  A data chunk of arbitrary size that is to be ouput to the registered data streams.
    """

    # Pass the data along to the registered data streams
    for data_stream in self.data_streams:
      data_stream.write_to_output_stream(output_data)
 
  def write_to_input_stream(self, input_data):
    """ Writes the provided chunk of data to the pipeline input stream.

    This method writes the supplied chunk of data to the input stream of the pipeline associated with this session. This
    is one step in the process of getting the pipeline input data from the end user to the pipeline's input device
    (typically a radio).

    @note This method sends the provided data to the pipeline via its write_to_pipeline() method.
    @note Even though sessions can register multiple data streams, only one data stream should write to this method at a
          time. If this convention isn't followed, it could result in jumbled data being sent to the pipeline (due to
          the nature of streams).
    
    @param input_data  A data chunk of arbitrary size that is to be written to the pipeline's input stream. Normally,
                       this comes from a Twisted protocol instance linked to the end user.
    """

    # Pass the data along to the pipeline
    self.active_pipeline.write_to_pipeline(input_data)

  def register_data_stream(self, data_stream):
    """ Registers the provided data stream with the session.

    This method is used to register the main pipeline data stream source/destination with the session. Typically, this 
    data stream will consist of a Twisted Protocol class that routes the main pipeline data stream to and from the 
    session user.

    @note Multiple data streams can be registered to the session. Any data that the pipeline generates will be routed to
          all registered data streams. This allows for simultaneous connections to the same session. However, if
          multiple data streams attempt to write to the session the data will be interlaced randomly (because of the
          stream based nature of the system).
    
    @throw Throws StreamAlreadyRegistered in the event that a data stream is registered twice.
    
    @param data_stream  An instance of a class that can generate and listen for pipeline data. Typically, this will be
                        a Twisted protocol.
    """

    # Check if the data stream is already registered
    if data_stream in self.data_streams:
      raise StreamAlreadyRegistered("The specified pipeline data stream has already been registered with the session.")

    self.data_streams.append(data_stream)
  
  def register_telemetry_stream(self, telem_stream):
    """ Registers the provided telemetry stream with the session.

    This method registers the supplied telemetry stream with the session. The session will use this reference to pass 
    extra data (i.e. not the main pipeline output) from the pipeline to the end user. This data will consist of things 
    like extra data streams (e.g. a webcam feed) and live pipeline device state. This stream will be directed, with the 
    data flowing from the pipeline to the end user (through this session).

    @note This method allows multiple telemetry streams to be registered with the session. Whenever the pipeline
          generates any telemetry, it will automatically be sent to each registered telemetry stream.

    @throw Raises StreamAlreadyRegistered in the event that a telemetry stream is registered twice.

    @param telem_stream  An instance of a class that can receive pipeline telemetry data. Typically, this will be a 
                         Twisted protocol.
    """

    # Check if the telemetry stream is already registered
    if telem_stream in self.telem_streams:
      raise StreamAlreadyRegistered("The specified telemetry stream has already been registered with the session.")

    self.telem_streams.append(telem_stream)

  def start_session(self):
    """ Sets up the session for use.
    
    This method sets up a new session by:
    - Reserving the pipeline hardware
    - Executing the pipeline setup commands
    - Executing the Pipeline (and in turn Driver) class setup methods
    - Executing the session setup commands
    
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
    pipeline_setup_deferred.addErrback(self._session_setup_error)
    
    return pipeline_setup_deferred
  
  def _run_setup_commands(self, pipeline_setup_commands_results):
    """ Runs the session setup commands.
    
    This callback runs the session setup commands after the pipeline setup commands have all been executed successfully
    and after the Pipeline activation method (and in turn the Device activation methods) has been called. The session 
    setup commands are responsible for putting the pipeline in the desired initial configuration based on this session's 
    associated reservation. For example, setup commands can be used by the pipeline user to set the initial radio 
    frequency.

    @note Before running the session setup commands, this method also registers itself with the pipeline. This must
          happen after the pipeline setup commands have been executed (this callback is automatically called after that 
          occurs).
    
    @param pipeline_setup_commands_results  An array containing the results of the pipeline setup commands. May be None
                                            if there were no pipeline setup commands.
    @return Returns a DeferredList that will be fired with the results of the session setup commands. If this session
            doesn't specify any session setup commands, a pre-fired (with None) deferred will be returned.
    """
    
    running_setup_commands = []

    # Register the session with the pipeline
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
class StreamAlreadyRegistered(Exception):
  pass
