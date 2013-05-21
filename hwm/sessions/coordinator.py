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
    
    # Initialize coordinator attributes
    self.active_sessions = {} # Sessions that are currently running or being prepared to run
    self.closed_sessions = {} # Sessions that have been completed or experienced a fatal error during initialization
  
  def coordinate(self):
    """ Coordinates the operation of the hardware manager.
    
    This method coordinates the hardware manager by performing periodic maintenance functions such as instructing the 
    schedule manager to update its schedule, checking for newly active reservations, and creating sessions as the 
    schedule dictates. This method is called periodically using a LoopingCall which is started during the main
    initialization process.
    """
    
    # Update the schedule if required
    self._update_schedule()
    
    # Check for completed sessions
    
    # Check the schedule for newly active reservations
    self._check_for_new_reservations()
    
    print 'COORDINATE'
  
  def _check_for_new_reservations(self):
    """ This method checks for newly active reservations in the schedule.
    
    This method checks for newly active reservations in the reservation schedule and creates sessions for them.
    
    @note If a session-fatal error occurs during the session initialization process, it will be logged and 
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
        
        # Create a session object for the newly active reservation
        self.active_sessions[active_reservation['reservation_id']] = session.Session(active_reservation, 
                                                                                     requested_pipeline)
        session_init_deferred = self.active_sessions[active_reservation['reservation_id']].start_session()
        session_init_deferred.addCallbacks(self._session_init_complete,
                                           self._session_init_failed,
                                           callbackArgs = (active_reservation['reservation_id']),
                                           errbackArgs = (active_reservation['reservation_id']))
  
  def _session_init_complete(self, session_command_results, reservation_id):
    """ Called once a new session is up and running.
    
    This callback is called after the associated session is up and running. It registers that the session is running
    and notes any failed session setup commands (which will be indicated in session_command_results).
    
    @param session_command_results  An array containing the results of each session setup command.
    @param reservation_id           The ID of the reservation that was just started.
    @return Passes on the results of the session setup commands.
    """
    
    
  
  def _session_init_failed(self, failure, reservation_id):
    """ Handles fatal session initialization errors.
    
    This callback is responsible for handling fatal session errors such as failed pipeline setup commands and hardware
    locking errors by registering the failure and saving the reservation ID so it won't be re-run by coordinate().
    
    @note This callback does not need to worry about cleaning up after the session or resetting the pipeline state. The
          session will do that automatically when it fails to setup the pipeline.
    
    @param failure         A Failure object encapsulating the session fatal error.
    @param reservation_id  The ID of the reservation that could not be started.
    @return Returns True after the error has been dealt with.
    """
    
    
  
  def _update_schedule(self):
    """ Updates the schedule if appropriate.
    
    This method instructs the schedule manager to update its schedule if it hasn't been updated recently.
    
    @return Returns the schedule update deferred from the schedule manager.
    """
    
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
