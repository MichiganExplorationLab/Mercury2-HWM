""" @package hwm.hardware.devices.drivers.sgp4_tracker.sgp4_tracker
This module contains a virtual driver and command handler for a standard SGP4 tracker.
"""

# Import required modules
import logging, time
import ephem
import math
from datetime import datetime
from twisted.internet import task, defer
from hwm.core.configuration import *
from hwm.hardware.devices.drivers import driver, service
from hwm.command import command
from hwm.command.handlers import handler

class SGP4TrackerDriver(driver.VirtualDriver):
  """ A virtual driver that provides a SGP4 tracking service.

  This virtual driver provides a 'tracker' service based on the SGP4 satellite propagation model.
  """ 

  def __init__(self, device_configuration, command_parser):
    """ Sets up the SGP4 tracker.

    @param device_configuration  A dictionary containing the tracker's configuration options.
    @param command_parser        A reference to the active CommandParser instance.
    """

    super(SGP4TrackerDriver,self).__init__(device_configuration, command_parser)

    # Initialize the driver's command handler
    self._command_handler = SGP4Handler(self)

    # Initialize the service that will perform the propagation
    self._propagation_service = SGP4PropagationService('sgp4_propagation_service', 'tracker')

    self._reset_tracker_state()

  def prepare_for_session(self, session_pipeline):
    """ Prepares the driver for use by a new session by starting the SGP4 tracking service.

    @param session_pipeline  The Pipeline associated with the new session.
    """

    # Start the tracking service
    self._propagation_service.start_tracker()

  def cleanup_after_session(self):
    """ Cleans up the tracker after the session using it has ended. """

    # Stop the propagation LoopingCall
    self._propagation_service.reset_tracker()

    self._reset_tracker_state()

  def get_state(self):
    """ Returns the current state of the SGP4 propagator.

    @return Returns a dictionary containing the current state of the SGP4 propagator.
    """

    return

  def _register_services(self, session_pipeline):
    """ Registers the SGP4 tracking service with the session pipeline.

    @param session_pipeline  The pipeline being used by the new session.
    """

    session_pipeline.register_service(self._propagation_service)

  def _reset_tracker_state(self):
    """ Resets the tracker's state, typically after a session has ended. """

    return

class SGP4PropagationService(service.Service):
  """ This service provides access to a SGP4 propagator.

  The SGP4 Propagation Service can be used by an antenna controller or similar device to determine the location of the 
  session's satellite of interest.
  """

  def __init__(self, service_id, service_type):
    """ Sets up the SGP4 propagation service.

    @param service_id     The unique service ID.
    @param service_type   The service type. Other drivers, such as the antenna controller driver, will search the active 
                          pipeline for this when looking for this service.
    """

    super(SGP4PropagationService,self).__init__(service_id, service_type)

    # Set configuration settings
    self.propagation_frequency = 2 # Seconds

    # Load the ground station's location
    self._global_config = Configuration
    self._station_longitude = self._global_config.get('station-longitude')
    self._station_latitude = self._global_config.get('station-latitude')
    self._station_altitude = self._global_config.get('station-altitude')

    self._reset_propagator_state()

  def start_tracker(self):
    """ Starts the SGP4 propagation loop.

    @note The SGP4 propagation depends on the target's TLE, which isn't available until the session setup commands have 
          been executed. As a result, The body of the propagation loop will be skipped until the TLE is available.

    @return Returns the deferred for the propagation LoopingCall.
    """

    # Create a LoopingCall to run the propagator
    self._propagation_loop = task.LoopingCall(self._propagate_tle)
    propagation_loop_deferred = self._propagation_loop.start(self.propagation_frequency)
    propagation_loop_deferred.addErrback(self._handle_propagation_error)
    return propagation_loop_deferred

  def reset_tracker(self):
    """ Stops the SGP4 propagator in between sessions. """

    # Stop the propagation loop if it's running
    if self._propagation_loop is not None and self._propagation_loop.running:
      self._propagation_loop.stop()
    self._reset_propagator_state()

  def register_position_receiver(self, callback):
    """ Registers the callback with the service.

    The SGP4 tracking service will call all registered callbacks everytime new position information is available. 
    Callbacks will be passed a dictionary containing the following elements:
    * timestamp
    * longitude 
    * latitude 
    * altitude 
    * azimuth
    * elevation

    @param callback  A method that will be called with the satellite's position every time new position information is 
                     available.
    """

    # Register the handler
    self._registered_handlers.append(callback)

  def set_tle(self, line_1, line_2):
    """ Sets the target's TLE.

    @param line_1  The first line of the TLE.
    @param line_2  The second line of the TLE.
    """

    # Set the TLE
    self._TLE_line_1 = line_1
    self._TLE_line_2 = line_2
    self._satellite = ephem.readtle("TARGET", self._TLE_line_1, self._TLE_line_2)

  def _propagate_tle(self):
    """ Propagates the configured TLE to determine the target's current position.

    This method performs a single iteration of propagation on the target's TLE to determine it's current location. The 
    new location will be passed to all registered callbacks.

    @return Returns a dictionary containing the target's current position if the TLE is set, and None otherwise.
    """

    # Make sure the TLE is available
    if self._satellite is not None:
      propagation_time = int(time.time())

      # Determine the current position of the satellite
      ground_station = ephem.Observer()
      ground_station.lon = self._station_longitude
      ground_station.lat = self._station_latitude
      ground_station.elevation = self._station_altitude
      ground_station.date = time.strftime("%Y/%m/%d %H:%M:%S", time.gmtime(propagation_time))
      ground_station.pressure = 0
      self._satellite.compute(ground_station)

      # Store the results
      self._target_position = {
        'timestamp': propagation_time,
        'longitude': math.degrees(self._satellite.sublong),
        'latitude': math.degrees(self._satellite.sublat),
        'altitude': self._satellite.elevation,
        'azimuth': math.degrees(self._satellite.az),
        'elevation': math.degrees(self._satellite.alt)
      }

      # Notify the handlers
      self._notify_handlers()

      return self._target_position

    return None

  def _notify_handlers(self):
    """ Notifies all registered handlers that new position information is available.
    
    This method sends the saved position information to all registered handlers.
    """

    # Notify all handlers 
    for handler_callback in self._registered_handlers:
      try:
        handler_callback(self._target_position)
      except Exception as e:
        # A receiver failed, catch and move on
        pass

  def _handle_propagation_error(self, failure):
    """ Handles any errors that may occur while executing the SGP4 propagation loop.
    
    @param failure  A Failure object encapsulating the error.
    @return Returns False after logging the error.
    """

    # Log the error
    logging.error("An error occured while running the '"+self._service_id+"' service, the service has been stopped: '"+
                  failure.getErrorMessage()+"'")
    # TODO: Log the error to the driver's state dictionary.

    # Stop the event loop just incase it's still running
    if self._propagation_loop.running:
      self._propagation_loop.stop()

    return False

  def _reset_propagator_state(self):
    """ Resets the propagator's state initially and in between sessions. """

    self._TLE_line_1 = None
    self._TLE_line_2 = None
    self._satellite = None
    self._propagation_loop = None
    self._registered_handlers = []
    self._target_position = {
      'timestamp': None,
      'longitude': None,
      'latitude': None,
      'altitude': None,
      'azimuth': None,
      'elevation': None
    }

class SGP4Handler(handler.DeviceCommandHandler):
  """ A command handler that handles commands for the SGP4 propagator virtual driver.
  """

  def command_start_tracking(self, active_command):
    """ Starts the SGP4 tracking service.

    If the service is already started, it will be indicated in the response.
    
    @param active_command  The executing Command. Contains the command parameters.
    @return Returns a dictionary containing the command response.
    """

    # Try to start the service
    service_response = self.driver._propagation_service.start_tracker()
    if service_response is None:
      return {'message': "The SGP4 tracking service is already running."}
    else:
      return {'message': "The SGP4 tracking service has been started."}

  def settings_start_tracking(self):
    """ Meta-data for the "start_tracking" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'start_tracking', self.name, requires_active_session = True)

  def command_stop_tracking(self, active_command):
    """ Stops the tracking service.

    This command will stop the SGP4 propagation event loop without resetting any of the service attributes. This will 
    allow it to easily be restarted by the user.
    
    @param active_command  The currently executing Command.
    @return Returns a dictionary containing the command response.
    """

    # Stop the service if it is running
    if self.driver._propagation_service._propagation_loop is not None and self.driver._propagation_service._propagation_loop.running:
      self.driver._propagation_service._propagation_loop.stop()
      return {'message': "The SGP4 tracker has been stopped."}
    else:
      return {'message': "The SGP4 tracker is not currently running."}

  def settings_stop_tracking(self):
    """ Meta-data for the "stop_tracking" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'stop_tracking', self.name, requires_active_session = True)

  def command_set_target_tle(self, active_command):
    """ Sets the tracker's active target.

    This command is used to set the tracker's active target's TLEs, which are used by the SGP4 propagator.
    
    @param active_command  The executing Command. Contains the satellite's TLEs.
    @return Returns a dictionary containing the command response.
    """

    # Validate the callsign
    if active_command.parameters is None or 'line_1' not in active_command.parameters or 'line_2' not in active_command.parameters:
      raise command.CommandError("Both TLE lines were not submitted with the command.")

    # Update the TLE
    self.driver._propagation_service.set_tle(active_command.parameters['line_1'], active_command.parameters['line_2'])

    return {'message': "The target's TLE has been set. All new position information will use the provided TLE."}

  def settings_set_target_tle(self):
    """ Meta-data for the "set_target_tle" command.
    
    @return Returns a dictionary containing meta-data about the command.
    """

    # The command parameters
    command_parameters = [
      {
        "type": "string",
        "minlength": 80,
        "maxlength": 80,
        "required": True,
        "title": "TLE_line_1",
        "description": "The first line of the target's TLE."
      },
      {
        "type": "string",
        "minlength": 80,
        "maxlength": 80,
        "required": True,
        "title": "TLE_line_2",
        "description": "The second line of the target's TLE."
      },
    ]

    return build_metadata_dict(command_parameters, 'set_target_tle', self.name, requires_active_session = True,
                               use_as_initial_value = True)
