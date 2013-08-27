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
  
  def __init__(self, reservation_schedule, device_manager, pipeline_manager, command_parser):
    """ Sets up the session coordinator instance.
    
    @param reservation_schedule  A reference to the schedule to coordinate.
    @param device_manager        A reference to a device manager that has been initialized with the available hardware. 
    @param pipeline_manager      A reference to a pipeline manager instance.
    @param command_parser        The CommandParser object that will be used to execute the session setup commands.
    """
    
    # Set the resource references
    self.schedule = reservation_schedule
    self.devices = device_manager
    self.pipelines = pipeline_manager
    self.command_parser = command_parser
    self.config = configuration.Configuration
    
    # Initialize coordinator attributes
    self.active_sessions = {} # Sessions that are currently running or being prepared to run
    self.closed_sessions = [] # Sessions that have been completed or experienced a fatal error during initialization,
                              # this is just an array of reservation IDs so that their session objects can get garbage
                              # collected.
  
  def coordinate(self):
    """ Coordinates the operation of the hardware manager.
    
    This method coordinates the hardware manager by performing periodic maintenance functions such as instructing the 
    schedule manager to update its schedule, checking for newly active reservations, and creating sessions as the 
    schedule dictates. This method is called periodically using a LoopingCall which is started during the main
    initialization process.

    @note This method checks for completed sessions before it checks for new ones. Because this method is only run in
          a single thread, this allows back to back session scheduling.
    """
    
    # Update the schedule if required
    self._update_schedule()
    
    # Check for completed sessions:
    # TODO: Check for completed sessions
    
    # Check the schedule for newly active reservations
    self._check_for_new_reservations()
    
    print 'COORDINATE'

  def load_reservation_session(self, reservation_id):
    """ Returns the Session instance for the requested reservation.

    This method returns the Session for the specified reservation, assuming that the reservation is active and that a
    Session instance has been created for it. It is typically used by network protocols to associate connections with 
    sessions.

    @throws Raises SessionNotFound if the specified reservation does not yet have an associated session or, if it does,
            if its session is not active (can occur if a protocol tries to load a session that is still in the process
            of executing its setup commands).

    @param reservation_id  The ID of the requested session.
    @return Returns the Session that represents the specified reservation.
    """

    # Check if the session has been created
    if reservation_id in self.active_sessions:
      requested_session = self.active_sessions[reservation_id]
    else:
      raise SessionNotFound("The reservation '"+reservation_id+"' does not exist or hasn't started yet.")

    # Make sure that the session is active
    if not requested_session.is_active:
      raise SessionNotFound("The reservation '"+reservation_id+"' is not active yet.")

    return requested_session
  
  def _check_for_new_reservations(self):
    """ Sets up new reservations defined in the reservation schedule.
    
    This method checks for newly active reservations in the reservation schedule, sets up Session objects for them, and
    reserves the pipeline specified in the reservation.
    
    @note If a session-fatal error occurs during the session initialization process, it will be logged by callbacks in 
          this class and gracefully fail.
    """
    
    # Get the list of active reservations
    active_reservations = self.schedule.get_active_reservations()
    
    # Check for new active reservations
    for active_reservation in active_reservations:
      if (active_reservation['reservation_id'] not in self.active_sessions and
          active_reservation['reservation_id'] not in self.closed_sessions):
        # Load the reservation's pipeline
        try:
          requested_pipeline = self.pipelines.get_pipeline(active_reservation['pipeline_id'])
        except pipeline_manager.PipelineNotFound:
          logging.error("The pipeline requested for reservation '"+active_reservation['reservation_id']+"' could not "+
                        "be found. Requested pipeline: "+active_reservation['pipeline_id'])
          self.closed_sessions.append(active_reservation['reservation_id'])
          continue
        
        # Create a session object for the newly active reservation
        self.active_sessions[active_reservation['reservation_id']] = session.Session(active_reservation, 
                                                                                     requested_pipeline,
                                                                                     self.command_parser)
        session_init_deferred = self.active_sessions[active_reservation['reservation_id']].start_session()
        session_init_deferred.addCallbacks(self._session_init_complete,
                                           errback = self._session_init_failed,
                                           callbackArgs = [active_reservation['reservation_id']],
                                           errbackArgs = [active_reservation['reservation_id']])
  
  def _session_init_complete(self, session_command_results, reservation_id):
    """ Called once a new session is up and running.
    
    This callback is called after the associated session is up and running. It registers that the session is running
    and notes any failed session setup commands (which will be indicated in session_command_results).
    
    @param session_command_results  An array containing the results of each session setup command. If the reservation
                                    didn't specify any setup commands, this will just be None.
    @param reservation_id           The ID of the reservation that was just started.
    @return Passes on the results of the session setup commands.
    """

    # Check for any failed session setup commands
    if session_command_results is not None:
      for (command_status, command_results) in session_command_results:
        if not command_status:
          logging.error("An non-fatal error occured executing a session setup command for the reservation: "+
                        reservation_id)

          # TODO: Log the error event in the state manager
  
  def _session_init_failed(self, failure, reservation_id):
    """ Handles fatal session initialization errors.
    
    This callback is responsible for handling fatal session errors such as failed pipeline setup commands and hardware
    locking errors by registering the failure and saving the reservation ID so it won't be re-run by coordinate().
    
    @note This callback (and those that follow it) does not need to worry about cleaning up after the session or 
          resetting the pipeline state. The session will do that automatically when it fails to setup the pipeline.
    
    @param failure         A Failure object encapsulating the session fatal error.
    @param reservation_id  The ID of the reservation that could not be started.
    @return Returns True after the error has been dealt with.
    """

    # Mark the session as closed and remove it from active_sessions so it won't be immediately re-run
    self.closed_sessions.append(reservation_id)
    self.active_sessions.pop(reservation_id, None)

    # Log the session failure
    logging.error("A fatal error occured while starting the session '"+reservation_id+"'.")
    # TODO: Log the error event in the state manager

    return True
  
  def _update_schedule(self):
    """ Updates the schedule if appropriate.
    
    This method instructs the schedule manager to update its schedule if it hasn't been updated recently ('recently' is
    defined by the 'schedule-update-period' configuration option).
    
    @return Returns the schedule update deferred from the schedule manager.
    """
    
    # Check if the schedule needs to be updated
    if (time.time()-self.schedule.last_updated) > self.config.get('schedule-update-period'):
      schedule_update_deferred = self.schedule.update_schedule()
      schedule_update_deferred.addErrback(self._error_updating_schedule)
    
    return schedule_update_deferred
  
  def _error_updating_schedule(self, failure):
    """ Handles failed schedule updates. 
    
    @param failure  The Failure object wrapping the generated exception.
    """
    
    # An error occured updating the schedule, just catch and log the error
    logging.error("The session coordinator could not update the active schedule. Received error: "+
                  failure.getErrorMessage())
    failure.trap(schedule.ScheduleError)

class CoordinatorError(Exception):
  pass
class SessionNotFound(CoordinatorError):
  pass
