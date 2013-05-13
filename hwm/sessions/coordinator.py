""" @package hwm.sessions.coordinator
Coordinates various periodic tasks used by the hardware manager.
 
This module contains a class that is used to coordinate the various sessions.
"""

# Import required modules
import logging, time
from hwm.core import configuration
from hwm.hardware.pipelines import pipeline, manager as pipeline_manager
from hwm.sessions import session, schedule

class SessionCoordinator:
  """ Handles the creation and management of reservation sessions.
  
  This class is used to manage the pool of active sessions and reservations for the hardware manager. It stores the 
  references to the active schedule instance and all active session instances. In addition, it contains the main 
  "program loop" that is responsible for periodically trigging schedule updates, checking for reservations, and 
  creating new sessions as needed.
  """
  
  def __init__(self, reservation_schedule, device_manager, pipeline_manager):
    """ Sets up the session coordinator instance.
    
    @param reservation_schedule  A reference to the schedule to coordinate.
    @param device_manager        A reference to a device manager that has been initialized with the available hardware. 
    @param pipeline_manager      A reference to a pipeline manager instance.
    """
    
    # Set the resource references
    self.schedule = reservation_schedule
    self.devices = device_manager
    self.pipelines = pipeline_manager
    self.config = configuration.Configuration
    
    # Initialize required attributes
    self.active_sessions = {}
  
  def coordinate(self):
    """ Coordinates the operation of the hardware manager.
    
    This method coordinates the hardware manager by performing periodic maintenance functions such as instructing the 
    schedule manager to update its schedule, checking for newly active reservations, and creating sessions as the 
    schedule dictates. This method is called periodically using a LoopingCall which is started during the main
    initialization process.
    """
    
    # Update the schedule if required
    self._update_schedule()
    
    # Create new session if needed
    self._check_for_new_reservations()
    
    print 'COORDINATE'
  
  def _check_for_new_reservations(self):
    """ This method checks for newly active reservations in the schedule.
    
    This method checks for newly active reservations in the reservation schedule and creates sessions for them.
    
    @note If an error is encountered when loading or reserving a pipeline the exception will be logged gracefully.
    """
    
    # Get the list of active reservations
    active_reservations = self.schedule.get_active_reservations()
    
    # Check for new active reservations
    for active_reservation in active_reservations:
      if active_reservation['reservation_id'] not in self.active_sessions:
        # Load the reservation's pipeline
        try:
          requested_pipeline = self.pipelines.get_pipeline(active_reservation['pipeline_id'])
        except pipeline_manager.PipelineNotFound:
          logging.error("The pipeline requested for reservation '"+active_reservation['reservation_id']+"' could not "+
                        "be found. Requested pipeline: "+active_reservation['pipeline_id'])
          continue
        
        # Try to reserve the pipeline
        try:
          requested_pipeline.reserve_pipeline()
        except pipeline.PipelineInUse:
          logging.error("The pipeline requested for reservation '"+active_reservation['reservation_id']+"' is "+
                        "currently being used and can not be locked.")
          continue
        
        # Create a session object for the newly active reservation
        self.active_sessions[active_reservation['reservation_id']] = session.Session(requested_pipeline)
  
  def _update_schedule(self):
    """ Updates the schedule if appropriate.
    
    This method instructs the schedule manager to update its schedule if it hasn't been updated recently.
    
    @return Returns the schedule update deferred from the schedule manager.
    """
    
    # Forward declarations
    schedule_update_deferred = None
    
    # Check if the schedule needs to be updated
    if (time.time()-self.schedule.last_updated) > self.config.get('schedule-update-period'):
      schedule_update_deferred = self.schedule.update_schedule()
      schedule_update_deferred.addErrback(self._error_updating_schedule)
    
    return schedule_update_deferred
  
  def _error_updating_schedule(self, failure):
    """ Handles failed schedule updates. 
    
    This is needed to keep the program from terminating if a schedule update fails.
    
    @param failure  The Failure object wrapping the generated exception.
    """
    
    # An error occured updating the schedule, just catch and log the error
    logging.error("The session coordinator could not update the active schedule. Received error: "+
                  failure.getErrorMessage())
    failure.trap(schedule.ScheduleError)
