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
            coordinator. This is done because this will often be recoverable with furthor input from the session user.
    
    @note All of the pipeline setup commands will always be executed before any of the session setup commands are.
    @note If a session fatal error occurs, a callback in this class with automatically clean up the session. It does not
          need to be done by the session coordinator.
    
    @return Returns a deferred that will be fired with the results of session setup commands if the session is up and
    """
    
    # Lock the pipeline and pipeline hardware
    try:
      requested_pipeline.reserve_pipeline()
    except pipeline.PipelineInUse:
      logging.error("The pipeline requested for reservation '"+self.configuration['reservation_id']+"' is "+
                    "currently being used and can not be locked.")
      return defer.fail()
    
