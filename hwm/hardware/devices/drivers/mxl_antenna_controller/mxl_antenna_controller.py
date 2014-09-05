""" @package hwm.hardware.devices.drivers.mxl_antenna_controller.mxl_antenna_controller
This module contains the driver and command handler for the MXL Antenna Controller.
"""

# Import required modules
import logging, time, json
import urllib, urllib2
from twisted.internet import task, defer, threads
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
    self.update_period = self.settings['update_period']
    self.controller_api_endpoint = self.settings['controller_api_endpoint']
    self.controller_api_timeout = self.settings['controller_api_timeout']

    # Initialize the driver's command handler
    self._command_handler = AntennaControllerHandler(self)

    self._reset_controller_state()

  def prepare_for_session(self, session_pipeline):
    """ Prepares the antenna controller for use by a new session.

    @note This method loads the active 'tracker' service from the session pipeline. If no such service is available, the
          antenna controller will still respond to manual adjustments but it will not be able to automatically track a 
          target.

    @param session_pipeline  The Pipeline associated with the new session.
    @return Returns a deferred for the state update LoopingCall if a 'tracker' service can be loaded and False
            otherwise.
    """

    # Load the pipeline's active tracking service
    self._session_pipeline = session_pipeline
    self._tracker_service = None
    try:
      self._tracker_service = session_pipeline.load_service("tracker")
    except pipeline.ServiceTypeNotFound as e:
      # A tracker service isn't available
      logging.warning("The '"+self.id+"' device could not load a 'tracker' service from the session's pipeline.")
      return False

    # Register a callback with the tracking service
    self._tracker_service.register_position_receiver(self.process_new_position)

    # Start a looping call to update the tracker's state
    #self._state_update_loop = task.LoopingCall(self._update_state)
    #update_loop_deferred = self._state_update_loop.start(self.update_period)
    #update_loop_deferred.addErrback(self._handle_state_update_error)
    #return update_loop_deferred
    return False

  def cleanup_after_session(self):
    """ Resets the antenna controller to its idle state after the session using it has ended.

    @note The "calibrate" command executed in this method is run in kernel mode because it must always happen, 
          regardless of the user controlling the session.

    @return Returns the deferred for the "calibrate" command call that goes out at the end of each session.
    """

    # Calibrate the antenna
    command_request = {
      'command': "calibrate",
      'destination': self._session_pipeline.id+"."+self.id
    }
    command_deferred = self._command_parser.parse_command(command_request, user_id = None, kernel_mode = True)
    command_deferred.addErrback(self._command_error)

    # Stop the state update LoopingCall
    if self._state_update_loop is not None and self._state_update_loop.running:
      self._state_update_loop.stop()

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

    target_elevation = 0 if target_position['elevation']<0 else int(target_position['elevation'])

    # Move the antenna
    command_request = {
      'command': "move",
      'destination': self._session_pipeline.id+"."+self.id,
      'parameters': {
        'azimuth': int(target_position['azimuth']),
        'elevation': target_elevation
      }
    }
    command_deferred = self._command_parser.parse_command(command_request, 
                                                          user_id = self._session_pipeline.current_session.user_id)
    command_deferred.addErrback(self._command_error)

    return command_deferred

  def _command_error(self, failure):
    """ Handles errors that may occur when executing an antenna controller command. 

    @param failure  A Failure instance containing details about the error. 
    """

    logging.error(failure.value.message)

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

      defer.returnValue(self.get_state())
    else:
      defer.returnValue(None)

  def _handle_state_update_error(self, failure):
    """ Handles errors that may occur during the state update loop.

    This errback handles any exceptions that may be thrown during the state update loop.

    @param failure  A Failure object encapsulating the error.
    @return Returns False after logging the error.
    """

    # Log the error
    logging.error("An error occured while updating the '"+self.id+"' device state: '"+failure.getErrorMessage()+"'")
    
    # TODO: Log the error to the driver's state dictionary

    # Stop the event loop just incase it's still running
    if self._state_update_loop.running:
      self._state_update_loop.stop()

    return False

  def _reset_controller_state(self):
    """ Resets the controller's state initially and in between sessions.
    """

    # Set the driver's attributes
    self._state_update_loop = None
    self._current_position = None
    self._tracker_service = None
    self._session_pipeline = None
    self._controller_state = {
      'timestamp': None,
      'azimuth': 0,
      'elevation': 0,
      'state': "inactive"
    }

class AntennaControllerHandler(handler.DeviceCommandHandler):
  """ This command handler processes commands for the MXL Antenna Controller.
  """

  @inlineCallbacks
  def command_move(self, active_command):
    """ Moves the antenna to the location specified in the command.

    @param active_command  The currently executing Command.
    @return Returns a deferred that will be fired with a dictionary containing the results of the move command. If the 
            command fails, the returned deferred will error.
    """

    # Build and send the command request
    request = self._build_request("W", {'azimuth': int(active_command.parameters['azimuth']),
                                        'elevation': int(active_command.parameters['elevation'])})
    command_deferred = self._send_commands([request])
    response = yield command_deferred

    # Check the response and return the move_antenna command response
    if response['status'] == "okay":
      self.driver._controller_state['state'] = "active"
      defer.returnValue({'message': "The antenna is being moved."})
    else:
      raise command.CommandError("An error occured while attempting to move '"+self.name+"': "+response['message'])

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
        "integer": True,
        "required": True,
        "title": "azimuth",
        "description": "The desired azimuth."
      },
      {
        "type": "number",
        "minvalue": 0,
        "maxvalue": 210,
        "integer": True,
        "required": True,
        "title": "elevation",
        "description": "The desired elevation."
      }
    ]

    return build_metadata_dict(command_parameters, 'move', self.name, requires_active_session = True,
                               schedulable = True)

  @inlineCallbacks
  def command_park(self, active_command):
    """ Parks the antenna.

    This command parks the antenna at an azimuth of 270 degrees, and an elevation of 0 degrees.

    @param active_command  The currently executing Command.
    @return Returns a deferred that will be fired with a dictionary containing the results of the park command. If the 
            command fails, the returned deferred will error.
    """

    # Build and send the command request
    request = self._build_request("park")
    command_deferred = self._send_commands([request])
    response = yield command_deferred

    # Check the response and return the park command response
    if response['status'] == "okay":
      self.driver._controller_state['state'] = "parking"
      defer.returnValue({'message': "The antenna is being parked."})
    else:
      raise command.CommandError("An error occured while parking '"+self.name+"': "+response['message'])

  def settings_park(self):
    """ Provides meta-data for the "park" command.

    @return Returns a dictionary containing meta-data about the command. 
    """

    return build_metadata_dict([], 'park', self.name, requires_active_session = True)

  @inlineCallbacks
  def command_calibrate(self, active_command):
    """ Completely calibrates the antenna.

    This command calibrates the antenna's azimuth and elevation by rotating it until it hits the vertical and horizontal 
    hardstops, at which point it will tare the azimuth and elevation.

    @note This command can only be interrupted by a "stop" command. Any "move" commands received when the antenna is 
          being calibrated will be ignored.

    @param active_command  The currently executing command.
    @return Returns a deferred that will be fired with a dictionary containing the results of the calibration. If the 
            command fails, the returned deferred will error.
    """

    # Build and send the command request
    request = self._build_request("cal")
    command_deferred = self._send_commands([request])
    response = yield command_deferred

    # Check the response and return the calibration results
    if response['status'] == "okay":
      self.driver._controller_state['state'] = "calibrating"
      defer.returnValue({'message': "The antenna is being calibrated."})
    else:
      raise command.CommandError("An error occured while calibrating '"+self.name+"': "+response['message'])

  def settings_calibrate(self):
    """ Provides meta-data for the "calibrate" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'calibrate', self.name, requires_active_session = True)

  @inlineCallbacks
  def command_calibrate_vert(self, active_command):
    """ Performs a vertical calibration.

    This command performs a vertical (El) calibration only. This command exists because the elevation tends to drift off
    quicker than the azimuth.

    @note This command can only be interrupted by a "stop" command. Any "move" commands received when the antenna is 
          being vertically calibrated will be ignored.

    @param active_command  The currently executing command.
    @return Returns a deferred that will be fired with a dictionary containing the results of the commands. If one of 
            the commands fail, the returned deferred will error.
    """

    # Build and send the command request
    request = self._build_request("vert_cal")
    command_deferred = self._send_commands([request])
    response = yield command_deferred

    # Check the response and return the results
    if response['status'] == "okay":
      self.driver._controller_state['state'] = "calibrating"
      defer.returnValue({'message': "The antenna is being vertically calibrated."})
    else:
      raise command.CommandError("An error occured while vertically calibrating '"+self.name+"': "+response['message'])

  def settings_calibrate_vert(self):
    """ Provides meta-data for the "calibrate_vert" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'calibrate_vert', self.name, requires_active_session = True)

  @inlineCallbacks
  def command_calibrate_and_park(self, active_command):
    """ Performs a full calibration and parks the antenna.

    This command calibrates the azimuth and elevation of the antenna and parks it at its rest position. 

    @note The "calibrate" command can only be interrupted by a "stop" command. Any "move" commands received when the 
          antenna is being calibrated will be ignored.

    @param active_command  The currently executing command.
    @return Returns a deferred that will be fired with a dictionary containing the results of the commands. If the 
            commands fail, the returned deferred will error.
    """

    # Build and send the command requests
    request_calibrate = self._build_request("cal")
    request_park = self._build_request("park")
    command_deferred = self._send_commands([request_calibrate, request_park])
    responses = yield command_deferred

    # Check the responses
    if responses['status'] == "okay":
      self.driver._controller_state['state'] = "calibrating"
      defer.returnValue({'message': "The antenna is being fully calibrated and will be parked at an Az/El of 270/0."})
    else:
      raise command.CommandError("An error occured while attempting to calibrate and park '"+self.name+"': "+
                                 responses['message'])

  def settings_calibrate_and_park(self):
    """ Provides meta-data for the "calibrate_and_park" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'calibrate_and_park', self.name, requires_active_session = True)

  @inlineCallbacks
  def command_get_state(self, active_command):
    """ Queries the antenna controller for its current state.

    This command loads and returns the controller's current state (i.e. its azimuth and elevation).
    
    @note If the antenna controller is out of calibration, this command may not return accurate results.

    @param active_command  The currently executing command.
    @return Returns a deferred that will be fired with a dictionary containing the results of the state command. If the 
            command fails, the returned deferred will error.
    """

    # Build and send the command request
    request = self._build_request("C2")
    command_deferred = self._send_commands([request])
    response = yield command_deferred

    # Check the response and return the results
    if response['status'] == "okay":
      defer.returnValue({'azimuth': response['responses'][0]['azimuth'], 
                         'elevation': response['responses'][0]['elevation']})
    else:
      raise command.CommandError("An error occured fetching the antenna controller state from '"+self.name+"': "+response['message'])

  def settings_get_state(self):
    """ Provides meta-data for the "get_state" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'get_state', self.name, requires_active_session = True)

  @inlineCallbacks
  def command_stop(self, active_command):
    """ Stops the antenna.

    This command instructs the antenna controller to stop executing whatever action it may currently be executing. It
    will not be calibrated or parked after being stopped.

    @param active_command  The currently executing command.
    @return Returns a deferred that will be fired with a dictionary containing the results of the stop command. If the 
            command fails, the returned deferred will error.
    """

    # Build and send the command request
    request = self._build_request("s")
    command_deferred = self._send_commands([request])
    response = yield command_deferred

    # Check the response
    if response['status'] == "okay":
      self.driver._controller_state['state'] = "stopped"
      defer.returnValue({'message': "The antenna controller has been stopped."})
    else:
      raise command.CommandError("An error occured while stopping '"+self.name+"': "+response['message'])

  def settings_stop(self):
    """ Provides meta-data for the "stop" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'stop', self.name, requires_active_session = True)

  @inlineCallbacks
  def command_stop_emergency(self, active_command):
    """ Stops the antenna in the event of an emergency.

    This command simulates a press of the emergency stop button on the antenna controller. An emergency stop differs 
    from a normal stop in that, after stopped, the device will not respond to any commands until the 'S' command is sent 
    again to bring the antenna controller out of emergency stop mode.
    
    @param active_command  The currently executing command.
    @param Returns a deferred that will be fired with a dictionary containing the results of the emergency stop. If the 
           command fails, the returned deferred will error.
    """

    # Build and send the command request
    request = self._build_request("S")
    command_deferred = self._send_commands([request])
    response = yield command_deferred

    # Check the response
    if response['status'] == "okay":
      self.driver._controller_state['state'] = "emergency_stopped"
      defer.returnValue({'message': "The antenna has been stopped and placed in emergency mode. It will not respond to "+
                                    "new commands until it receives another emergency stop command."})
    else:
      raise command.CommandError("An error occured while performing an emergency stop on '"+self.name+"': "+response['message'])

  def settings_stop_emergency(self):
    """ Provides meta-data for the "stop_emergency" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'stop_emergency', self.name, requires_active_session = True, dangerous = True)

  def _build_request(self, command, parameters = None):
    """ Constructs a request dictionary for the antenna controller API.
    
    @param command     The command to be executed. This should be a low level antenna controller command, not a Mercury2
                       command.
    @param parameters  A dictionary containing parameters that should be passed along with the command.
    @return Returns a dictionary that represents a request to the antenna controller web API.
    """

    # Construct the request
    new_request = {
      'command': command
    }

    if parameters is not None:
      new_request['arguments'] = parameters

    return new_request

  def _send_commands(self, requests):
    """ Sends commands to the antenna controller API.

    @param requests  An array containing requests to be sent to the antenna controller command API. Requests will be 
                     sequentially sent in the order provided.
    @return Returns a deferred that will eventually be fired with the command results (or an error message in the event
            of a failure).
    """

    # Encode the request
    request_json = json.dumps(requests)
    request_encoded = urllib.urlencode({"request": request_json})

    # Query the controller
    command_deferred = self._query_antenna_controller(request_encoded)
    command_deferred.addErrback(self._handle_query_error)

    return command_deferred

  @inlineCallbacks
  def _query_antenna_controller(self, encoded_request):
    """ Asynchronously sends commands to the antenna controller.

    This method is used by _send_commands() to send commands to the antenna controller API in a non-blocking fashion.

    @param encoded_request  The encoded request JSON ready for transmission.
    @return Returns a deferred that will be fired with the request response.
    """

    # Query the antenna controller API
    ac_request = urllib2.Request(self.driver.controller_api_endpoint, encoded_request)
    ac_opener = urllib2.build_opener()
    ac_deferred = threads.deferToThread(ac_opener.open, ac_request, None, self.driver.controller_api_timeout)
    ac_response = yield ac_deferred

    # Parse and return response
    parsed_response = json.load(ac_response)
    defer.returnValue(parsed_response)

  def _handle_query_error(self, failure):
    """ Handles errors that may occur while querying the antenna controller by returning a dictionary containing an
    error response

    @param failure  The Failure object encapsulating the error.
    """

    request_response = {}
    request_response['status'] = "error"
    request_response['message'] = str(failure.value)

    return request_response

class AntennaControllerError(Exception):
  pass
class InvalidTargetPosition(AntennaControllerError):
  pass
