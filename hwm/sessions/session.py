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
  
  def __init__(self, reservation_configuration, session_pipeline):
    """ Initializes the new session.
    
    @note The provided pipeline is not locked when it is passed in. self.start_session needs to be called to lock up the
          pipeline and perform other session setup tasks.
    
    @param reservation_configuration  A dictionary containing the configuration settings for the reservation associated
                                      with this session.
    @param session_pipeline           The pipeline that this session will use.
    """
    
    # Set the session attributes
    self.active_pipeline = session_pipeline
    self.configuration = reservation_configuration
    self.active = False
  
  def start_session(self):
    """ Sets up the session for use.
    
    This method sets up a new session by:
    - Reserving the pipeline hardware
    - Executing the pipeline setup commands
    - Executing the session setup commands
    
    @throws May fire the errback callback chain on the returned deferred if there is a problem reserving the pipeline or
            executing the pipeline setup commands. This will cause the session coordinator to log the error and end the 
            session. Session setup commands don't generate a session-fatal error and are simply noted by the session 
            coordinator. This is done because this will often be recoverable with additional input from the session 
            user.
    
    @note All of the pipeline setup commands will always be executed before any of the session setup commands are.
    @note If a session fatal error occurs, the self._session_setup_error callback will automatically clean up the 
          session. Whatever calls this function (i.e. SessionCoordinator) doesn't need to worry about it.
    
    @return Returns a deferred that will be fired with the results of session setup commands (an array containing the 
            results for each setup command). 
    """
    
    # Lock the pipeline and pipeline hardware
    try:
      self.active_pipeline.reserve_pipeline()
    except pipeline.PipelineInUse:
      return defer.fail(pipeline.PipelineInUse("The pipeline requested for reservation '"+
                                               self.configuration['reservation_id']+"' could not be locked."))
    
    # Execute the pipeline setup commands
    pipeline_setup_deferred = self._run_pipeline_setup_commands()
    pipeline_setup_deferred.addCallback(self._run_session_setup_commands)
    pipeline_setup_deferred.addErrback(self._session_setup_error)
    
    return pipeline_setup_deferred
  
  def _run_pipeline_setup_commands(self):
    """ Runs the pipeline setup commands for the pipeline used by this session.
    
    This method runs the pipeline setup commands, which are responsible for putting the pipeline in its intended state
    before running the session setup commands.
    
    @return Returns a DeferredList that will be fired with the results of the pipeline setup commands. If any of the 
            pipeline setup commands fail, this method will return a deferred pre-fired with a Failure.
    """

    running_pipeline_setup_commands = []

    # Run the pipeline setup commands 
    if self.active_pipeline.setup_commands is not None:
      for temp_command in self.active_pipeline.setup_commands:
        # Make sure the command belongs to a system command handler or to a device used by the pipeline
        if (temp_command['destination'] not in self.command_parser.system_command_handlers and
            temp_command['destination'] not in self.active_pipeline.devices):
          raise PipelineConfigInvalid("The '"+self.id+"' pipeline configuration contained setup commands that used "+
                                      "command handlers that the pipeline does not have access to.")

    if 'setup_commands' in self.configuration:
      temp_command_deferred = self.active_pipeline.command_parser
      running_pipeline_setup_commands.append()
  
  def _run_session_setup_commands(self, pipeline_setup_commands_results):
    """ Runs the session setup commands.
    
    This callback runs the session setup commands after the pipeline setup commands have all been executed successfully.
    The session setup commands are responsible for putting the pipeline in the desired initial configuration based on 
    this session's associated reservation. For example, setup commands can be used by the pipeline user to set the 
    initial radio frequency.
    
    @param pipeline_setup_commands_results  An array containing the results of the pipeline setup commands.
    """
    
    
  
  def _session_setup_error(self, failure):
    """ Cleans up after session-fatal errors.
    
    This callback handles session fatal errors that may have occured during the session initialization process. For
    example, a failure to lock pipeline hardware or to execute pipeline setup commands both generate a fatal error 
    (leaving the session in a non-running state). It cleans up after the session by rolling back any state changes made 
    by the process so far (such as hardware locks).
    
    @throw Will re-raise the triggering exception so that the session coordinator can perform additional clean up if 
           necessary. Because DeferredList wraps its failures in another class, this method will flatten the exception
           so that it is consistent for the session coordinator.

    
    @param failure  A Failure object encapsulating the error (or FirstError if it was a DeferredList that failed).
    """
    
    
