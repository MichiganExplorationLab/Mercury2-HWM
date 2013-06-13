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
    @param session_pipeline           The pipeline that this session will use.
    @param command_parser             The CommandParser that will be used to execute the session setup commands.
    """
    
    # Set the session attributes
    self.active_pipeline = session_pipeline
    self.command_parser = command_parser
    self.configuration = reservation_configuration
    self.user_id = reservation_configuration['user_id']
    if 'setup_commands' in reservation_configuration:
      self.setup_commands = reservation_configuration['setup_commands']
    else:
      self.setup_commands = None
    self.active = False
  
  def start_session(self):
    """ Sets up the session for use.
    
    This method sets up a new session by:
    - Reserving the pipeline hardware
    - Executing the pipeline setup commands
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
      return defer.fail(pipeline.PipelineInUse("The pipeline requested for reservation '"+
                                               self.configuration['reservation_id']+"' could not be locked: "+
                                               self.active_pipeline.id))
    
    # Execute the pipeline setup commands
    pipeline_setup_deferred = self.active_pipeline.run_setup_commands()
    pipeline_setup_deferred.addCallback(self._run_setup_commands)
    pipeline_setup_deferred.addErrback(self._session_setup_error)
    
    return pipeline_setup_deferred
  
  def _run_setup_commands(self, pipeline_setup_commands_results):
    """ Runs the session setup commands.
    
    This callback runs the session setup commands after the pipeline setup commands have all been executed successfully.
    The session setup commands are responsible for putting the pipeline in the desired initial configuration based on 
    this session's associated reservation. For example, setup commands can be used by the pipeline user to set the 
    initial radio frequency.
    
    @param pipeline_setup_commands_results  An array containing the results of the pipeline setup commands. May be None
                                            if there were no pipeline setup commands.
    @return Returns a DeferredList that will be fired with the results of the session setup commands. If this session
            doesn't specify any session setup commands, a pre-fired (with None) deferred will be returned.
    """
    
    running_setup_commands = []

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
