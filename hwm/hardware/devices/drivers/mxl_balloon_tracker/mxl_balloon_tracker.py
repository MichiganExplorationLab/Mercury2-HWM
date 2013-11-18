""" @package hwm.hardware.devices.drivers.mxl_balloon_tracker.mxl_balloon_tracker
This module contains a virtual driver that provides tracking information for MXL balloon missions using a combination of
the APRS.fi network and position information downlinked directly from the balloon.
"""

# Import required modules
import time, urllib2, json, logging
from math import *
from twisted.internet import task, defer, reactor, threads
from hwm.core.configuration import Configuration
from hwm.hardware.devices.drivers import driver, service
from hwm.command.handlers import handler
from hwm.command.metadata import *
from hwm.command import command

class MXL_Balloon_Tracker(driver.VirtualDriver):
  """ A general purpose tracker for MXL Balloon missions.

  This virtual driver provides a tracking service that can be used by an antenna controller to target a Strato balloon.
  It works by querying the APRS.fi network for the balloon's last known position, which the antenna controller driver 
  can use to track the balloon. It will also periodically check for GPS coordinates downlinked directly from the
  balloon, which will take precedence over the APRS.fi data.
  
  @note Because this driver is a virtual driver, it will be initialized independently for each pipeline that uses it.
        As a result, we don't need to worry about providing tracking information for multiple targets because at most
        one pipeline will ever be using the driver at a time.
  """

  def __init__(self, device_configuration):
    """ Sets up the balloon tracker and initializes its command handler.

    @param device_configuration  A dictionary containing the tracker's configuration options.
    """

    # Call the VirtualDriver constructor
    super(MXL_Balloon_Tracker,self).__init__(device_configuration)

    # Initialize the driver's command handler
    self._command_handler = BalloonHandler(self)

    # Create the Direct Downlink APRS tracking service
    self._aprs_service = Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker')

    # Setup tracker attributes
    self.last_known_location = None

  def prepare_for_session(self, session_pipeline):
    """ Prepares the balloon tracker for use by starting the tracking service.

    @param session_pipeline  The Pipeline associated with the new session.
    """

    self._aprs_service._active_session_pipeline = session_pipeline # Used to load live_craft_position service
    self._aprs_service.start_tracker()

  def cleanup_after_session(self):
    """ Stops the balloon tracker service.
    """

    self._aprs_service.reset_tracker()

  def get_state(self):
    """ Returns a dictionary containing the current state of the tracker.
    """

    # TODO: Assemble a dictionary containing the tracker state

    return {}

  def _register_services(self, pipeline):
    """ Registers the tracker's services with the specified pipeline.

    This callback is called when a pipeline is registered with the driver during the pipeline initialization process. It
    will register the driver's tracking service with the Pipeline so that other devices in the pipeline (such as the 
    antenna controller) can locate and use it.

    @param pipeline  The Pipeline that was just registered with this driver.
    """

    pipeline.register_service(self._aprs_service)

class Direct_Downlink_APRS_Service(service.Service):
  """ This Service class provides the Direct Downlink and APRS tracking service.

  The Direct Downlink and APRS tracking service provides position and tracking information for MXL balloon flights, 
  which can be used by other devices (such as the antenna controller) to track the balloon. It works by first querying 
  the APRS.fi API for the balloon's most recent position data, which the antenna controller will use to point the 
  antenna at the balloon. Once the radio driver starts receiving data from the balloon, it will provide the downlinked 
  position data via the *live_craft_position* service. The position data provided by the live_craft_position service 
  will be preferred over APRS.fi data. If the live_craft_position service stops providing new data for whatever reason
  (i.e. if the downlinked data expires), the service will revert to using APRS.fi until the connection is 
  re-established.
  """

  def __init__(self, service_id, service_type):
    """ Sets up the tracking service.

    @param service_id     The unique service ID.
    @param service_type   The service type. Other drivers, such as the antenna controller driver, will search for this 
                          when looking for this service.
    """

    # Call the Service constructor
    super(Direct_Downlink_APRS_Service,self).__init__(service_id, service_type)

    # Configuration settings
    self.update_interval = 2 # Seconds
    self.aprs_fallback_timeout = 10 # Seconds
    self.aprs_update_timeout = 4 # Seconds
    self.api_key = None

    # Load the ground station's location
    self._global_config = Configuration
    self._station_longitude = self._global_config.get('station-longitude')
    self._station_latitude = self._global_config.get('station-latitude')
    self._station_altitude = self._global_config.get('station-altitude')

    # Set the service attributes
    self._reset_tracker_state()

  def start_tracker(self):
    """ Starts the tracker by initiating periodic APRS.fi and live_craft_position service updates using a LoopingCall.

    @note This method will attempt to load the 'live_craft_position' service from the device's pipeline.

    @return Returns the new LoopingCall deferred if started successfully and None if there is already a tracking service
            running.
    """

    # Load the live_craft_position service
    live_craft_position = None

    # Start the tracker if there isn't already one running
    if self._tracking_update_loop is None or not self._tracking_update_loop.running:
      self._live_craft_position_service = live_craft_position
      self._tracking_update_loop = task.LoopingCall(self._track_target)
      tracking_loop_deferred = self._tracking_update_loop.start(self.update_interval)
      tracking_loop_deferred.addErrback(self._handle_tracker_error)
      return tracking_loop_deferred
    else:
      return None

  def reset_tracker(self):
    """ Stops and resets the balloon tracker in between sessions.
    """

    # Stop the tracker event loop if it's running and reset the service
    if self._tracking_update_loop is not None and self._tracking_update_loop.running:
      self._tracking_update_loop.stop()
    self._reset_tracker_state()

  def get_target_position(self):
    """ Returns the target's current position.
    
    This method returns the target's most recent position and tracking information in a dictionary with the following
    attributes:
    * timestamp
    * longitude 
    * latitude 
    * altitude 
    * azimuth
    * elevation

    @throw May throw PositionNotAvailable errors if the balloon's position isn't available yet. If any position
           information is available it will be returned regardless of how old it is.

    @return Returns a dictionary containing the elements specified above.
    """

    # Make sure some position data has been collected
    if self._balloon_position['timestamp'] is None:
      raise PositionNotAvailable("No position data is currently available for the target balloon.")

    return self._balloon_position

  def _track_target(self):
    """ This method is responsible for coordinating the balloon tracker by checking for new position information and, if
    any is available, recalculating the balloon's targeting information.
    
    @note This method should be called periodically when the service is active using callLater or LoopingCall.
    @note APRS.fi will only be queried if the target's position hasn't been updated from other sources in some number of
          seconds (defined in the configuration).
    @return This method will return a deferred that will be fired with the current position of the balloon, after any 
            updates have been performed. If no updates have been performed, the returned deferred will be fired with 
            None.
    """

    tracking_update_deferred = None

    # Check the live_craft_position service for the balloon's position
    if self._live_craft_position_service is not None:
      balloon_coordinates = None
      try:
        balloon_coordinates = self._live_craft_position_service.get_position()
      except Exception as e:
        logging.error("An error occured in the '"+self._service_id+"' service when attempting to load the balloon "+
                      "position from the 'live_craft_position' service: "+str(e))

      if balloon_coordinates is not None:
        balloon_position = self._update_targeting_info(balloon_coordinates)
        tracking_update_deferred = defer.Deferred()
        tracking_update_deferred.callback(balloon_position)

    # Query APRS.fi if needed
    if self.callsign is not None:
      if self._balloon_position['timestamp'] is None or (int(time.time()) - self._balloon_position['timestamp']) >= self.aprs_fallback_timeout:
        tracking_update_deferred = threads.deferToThread(self._query_aprs_api)
        tracking_update_deferred.addErrback(self._handle_aprs_error)
        tracking_update_deferred.addCallback(self._update_targeting_info)

    if tracking_update_deferred is not None:
      return tracking_update_deferred
    else:
      return defer.succeed(None)

  def _query_aprs_api(self):
    """ Queries the APRS.fi API for the target's last known location.
    
    @note This method is blocking and should be called using threads.deferToThread().

    @return Returns a dictionary containing the target's last known location from APRS.fi.
    """
    
    # Query APRS.fi for the balloon's location
    try:
      aprs_request = urllib2.Request(self._aprs_api_endpoint)
      aprs_opener = urllib2.build_opener()
      aprs_response = aprs_opener.open(aprs_request, None, self.aprs_update_timeout)
    except Exception as e:
      # Error downloading the file
      raise APRSAPIError('There was an error querying the APRS.fi API.')
    
    # Parse the APRS response
    try:
      parsed_response = json.load(aprs_response)
    except ValueError as e:
      # Error parsing the response
      raise APRSAPIError('There was an error parsing the JSON response from the APRS.fi API.')

    # Check for an API error
    if parsed_response['result'] == "fail":
      raise APRSAPIError('An error occured querying the APRS.fi API: "'+parsed_response['description']+'"')

    # Format the response into the expected format
    final_response = {
      'timestamp': int(parsed_response['entries'][0]['time']),
      'longitude': float(parsed_response['entries'][0]['lng']),
      'latitude': float(parsed_response['entries'][0]['lat']),
      'altitude': float(parsed_response['entries'][0]['altitude'])
    }

    return final_response

  def _handle_tracker_error(self, failure):
    """ This callback handles errors that may occur in the tracking event loop.

    @param failure  A Failure object encapsulating the error.
    @return Returns False after logging the error.
    """

    # Log the error
    logging.error("An error occured while running the '"+self._service_id+"' service, the service has been stopped: '"+
                  failure.getErrorMessage()+"'")
    # TODO: Log the error to the event's state dictionary.

    # Stop the event loop just incase it's still running
    if self._tracking_update_loop.running:
      self._tracking_update_loop.stop()

    return False

  def _handle_aprs_error(self, failure):
    """ This callback handles errors that may result from an APRS.fi API query.

    @param failure  A Failure object encapsulating the error.
    @return Returns None after logging the error.
    """

    # Log the error
    logging.error("An error occured in the '"+self._service_id+"' service while querying the APRS.fi API: "+
                  failure.getErrorMessage())

    return None

  def _update_targeting_info(self, balloon_position):
    """ Updates the balloon's targeting information based on the provided position given that it is more recent than the
    currently recorded position.

    @param balloon_position  A dictionary containing the balloon's position information (longitude, latitude, altitude).
    @return Returns the ballon's new position information. If the provided position was invalid or older than the 
            current position data, None will be returned.
    """

    # Validate the received position
    if balloon_position is None:
      return None
    if not all (k in balloon_position for k in ('timestamp', 'longitude', 'latitude', 'altitude')):
      return None

    # Make sure the new measurement is more recent than the current one
    if self._balloon_position['timestamp'] is None or balloon_position['timestamp'] >= self._balloon_position['timestamp']:
      # Calculate the azimuth and elevation for the new position
      balloon_ecef = self._position_to_ECEF(balloon_position['latitude'], balloon_position['longitude'],
                                            balloon_position['altitude'])
      station_ecef = self._position_to_ECEF(self._station_latitude, self._station_longitude, self._station_altitude)
      balloon_enu = self._ECEF_to_ENU(station_ecef, balloon_ecef)
      balloon_azel = self._ENU_to_AzEl(balloon_enu)
      
      return self._set_balloon_position(balloon_position['timestamp'], balloon_position['longitude'],
                                        balloon_position['latitude'], balloon_position['altitude'],
                                        balloon_azel[0], balloon_azel[1])

    return None

  def _position_to_ECEF(self, latitude, longitude, altitude):
    """ Converts the supplied position to an Earth centered, Earth fixed coordinate system.

    @param latitude   The current latitude of the target.
    @param longitude  The current longitude of the target.
    @param altitude   The current altitude of the target.
    @return Returns an array containing the (x, y, z) coordinates of the target in ECEF. These coordinates are in
            meters.
    """

    # Convert the position to cartesian coordinates in the ECEF frame.
    angular_latitude = radians(latitude)
    angular_longitude = radians(longitude)
    a = 6378137.0 # Earth's semi-major axis (meters)
    f = 1/298.257223563 # Reciprocal flattening
    e2 = 2*f -f**2 # Eccentricity squared
    chi = sqrt(1-e2*(sin(angular_latitude))**2)
    ecef_x = (a/chi + altitude)*cos(angular_latitude)*cos(angular_longitude)
    ecef_y = (a/chi + altitude)*cos(angular_latitude)*sin(angular_longitude)
    ecef_z = (a*(1-e2)/chi + altitude)*sin(angular_latitude)

    return [ecef_x, ecef_y, ecef_z]

  def _ECEF_to_ENU(self, station_pos, target_pos):
    """ Calculates the position of the target in the "East, North, Up" coordinate system relative the position of the
    ground station.

    @note By convention the East-West axis is x, North-South is y, and Up-Down is z.

    @param station_pos  The ECEF position of the ground station that the target's ENU position will be calculated
                        relative to.
    @param target_pos   The ECEF position of the target.
    @return Returns an array containing the ENU position of the target relative to the provided station.
    """

    # Calculate the target's ENU position
    station_x = station_pos[0]
    station_y = station_pos[1]
    station_z = station_pos[2]
    target_x = target_pos[0]
    target_y = target_pos[1]
    target_z = target_pos[2]

    phi_p = atan2(station_z, sqrt(station_x**2 + station_y**2))
    lamb = atan2(station_y, station_x)
    enu_e = -sin(lamb)*(target_x-station_x) + cos(lamb)*(target_y-station_y)
    enu_n = (-sin(phi_p)*cos(lamb)*(target_x-station_x) - sin(phi_p)*sin(lamb)*(target_y-station_y) +
             cos(phi_p)*(target_z-station_z))
    enu_u = (cos(phi_p)*cos(lamb)*(target_x-station_x) + cos(phi_p)*sin(lamb)*(target_y-station_y) +
             sin(phi_p)*(target_z-station_z))

    return [enu_e, enu_n, enu_u]

  def _ENU_to_AzEl(self, target_pos):
    """ Calculates the target's azimuth and elevation given its ENU position.

    @param target_pos  The target's position in the ENU coordinate system.
    @return Returns the target's azimuth and elevation.
    """

    # Calculate the target's azimuth and elevation
    target_e = target_pos[0]
    target_n = target_pos[1]
    target_u = target_pos[2]

    target_az = atan2(target_e, target_n)
    target_az = degrees((target_az + 2*pi) if target_az < 0 else target_az)
    target_el = degrees(atan2(target_u, sqrt(target_e**2 + target_n**2)))

    # Check for and correct any excessive rotation
    while abs(target_az) > 360:
      if target_az > 0:
        target_az = target_az - 360
      elif target_az < 0:
        target_az = target_az + 360

    while abs(target_el) > 360:
      if target_el > 0:
        target_el = target_el - 360
      elif target_az < 0:
        target_el = target_el + 360

    return [target_az, target_el]

  def _set_balloon_position(self, timestamp, longitude, latitude, altitude, azimuth, elevation):
    """ Updates the recorded balloon position with the supplied location information.

    @param timestamp  When the balloon position data was collected/generated.
    @param longitude  The longitude of the balloon.
    @param latitude   The latitude of the balloon.
    @param altitude   The altitude of the balloon.
    @param azimuth    The azimuth of the balloon relative to the ground station location.
    @param elevation  The elevation of the balloon relative to the ground station location.
    @return Returns the new balloon position dictionary.
    """

    self._balloon_position = {
      'timestamp': timestamp,
      'longitude': longitude,
      'latitude': latitude,
      'altitude': altitude,
      'azimuth': round(azimuth, 3),
      'elevation': round(elevation, 3)
    }

    return self._balloon_position

  def _reset_tracker_state(self):
    """ Resets the state of the tracker initially and in between sessions.
    """

    # Reset service attributes
    self.callsign = None
    self._live_craft_position_service = None
    self._tracking_update_loop = None
    self._active_session_pipeline = None
    self._aprs_api_endpoint = None
    self._balloon_position = {
      'timestamp': None,
      'longitude': None,
      'latitude': None,
      'altitude': None,
      'azimuth': None,
      'elevation': None
    }

class BalloonHandler(handler.DeviceCommandHandler):
  """ A command handler that handles commands for the balloon tracker.
  """

  def command_start_tracking(self, active_command):
    """ Starts the tracking service.

    If the service is already started, it will be indicated in the response.
    
    @param active_command  The executing Command. Contains the command parameters.
    @return Returns a dictionary containing the command response.
    """

    # Try to start the service
    service_response = self.driver._aprs_service.start_tracker()
    if service_response is None:
      return {'message': "The balloon tracking service is already running."}
    else:
      return {'message': "The balloon tracking service has been started."}

  def settings_start_tracking(self):
    """ Meta-data for the "start_tracking" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'start_tracking', self.name, requires_active_session = True)

  def command_stop_tracking(self, active_command):
    """ Stops the tracking service.

    This command will stop the tracking service's event loop without resetting any of the service attributes. This will 
    allow it to easily be restarted by the user.
    
    @param active_command  The currently executing Command. Contains the command parameters.
    @return Returns a dictionary containing the command response.
    """

    # Stop the service if it is running
    if self.driver._aprs_service._tracking_update_loop is not None and self.driver._aprs_service._tracking_update_loop.running:
      self.driver._aprs_service._tracking_update_loop.stop()
      return {'message': "The balloon tracker has been stopped."}
    else:
      return {'message': "The balloon tracker is not currently running."}

  def settings_stop_tracking(self):
    """ Meta-data for the "stop_tracking" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    return build_metadata_dict([], 'stop_tracking', self.name, requires_active_session = True)

  def command_set_callsign(self, active_command):
    """ Sets the tracker's active APRS callsign.

    This command is used to set the tracker's active APRS callsign and should be run as a session setup command.
    
    @param active_command  The executing Command. Contains the command parameters.
    @return Returns a dictionary containing the command response.
    """

    # Validate the callsign
    if active_command.parameters is None or 'callsign' not in active_command.parameters:
      raise command.CommandError("The required 'callsign' parameter was not included in the submitted command.")

    # Update the APRS callsign
    self.driver._aprs_service.callsign = active_command.parameters['callsign']
    self.driver._aprs_service._aprs_api_endpoint = ("http://api.aprs.fi/api/get?name="+
                                                    self.driver._aprs_service.callsign+"&what=loc&apikey="+
                                                    self.driver.api_key+"&format=json")

    return {'message': "The balloon's APRS callsign has been updated."}

  def settings_set_callsign(self):
    """ Meta-data for the "set_callsign" command.
    
    @return Returns a dictionary containing meta-data about the "set_callsign" command.
    """

    # The command parameters
    command_parameters = [
      {
        "type": "string",
        "minlength": 1,
        "maxlength": 1,
        "required": True,
        "title": "callsign",
        "description": "The APRS callsign to be tracked."
      }
    ]

    return build_metadata_dict(command_parameters, 'set_callsign', self.name, requires_active_session = True,
                               use_as_initial_value = True)

class BalloonTrackerError(Exception):
  pass
class PositionNotAvailable(BalloonTrackerError):
  pass
class APRSAPIError(BalloonTrackerError):
  pass
