""" @package hwm.sessions.session
Provides a representation for hardware manager usage sessions.

This module contains a class that is used to represent user access sessions (as specified in the reservation schedule).
"""

# Import required modules
import logging

class Session:
  """Represents a user hardware manager usage session.
  
  This class provides access to user reservation sessions, which are specified by the reservation schedule. Session
  instances are managed by the session coordinator, which is responsible for creating and destroying sessions as needed.
  """
  
  def __init__(self, session_pipeline):
    """Initializes the new session.
    
    This constructor sets up a new session and associates it with the specified hardware pipeline.
    
    @note The provided pipeline is locked by the pipeline manager before the session is initialized.
    
    @param session_pipeline  The pipeline that this session will use.
    """
    
    # Initialize the session attributes
    self.active_pipeline = session_pipeline
    
    
