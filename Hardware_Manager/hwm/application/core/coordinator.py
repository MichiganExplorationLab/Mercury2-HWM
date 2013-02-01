""" @package hwm.application.core.coordinator
Coordinates various periodic tasks used by the hardware manager.
 
This module contains a class that is used to coordinate the various sessions.
"""

# Import required modules
import logging

class SessionCoordinator:
  """Handles the creation and management of reservation sessions.
  
  This class is used to manage the pool of active sessions and reservations for the hardware manager. It stores the 
  references to the active schedule instance and all active session instances. In addition, it contains the method 
  which instructs the schedule manager to update its schedule, checks for new reservations, and creates sessions as
  needed (intended to be called with twisted.internet.task.LoopingCall).
  """
  
  def __init__(self, reservation_schedule):
    """Sets up the session coordinator instance.
    
    @param reservation_schedule  A reference to the schedule to execute.
    """
    
    # Set the schedule manager reference
    #self.schedule = reservation_schedule
    print 'init'
  
  def coordinate(self):
    """Coordinates the operation of the hardware manager.
    
    This method coordinates the hardware manager by performing periodic maintenance functions such as instructing the 
    schedule manager to update its schedule, checking for newly active reservations, and creating sessions as the 
    schedule dictates. This method is called periodically using LoopingCall which is started by setup().
    """
    
    print 'test'
