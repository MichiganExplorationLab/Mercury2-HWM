# Import required modules
import logging, time, urllib2
from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks
from mock import MagicMock
from pkg_resources import Requirement, resource_filename
from StringIO import StringIO
from hwm.core.configuration import *
from hwm.command import command
from hwm.hardware.devices.drivers.mxl_balloon_tracker import mxl_balloon_tracker

class TestMXLBalloonTrackerDriver(unittest.TestCase):
  """ This test suite verifies the functionality of the MXL Balloon Tracker virtual driver.
  """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    self.config.read_configuration(self.source_data_directory+'/core/tests/data/test_config_basic.yml')
    self.standard_device_config = {'id': "test_device", 'settings': {'update_interval': 2, 'aprs_fallback_timeout': 10, 'aprs_update_timeout': 4, 'api_key': None}} 

    # Backup a urllib2 method that gets monkey-patched so that it can be restored between tests
    self.old_build_opener = urllib2.build_opener
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Restore urllib2 functions
    urllib2.build_opener = self.old_build_opener

    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  def test_prepare_for_session(self):
    """ Tests that the prepare_for_session callback performs the correct actions. It also verifies that the device 
    correctly performs service registrations and command handler initialization.
    """

    # Initialize the device
    test_pipeline = MagicMock()
    test_device = mxl_balloon_tracker.MXL_Balloon_Tracker(self.standard_device_config, MagicMock())
    test_device._aprs_service = MagicMock()
    test_device._aprs_service.id = "aprs_test_service"
    test_device._aprs_service.type = "tracker"

    # Verify the device can register services and initialize its command handler
    test_device.register_pipeline(test_pipeline)
    test_pipeline.register_service.assert_called_once_with(test_device._aprs_service)
    self.assertTrue(isinstance(test_device._command_handler, mxl_balloon_tracker.BalloonHandler))

    # Run the prepare_for_session callback and check results
    test_device.prepare_for_session(test_pipeline)
    self.assertEqual(test_device._aprs_service._active_session_pipeline, test_pipeline)
    test_device._aprs_service.start_tracker.assert_called_once_with()

  def test_cleanup_after_session(self):
    """ Tests that the cleanup_after_session callback performs the correct actions. """

    # Initialize the device
    test_pipeline = MagicMock()
    test_device = mxl_balloon_tracker.MXL_Balloon_Tracker(self.standard_device_config, MagicMock())
    test_device._aprs_service = MagicMock()

    # Run the prepare_for_session callback and check results
    test_device.cleanup_after_session()
    test_device._aprs_service.reset_tracker.assert_called_once_with()

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

class TestBalloonHandler(unittest.TestCase):
  """ This test suite verifies the functionality of the MXL Balloon Tracker command handler.
  """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    self.config.read_configuration(self.source_data_directory+'/core/tests/data/test_config_basic.yml')

    # Backup a urllib2 method that gets monkey-patched so that it can be restored between tests
    self.old_build_opener = urllib2.build_opener
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Restore urllib2 functions
    urllib2.build_opener = self.old_build_opener

    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  def test_start_tracking_command(self):
    """ Tests the 'start_tracking' command and possible errors.
    """

    # Initialize a test command handler with a mock driver
    test_command = MagicMock()
    test_driver = MagicMock()
    test_driver._aprs_service.start_tracker = lambda : None
    test_handler = mxl_balloon_tracker.BalloonHandler(test_driver)

    # Run the command with a simulated tracker event loop already running
    self.assertRaises(command.CommandError, test_handler.command_start_tracking, test_command)

    # Run the command without a simulated tracker running
    test_driver._aprs_service.start_tracker = lambda : True
    results = test_handler.command_start_tracking(test_command)
    self.assertTrue("has been started." in results['message'])

  def test_stop_tracking_command(self):
    """ Tests the 'stop_tracking' command and possible errors.
    """

    # Initialize a test command handler with a mock driver
    test_command = MagicMock()
    test_driver = MagicMock()
    test_driver._aprs_service._tracking_update_loop = MagicMock()
    test_driver._aprs_service._tracking_update_loop.running = True
    test_handler = mxl_balloon_tracker.BalloonHandler(test_driver)

    # Run the command with a simulated tracker event loop already running
    results = test_handler.command_stop_tracking(test_command)
    test_driver._aprs_service._tracking_update_loop.stop.assert_called_once_with()
    self.assertTrue("has been stopped." in results['message'])

    # Run the command without a simulated tracker not running
    test_driver._aprs_service._tracking_update_loop = None
    self.assertRaises(command.CommandError, test_handler.command_stop_tracking, test_command)

  def test_set_callsign_command(self):
    """ Tests the 'set_callsign' command and possible errors.
    """

    # Initialize a test command handler with a command that doesn't specify any parameters
    test_command = MagicMock()
    test_command.parameters = {}
    test_driver = MagicMock()
    test_handler = mxl_balloon_tracker.BalloonHandler(test_driver)

    # Make sure the command fails if no callsign provided
    self.assertRaises(command.CommandError, test_handler.command_set_callsign, test_command)

    # Add a callsign and make sure it updated the service correctly
    test_command.parameters = {'callsign': "test_callsign"}
    results = test_handler.command_set_callsign(test_command)
    self.assertEqual(test_driver._aprs_service.callsign, "test_callsign")
    self.assertTrue("callsign has been updated." in results['message'])

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

class TestAPRSTrackingService(unittest.TestCase):
  """ This test suite is designed to test the functionality of the APRS balloon tracking service.
  """
  
  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    self.config.read_configuration(self.source_data_directory+'/core/tests/data/test_config_basic.yml')
    self.standard_device_config = {'id': "test_device", 'update_interval': 2, 'aprs_fallback_timeout': 10, 'aprs_update_timeout': 4, 'api_key': None} 

    # Backup a urllib2 method that gets monkey-patched so that it can be restored between tests
    self.old_build_opener = urllib2.build_opener
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Restore urllib2 functions
    urllib2.build_opener = self.old_build_opener

    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  def test_service_initialization(self):
    """ Tests that the tracking service correctly initializes its state when constructed.
    """

    # Create a test service instance
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)

    # Verify the service's attributes
    self.assertEqual(test_service._station_longitude, -83.71264)
    self.assertEqual(test_service._station_latitude, 42.29364)
    self.assertEqual(test_service._station_altitude, 276)
    self.assertEqual(test_service.callsign, None)
    self.assertEqual(test_service.update_interval, 2)
    self.assertEqual(test_service.aprs_fallback_timeout, 10)
    self.assertEqual(test_service.aprs_update_timeout, 4)
    self.assertEqual(test_service.api_key, None)
    self.assertEqual(test_service._balloon_position['timestamp'], None)

  def test_set_balloon_position(self):
    """ Tests that the _set_balloon_position() method correctly updates the balloon's position.
    """

    # Create a test service instance
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)

    # Manually set some position data and try again
    test_service._set_balloon_position(1384115919, -84.48387, 42.73698, 12000, 20, 30) 
    balloon_position = test_service._balloon_position
    self.assertEqual(balloon_position['timestamp'], 1384115919)
    self.assertEqual(balloon_position['longitude'], -84.48387)
    self.assertEqual(balloon_position['latitude'], 42.73698)
    self.assertEqual(balloon_position['altitude'], 12000)
    self.assertEqual(balloon_position['azimuth'], 20)
    self.assertEqual(balloon_position['elevation'], 30)

  def test_aprs_query(self):
    """ Tests that the APRS query method can successfully query the APRS API for the balloon's position and parse the 
    response.

    @note This test uses a mocked network handler instead of actually querying the APRS.fi API. As a result, if the API
          changes this test will still pass even though it will fail in production. This was done to limit test 
          dependencies.
    """

    # Create a test service instance and mock some urllib2 methods
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)
    test_service._aprs_api_endpoint = "http://aprstest.local"
    self.set_mock_request_builder(mock_aprs_success)

    # Query the APRS API with a successful request and make sure it correctly parses the response
    test_location = test_service._query_aprs_api()
    self.assertEqual(test_location['timestamp'], 1384119682)
    self.assertEqual(test_location['longitude'], -83.944942)
    self.assertEqual(test_location['latitude'], 42.003933)
    self.assertEqual(test_location['altitude'], 12000)

  def test_aprs_query_errors(self):
    """ Verifies that the APRS query method can correctly handle several probable errors.
    """

    # Create a test service instance and mock some urllib2 methods
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)
    test_service._aprs_api_endpoint = "aprstest.local"

    # Test that the service correctly responds to urllib2 errors
    self.assertRaises(mxl_balloon_tracker.APRSAPIError, test_service._query_aprs_api)

    # Test with a malformed APRS response
    test_service._aprs_api_endpoint = "http://aprstest.local"
    self.set_mock_request_builder(mock_aprs_malformed)
    self.assertRaises(mxl_balloon_tracker.APRSAPIError, test_service._query_aprs_api)

    # Test with a failed APRS response
    test_service._aprs_api_endpoint = "http://aprstest.local"
    self.set_mock_request_builder(mock_aprs_failed)
    self.assertRaises(mxl_balloon_tracker.APRSAPIError, test_service._query_aprs_api)

  def test_calculate_targeting_info_failed(self):
    """ Tests that the APRS tracking service correctly handles errors that may occur when calculating balloon targeting 
    information.
    """

    # Create a test service instance
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)

    # Submit some invalid positions
    self.assertEqual(test_service._update_targeting_info(None), None)
    
    test_position = {"timestamp": 234235234, "altitude": 12000} # Missing fields
    self.assertEqual(test_service._update_targeting_info(test_position), None)
    
    test_position = {
      "timestamp": 234235234,
      "longitude": -83.944942,
      "latitude": 42.003933,
      "altitude": 12000
    }
    test_service._balloon_position['timestamp'] = 234235235 # Newer than test timestmap
    self.assertEqual(test_service._update_targeting_info(test_position), None)

  def test_calculate_targeting_info(self):
    """ Tests that, given a balloon position, the APRS service can correctly determine the Az and El to the target.
    """

    # Create a test service instance
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)

    # Submit some position information and see if the service calculates the targeting info correctly
    position = {
      "timestamp": 234235234,
      "longitude": -83.944942,
      "latitude": 42.003933,
      "altitude": 12000
    }
    new_position_info = test_service._update_targeting_info(position)
    self.assertEqual(new_position_info['timestamp'], 234235234)
    self.assertEqual(new_position_info['longitude'], -83.944942)
    self.assertEqual(new_position_info['latitude'], 42.003933)
    self.assertEqual(new_position_info['altitude'], 12000)
    self.assertEqual(new_position_info['azimuth'], 210.933)
    self.assertEqual(new_position_info['elevation'], 17.353)

  @inlineCallbacks
  def test_track_target_aprs_errors(self):
    """ Tests that the APRS tracking service correctly handles APRS.fi errors that may occur in the service event loop.
    """

    # Create a test service instance
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)

    # Run the tracking update loop body without a service or APRS callsign
    test_deferred = test_service._track_target()
    result = yield test_deferred

    # Verify results and set the APRS callsign + mock the API to return a failed response
    self.assertEqual(result, None)
    test_service._aprs_api_endpoint = "http://aprstest.local"
    self.set_mock_request_builder(mock_aprs_failed)
    test_service.callsign = "test_callsign"
    test_deferred = test_service._track_target()
    result = yield test_deferred

    # Verify results
    self.assertEqual(result, None)

  @inlineCallbacks
  def test_track_target_aprs_success(self):
    """ Tests that the tracking service can correctly handle successful APRS.fi queries.
    """

    # Create a test service instance
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)
    self.receiver_results = None

    # Create and register a position receiver with the service
    def mock_position_receiver(position_data):
      self.receiver_results = position_data
    test_service.register_position_receiver(mock_position_receiver)

    # Set the APRS callsign, add an existing expired balloon position, and mock the API to return a failed response
    test_service._balloon_position['timestamp'] = 1384119680
    test_service._aprs_api_endpoint = "http://aprstest.local"
    self.set_mock_request_builder(mock_aprs_success)
    test_service.callsign = "test_callsign"
    test_deferred = test_service._track_target()
    result = yield test_deferred

    # Verify results
    self.assertEqual(result['timestamp'], 1384119682)
    self.assertEqual(result['longitude'], -83.944942)
    self.assertEqual(result['latitude'], 42.003933)
    self.assertEqual(result['altitude'], 12000)
    self.assertEqual(result['azimuth'], 210.933)
    self.assertEqual(result['elevation'], 17.353)
    self.assertEqual(self.receiver_results['timestamp'], 1384119682)
    self.assertEqual(self.receiver_results['longitude'], -83.944942)
    self.assertEqual(self.receiver_results['latitude'], 42.003933)
    self.assertEqual(self.receiver_results['altitude'], 12000)
    self.assertEqual(self.receiver_results['azimuth'], 210.933)
    self.assertEqual(self.receiver_results['elevation'], 17.353)

  @inlineCallbacks
  def test_track_target_service_success(self):
    """ Tests that the APRS tracking service prefers position information from a pipeline service over APRS when
    possible.
    """

    # Create a test service instance
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)

    # Mock the position service and track the target
    test_time = int(time.time())-1
    position = {
      "timestamp": test_time,
      "longitude": -83.944942,
      "latitude": 42.003933,
      "altitude": 12000
    }
    test_service._live_craft_position_service = MagicMock()
    test_service._live_craft_position_service.get_position = lambda : position
    test_service.callsign = "test_callsign"
    test_deferred = test_service._track_target()
    result = yield test_deferred

    # Verify results
    self.assertEqual(result['timestamp'], test_time)
    self.assertEqual(result['longitude'], -83.944942)
    self.assertEqual(result['latitude'], 42.003933)
    self.assertEqual(result['altitude'], 12000)
    self.assertEqual(result['azimuth'], 210.933)
    self.assertEqual(result['elevation'], 17.353)

  @inlineCallbacks
  def test_track_target_service_errors(self):
    """ Tests that the APRS tracking service can handle errors that may occur when querying the craft position service.
    """

    def mock_get_position_error():
      raise TypeError

    # Create a test service instance
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)

    # Mock the position service with a function that will generate an error and check that it reverted to APRS
    test_service._live_craft_position_service = MagicMock()
    test_service._live_craft_position_service.get_position = mock_get_position_error
    test_service._aprs_api_endpoint = "http://aprstest.local"
    test_service.callsign = "test_callsign"
    self.set_mock_request_builder(mock_aprs_success)
    test_deferred = test_service._track_target()
    result = yield test_deferred

    # Verify results and test with a mocked get_position that returns an old position which causes a fallback to APRS
    self.assertEqual(result['timestamp'], 1384119682)
    self.assertEqual(result['longitude'], -83.944942)
    self.assertEqual(result['latitude'], 42.003933)
    self.assertEqual(result['altitude'], 12000)
    self.assertEqual(result['azimuth'], 210.933)
    self.assertEqual(result['elevation'], 17.353)
    position = {
      "timestamp": 1384119682-1,
      "longitude": -83.944942,
      "latitude": 42.003933,
      "altitude": 12001
    }
    test_service._balloon_position['timestamp'] = 1384119682-2 # Make it so that the position above gets saved but is
                                                               # still too old
    test_service._live_craft_position_service.get_position = lambda : position
    self.set_mock_request_builder(mock_aprs_success)
    test_deferred = test_service._track_target()
    result = yield test_deferred

    # Verify results (should match successful mock APRS response)
    self.assertEqual(result['timestamp'], 1384119682)
    self.assertEqual(result['longitude'], -83.944942)
    self.assertEqual(result['latitude'], 42.003933)
    self.assertEqual(result['altitude'], 12000)
    self.assertEqual(result['azimuth'], 210.933)
    self.assertEqual(result['elevation'], 17.353)

  @inlineCallbacks
  def test_start_tracker_errors(self):
    """ Tests that the start_tracker method can handle any errors that may occur when the tracker is running.
    """

    def mock_track_target():
      raise TypeError

    # Create a test service instance
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)

    # Try starting the tracker with a mock already running event loop
    test_service._tracking_update_loop = MagicMock()
    test_service._tracking_update_loop.running = True
    self.assertEqual(test_service.start_tracker(), None)

    # Mock the _track_target method to raise an except and make sure it gets handled
    test_service._tracking_update_loop = None
    test_service._track_target = mock_track_target
    test_deferred = test_service.start_tracker()
    result = yield test_deferred

    # Verify results
    self.assertTrue(not test_service._tracking_update_loop.running)
    self.assertEqual(result, False)

  def test_reset_tracker(self):
    """ Verifies that the reset_tracker method can stop and cleanup after a running tracker event loop.
    """

    # Create a test service instance
    test_service = mxl_balloon_tracker.Direct_Downlink_APRS_Service('direct_downlink_aprs_service', 'tracker', self.standard_device_config)

    def check_results(result, tracking_update_loop):
      # Will be called when the tracker LoopingCall loop is stopped with a reference to the LoopingCall instance
      self.assertEqual(result, tracking_update_loop)

    # Start the tracker with a mock _track_target method
    test_service._track_target = lambda : True
    test_deferred = test_service.start_tracker()
    test_deferred.addCallback(check_results, test_service._tracking_update_loop)

    # Reset the tracker and verify
    old_update_loop = test_service._tracking_update_loop
    test_service.reset_tracker()
    self.assertTrue(not old_update_loop.running)
    self.assertEqual(test_service._tracking_update_loop, None)

    return test_deferred

  def set_mock_request_builder(self, mock_request_handler):
    """ This method modifies the global urllib2 module to return a handler that we constructed that uses a custom 
    request handler.
    """

    urllib2.build_opener = self.old_build_opener
    test_build_opener = urllib2.build_opener(MockAPRSHandler)
    urllib2.build_opener = lambda : test_build_opener
    for temp_handler in test_build_opener.handlers:
      if isinstance(temp_handler, MockAPRSHandler):
        temp_handler.mock_request_builder = mock_request_handler
        break

    return test_build_opener

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

class MockAPRSHandler(urllib2.HTTPHandler):
  """ A mock HTTP handler for simulating APRS.fi API queries. """

  def http_open(self, req):
    return self.mock_request_builder(req)

def mock_aprs_success(request):
  """ A mock urllib2 request handler that returns a simulated successful APRS.fi API response.
  """

  response = urllib2.addinfourl(StringIO("{\"command\":\"get\",\"result\":\"ok\",\"what\":\"loc\",\"found\":1,\"entries\": [{\"time\":\"1384119682\",\"lat\":\"42.003933\",\"lng\":\"-83.944942\",\"altitude\":\"12000\"}]}"), "mock headers", request.get_full_url())
  response.code = 200
  response.msg = "OK"
  
  return response

def mock_aprs_malformed(request):
  """ A mock urllib2 request handler that returns a malformed APRS.fi response.
  """

  response = urllib2.addinfourl(StringIO("{\"test_response\":false,\"invalid\":True}"), "mock headers", request.get_full_url())
  response.code = 200
  response.msg = "OK"
  
  return response

def mock_aprs_failed(request):
  """ A mock urllib2 request handler that returns a simulated failed APRS.fi API response.
  """

  response = urllib2.addinfourl(StringIO("{\"command\":\"get\",\"result\":\"fail\",\"description\":\"Test error description.\"}"), "mock headers", request.get_full_url())
  response.code = 200
  response.msg = "OK"
  
  return response
