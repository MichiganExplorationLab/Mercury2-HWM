""" @package hwm.hardware.devices.drivers.mxl_antenna_controller.mxl_antenna_controller
This module contains the driver and command handler for the MXL Antenna Controller.
"""

# Import required modules
import logging, time
from twisted.internet.defer import inlineCallbacks
from hwm.hardware.devices.drivers import driver
from hwm.hardware.pipelines import pipeline
from hwm.command import command
from hwm.command.handlers import handler

class MXL_Antenna_Controller(driver.HardwareDriver):
  """ A driver for the custom MXL antenna controller.

  This HardwareDriver class provides an interface to the MXL antenna controller.
  """

  def __init__(self, device_configuration, command_parser):
    """ Sets up the antenna controller.

    @param device_configuration  A dictionary containing the controller's configuration options.
    @param command_parser        A reference to the active CommandParser instance. The antenna controller will use this 
                                 to calibrate and park the antenna when appropriate.
    """

    super(MXL_Antenna_Controller,self).__init__(device_configuration, command_parser)

    # Set configuration settings
    self.update_period = 2 # Seconds

    # Initialize the driver's command handler
    self._command_handler = AntennaControllerHandler(self)

    self._reset_controller_state()

  def prepare_for_session(self, session_pipeline):
    """ Prepares the antenna controller for use by a new session.

    @note This method loads the active 'tracker' service from the session pipeline. If no such service is available, the
          antenna controller will still respond to manual adjustments but it will not be able to automatically track a 
          target.

    @param session_pipeline  The Pipeline associated with the new session.
    @return Returns a deferred for the state update LoopingCall.
    """

    # Load the pipeline's active tracking service
    self._session_pipeline = session_pipeline
    self._tracker_service = None
    try:
      self._tracker_service = session_pipeline.load_service("tracker")
    except pipeline.ServiceTypeNotFound as e:
      # A tracker service isn't available, log the error
      logging.error("The MXL antenna controller could not load a tracking service from the session's pipeline.")

    # Register a callback with the tracking service
    if self._tracker_service is not None:
      self._tracker_service.register_position_receiver(self.process_new_position)

    # Start a looping call to update the tracker's state
    self._state_update_loop = task.LoopingCall(self._update_state)
    update_loop_deferred = self._state_update_loop.start(self.update_period)
    update_loop_deferred.addErrback(self._handle_state_update_error)
    return update_loop_deferred

  def cleanup_after_session(self):
    """ Resets the antenna controller to its idle state after the session using it has ended.

    @note The "calibrate_and_park" command executed in this method is run in kernel mode because it must always happen,
          regardless of the user controlling the session.

    @return Returns the deferred for the "calibrate_and_park" command call that goes out at the end of each session.
    """

    # Vertically calibrate and park the antenna
    command_request = {
      'command': "calibrate_and_park",
      'destination': self._session_pipeline.id+"."+self.id
    }
    command_deferred = self._command_parser.parse_command(command_request, user_id = None, kernel_mode = True)

    # Reset the device
    self._reset_controller_state()

    return command_deferred

  def get_state(self):
    """ Returns a dictionary that contains the current state of the antenna controller.

    @return Returns a dictionary containing select antenna controller state.
    """

    return self._controller_state

  def process_new_position(self, target_position):
    """ Instructs the antenna controller to point at the specified target.

    This callback commands the antenna to point at the specified target's azimuth/elevation. It is called every time the
    loaded "tracker" service has new position information.

    @throw May raise InvalidTargetPosition if the specified target position does not contain an azimuth or elevation.

    @param target_position  A dictionary containing details about the target's position, including its azimuth and
                            elevation.
    @return Returns the deferred for the "move" command.
    """

    # Verify the target's position
    if 'azimuth' not in target_position or 'elevation' not in target_position:
      raise InvalidTargetPosition("The provided target position is invalid (didn't contain an azimuth or elevation).")

    # Move the antenna
    command_request = {
      'command': "move",
      'destination': self._session_pipeline.id+"."+self.id,
      'parameters': {
        'azimuth': target_position['azimuth'],
        'elevation': target_position['elevation']
      }
    }
    command_deferred = self._command_parser.parse_command(command_request, 
                                                          user_id = self._session_pipeline.current_session.user_id)

    return command_deferred

  @inlineCallbacks
  def _update_state(self):
    """ Updates the antenna controller's state.

    This method queries the antenna controller for its current azimuth and elevation and saves it to the driver state.
    It should typically be called automatically using something like LoopingCall.

    @return Returns a dictionary containing the new device state. If an error occurs updating the state None will be
            returned instead.
    """

    # Query the antenna controller for it's current orientation
    command_request = {
      'command': "get_state",
      'destination': self._session_pipeline.id+"."+self.id
    }
    command_deferred = self._command_parser.parse_command(command_request, 
                                                          user_id = self._session_pipeline.current_session.user_id)
    result = yield command_deferred

    # Process the results
    if result['response']['status'] == "okay":
      self._controller_state['timestamp'] = int(time.time())
      self._controller_state['azimuth'] = result['response']['azimuth']
      self._controller_state['elevation'] = result['response']['elevation']
    else:
      return None 

  def _handle_state_update_error(self, failure):
    """ Handles errors that may occur during the state update loop.

    This errback handles any exceptions that may be thrown during the state update loop.

    @param failure  A Failure object encapsulating the error.
    @return Returns False after logging the error.
    """

    # Log the error
    logging.error("An error occured while updating '"+self.id+"' device state: '"+failure.getErrorMessage()+"'")
    # TODO: Log the error to the driver's state dictionary

    # Stop the event loop just incase it's still running
    if self._state_update_loop.running:
      self._state_update_loop.stop()

    return False

  def _reset_controller_state(self):
    """ Resets the controller's state initially and in between sessions.
    """

    # Set the driver's attributes
    self._current_position = None
    self._tracker_service = None
    self._session_pipeline = None
    self._controller_state = {
      "timestamp": None,
      "azimuth": 0.0,
      "elevation": 0.0,
      "state": None
    }

class AntennaControllerHandler(handler.DeviceCommandHandler):
  """ This command handler processes commands for the MXL Antenna Controller.
  """

  def command_move(self, active_command):
    """ Moves the antenna to the location specified in the command.

    @throw May throw CommandError if an error occurs while instructing the antenna to move.

    @param active_command  The currently executing Command.
    @return Returns a dictionary containing the results of the move command.
    """

    # Build and send the command request
    request = self._build_request("W", {'az': command.parameters['azimuth'], 'el': command.parameters['elevation']})
    response = self._send_commands([request])

    # Check the response and return the move_antenna command response
    if response[0]['status'] == "okay":
      self.driver._controller_state['state'] = "active"
      return {'message': "The antenna is being moved."}
    else:
      raise command.CommandError("An error occured while attempting to move the antenna: '"+response[0]['message']+"'")

  def settings_move(self):
    """ Provides meta-data for the "move" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    # Define a schema for parameters
    command_parameters = [
      {
        "type": "number",
        "minvalue": 0,
        "maxvalue": 360,
        "required": True,
        "title": "azimuth",
        "description": "The desired azimuth."
      },
      {
        "type": "number",
        "minvalue": 0,
        "maxvalue": 210,
        "required": True,
        "title": "elevation",
        "description": "The desired elevation."
      }
    ]

    return build_metadata_dict(command_parameters, 'move', self.name, requires_active_session = True,
                               schedulable = True)

  def command_park(self, command):
    """ Parks the antenna.

    This command parks the antenna at an azimuth of 270 degrees, and an elevation of 0 degrees.
  
    @throw May throw CommandError if an error occurs while instructing the antenna to park.

    @param command  The currently executing Command.
    @return Returns a dictionary containing the results of the park command.
    """

    # Build and send the command request
    request = self._build_request("park")
    response = self._send_commands([request])

    # Check the response and return the park command response
    if response[0]['status'] == "okay":
      self.driver._controller_state['state'] = "parking"
      return {'message': "The antenna is being parked."}
    else:
      raise command.CommandError("An error occured while parking the antenna: '"+response[0]['message']+"'")

  def settings_park(self):
    """ Provides meta-data for the "park" command.

    @return Returns a dictionary containing meta-data about the command. 
    """

    return build_metadata_dict([], 'park', self.name, requires_active_session = True)

  def command_calibrate(self, command):
    """ Completely calibrates the antenna.

    This command calibrates the antenna's azimuth and elevation by rotating it until it hits the vertical and horizontal 
    hardstops, at which point it will tare the azimuth and elevation.

    @note This command can only be interrupted by a "stop" command. Any "move" commands received when the antenna is 
          being calibrated will be ignored.

    @throw May throw CommandError if an error occurs while starting the calibration.

    @param command  The currently executing command.
    @return Returns a dictionary containing the results of the calibration.
    """

    # Build and send the command request
    request = self._build_request("cal")
    response = self._send_commands([request])

    # Check the response and return the calibration results
    if response[0]['status'] == "okay":
      self.driver._controller_state['state'] = "calibrating"
      return {'message': "The antenna is being calibrated."}
    else:
      raise command.CommandError("An error occured while calibrating the antenna: '"+response[0]['message']+"'")

  def settings_calibrate(self):
    """ Provides meta-data for the "calibrate" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'calibrate', self.name, requires_active_session = True)

  def command_calibrate_vert(self, command):
    """ Performs a vertical calibration.

    This command performs a vertical (El) calibration only. This command exists because the elevation tends to drift off
    quicker than the azimuth.

    @note This command can only be interrupted by a "stop" command. Any "move" commands received when the antenna is 
          being vertically calibrated will be ignored.

    @throw May throw CommandError if an error occurs while starting the vertical calibration.

    @param command  The currently executing command.
    @return Returns a dictionary containing the results of the vertical calibration.
    """

    # Build and send the command request
    request = self._build_request("vert_cal")
    response = self._send_commands([request])

    # Check the response and return the results
    if response[0]['status'] == "okay":
      self.driver._controller_state['state'] = "calibrating"
      return {'message': "The antenna is being vertically calibrated."}
    else:
      raise command.CommandError("An error occured while vertically calibrating the antenna: '"+response[0]['message']+"'")

  def settings_calibrate_vert(self):
    """ Provides meta-data for the "calibrate_vert" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'calibrate', self.name, requires_active_session = True)

  def command_calibrate_and_park(self, command):
    """ Performs a full calibration and parks the antenna.

    This command calibrates the azimuth and elevation of the antenna and parks it at its rest position. 

    @note The "calibrate" command can only be interrupted by a "stop" command. Any "move" commands received when the 
          antenna is being calibrated will be ignored.

    @throw May throw CommandError if an error occurs while instructing the antenna to calibrate and park.

    @param command  The currently executing command.
    @return Returns a dictionary containing the results of the calibration and park commands.
    """

    # Build and send the command requests
    request_calibrate = self._build_request("cal")
    request_park = self._build_request("park")
    responses = self._send_commands([request_calibrate, request_park])

    # Check the responses
    if responses[0]['status'] == "okay" and responses[1]['status'] == "okay":
      self.driver._controller_state['state'] = "calibrating"
      return {'message': "The antenna is being fully calibrated and will be parked at an Az/El of 270/0."}
    else:
      error_message = responses[0]['message'] if responses[0]['status'] == "error" else responses[1]['message']
      raise command.CommandError("An error occured while attempting to calibrate and park the antenna: '"+error_message+"'")

  def settings_calibrate_and_park(self):
    """ Provides meta-data for the "calibrate_and_park" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'calibrate_and_park', self.name, requires_active_session = True)

  def command_get_state(self, command):
    """ Queries the antenna controller for its current state.

    This command loads and returns the controller's current state (i.e. its azimuth and elevation).
    
    @note If the antenna controller is out of calibration, this command may not return accurate results.

    @throw May throw CommandError if an error occurs while fetching the controller's state.

    @param command  The currently executing command.
    @return Returns a dictionary containing the current azimuth and elevation of the antenna.
    """

    # Build and send the command request
    request = self._build_request("C2")
    response = self._send_commands([request])

    # Check the response and return the results
    if response[0]['status'] == "okay":
      return {'azimuth': response[0]['azimuth'], 'elevation': response[0]['elevation']}
    else:
      raise command.CommandError("An error occured fetching the antenna controller state: '"+response[0]['message']+"'")

  def command_stop(self, command):
    """ Stops the antenna.

    This command instructs the antenna controller to stop executing whatever action it may currently be executing. It
    will not be calibrated or parked after being stopped.

    @throw May throw CommandError if an error occurs while instructing the antenna to park.

    @param command  The currently executing command.
    @return Returns a dictonary containing the results of the stop command.
    """

    # Build and send the command request
    request = self._build_request("s")
    response = self._send_commands([request])

    # Check the response
    if response[0]['status'] == "okay":
      self.driver._controller_state['state'] = "stopped"
      return {'message': "The antenna has been stopped."}
    else:
      raise command.CommandError("An error occured while stopping the antenna: '"+response[0]['message']+"'")

  def settings_stop(self):
    """ Provides meta-data for the "stop" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'stop', self.name, requires_active_session = True)

  def command_stop_emergency(self, command):
    """ Stops the antenna in the event of an emergency.

    This command simulates a press of the emergency stop button on the antenna controller. An emergency stop differs 
    from a normal stop in that, after stopped, the device will not respond to any commands until the 'S' command is sent 
    again to bring the antenna controller out of emergency stop mode.

    @throw May throw CommandError if an error occurs while performing an emergency stop.
    
    @param command  The currently executing command.
    @param Returns a dictionary containing the results of the emergency stop.
    """

    # Build and send the command request
    request = self._build_request("S")
    response = self._send_commands([request])

    # Check the response
    if response[0]['status'] == "okay":
      self.driver._controller_state['state'] = "emergency_stopped"
      return {'message': "The antenna has been stopped and placed in emergency mode. It will not respond to new "+
                         "commands until it receives another emergency stop command."}
    else:
      raise command.CommandError("An error occured while performing the emergency stop: '"+response[0]['message']+"'")

  def settings_stop_emergency(self):
    """ Provides meta-data for the "stop_emergency" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'stop_emergency', self.name, requires_active_session = True, dangerous = True)

class AntennaControllerError(Exception):
  pass
class InvalidTargetPosition(AntennaControllerError):
  pass
