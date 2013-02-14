""" @package hwm.sessions.coordinator
Coordinates various periodic tasks used by the hardware manager.
 
This module contains a class that is used to coordinate the various sessions.
"""

# Import required modules
import logging, time
from hwm.core import configuration
from hwm.hardware.pipelines import pipeline, manager
from hwm.sessions import session

class SessionCoordinator:
  """Handles the creation and management of reservation sessions.
  
  This class is used to manage the pool of active sessions and reservations for the hardware manager. It stores the 
  references to the active schedule instance and all active session instances. In addition, it contains the main 
  "program loop" that is responsible for periodically trigging schedule updates, checking for reservations, and 
  creating new sessions as needed.
  """
  
  def __init__(self, reservation_schedule, pipeline_manager):
    """Sets up the session coordinator instance.
    
    @param reservation_schedule  A reference to the schedule to execute.
    @param pipeline_manager      A reference to the pipeline manager object.
    """
    
    # Set the resource references
    self.schedule = reservation_schedule
    self.pipelines = pipeline_manager
    self.config = configuration.Configuration
    
    # Initialize required attributes
    self.last_updated = 0
    self.active_sessions = {}
  
  def coordinate(self):
    """Coordinates the operation of the hardware manager.
    
    This method coordinates the hardware manager by performing periodic maintenance functions such as instructing the 
    schedule manager to update its schedule, checking for newly active reservations, and creating sessions as the 
    schedule dictates. This method is called periodically using LoopingCall which is started by setup().
    """
    
    # Update the schedule if required
    if (time.time()-self.last_updated) > self.config.get('schedule-update-period'):
      schedule_update_deferred = self.schedule.update_schedule()
      schedule_update_deferred.addCallback(self._update_schedule_update_time)
    
    # Get the list of active reservations
    active_reservations = self.schedule.get_active_reservations()
    
    # Check for new active reservations
    for active_reservation in active_reservations:
      if active_reservation['reservation_id'] not in self.active_sessions:
        # Load the reservation's pipeline
        try:
          requested_pipeline = self.pipelines.get_pipeline(active_reservation['pipeline_id'])
        except manager.PipelineNotFound:
          logging.error("The pipeline requested for reservation '"+active_reservation['reservation_id']+"' could not "+
                        "be found. Requested pipeline: "+active_reservation['pipeline_id'])
          continue
        
        # Try to lock the pipeline
        try:
          requested_pipeline.reserve_pipeline()
        except pipeline.PipelineInUse:
          logging.error("The pipeline requested for reservation '"+active_reservation['reservation_id']+"' is "+
                        "currently being used and can not be locked.")
          continue
        
        # Create a session object for the new reservation
        self.active_sessions[active_reservation['reservation_id']] = session.Session(requested_pipeline)
  
  def _update_schedule_update_time(self, downloaded_schedule):
    """This callback updates the schedule last fetched time.
    
    @param downloaded_schedule  The new schedule from the schedule downloader. Ignored.
    """
    
    self.last_updated = time.time()