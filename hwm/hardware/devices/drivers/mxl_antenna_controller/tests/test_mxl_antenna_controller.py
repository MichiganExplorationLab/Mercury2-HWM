# Import required modules
import logging, time, urllib2, urlparse, json
from twisted.trial import unittest
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks
from mock import MagicMock
from pkg_resources import Requirement, resource_filename
from StringIO import StringIO
from hwm.core.configuration import *
from hwm.command import command
from hwm.hardware.devices.drivers.mxl_antenna_controller import mxl_antenna_controller
from hwm.hardware.pipelines import pipeline

class TestMXLAntennaControllerDriver(unittest.TestCase):
  """ This test suite verifies the functionality of the custom MXL antenna controller driver.
  """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    self.config.read_configuration(self.source_data_directory+'/core/tests/data/test_config_basic.yml')
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  def test_prepare_for_session(self):
    """ Verifies that the antenna controller can set itself up correctly in preparation for a new session given that 
    the required service is available.
    """

    # Create a driver instance to test with
    test_pipeline = MagicMock()
    test_device = mxl_antenna_controller.MXL_Antenna_Controller({'id': 'test_device'}, MagicMock())
    test_device._update_state = MagicMock()

    # Create a mock 'tracker' service
    tracker_service = MagicMock()
    test_pipeline.load_service = lambda service_id : tracker_service

    # Run prepare_for_session and check results
    test_deferred = test_device.prepare_for_session(test_pipeline)
    tracker_service.register_position_receiver.assert_called_once_with(test_device.process_new_position)
    self.assertTrue(test_device._state_update_loop.running)

    # Stop the LoopingCall
    test_device._state_update_loop.stop()

    return test_deferred

  def test_prepare_for_session_no_tracker_service(self):
    """ Verifies that the antenna controller takes the correct actions if can't find a 'tracker' service during the 
    prepare_for_session() phase.
    """

    def mock_load_service(service_id):
      raise pipeline.ServiceTypeNotFound("Test error yo.")

    # Create driver and pipeline instances to test with
    test_pipeline = MagicMock()
    test_pipeline.load_service = mock_load_service
    test_device = mxl_antenna_controller.MXL_Antenna_Controller({'id': 'test_device'}, MagicMock())
    test_device._update_state = MagicMock()

    # Run prepare_for_session and check results
    test_results = test_device.prepare_for_session(test_pipeline)
    self.assertTrue(not test_results)

  @inlineCallbacks
  def test_prepare_for_session_update_loop_error(self):
    """ This test verifies that the antenna controller prepare_for_session deferred. """

    def mock_update_state(service_id):
      raise TypeError("Test error yo.")

    # Create a driver instance to test with
    test_pipeline = MagicMock()
    test_device = mxl_antenna_controller.MXL_Antenna_Controller({'id': 'test_device'}, MagicMock())
    test_device._update_state = mock_update_state

    # Create a mock 'tracker' service
    tracker_service = MagicMock()
    test_pipeline.load_service = lambda service_id : tracker_service

    # Run prepare_for_session
    test_deferred = test_device.prepare_for_session(test_pipeline)
    result = yield test_deferred

    # Verify the results
    self.assertTrue(not test_device._state_update_loop.running)
    self.assertEqual(result, False)

  @inlineCallbacks
  def test_cleanup_after_session(self):
    """ Tests that the antenna controller takes the correct actions once a session has ended. """

    def mock_parse_command(command_request, **keywords):
      self.assertEqual(command_request['command'], "calibrate_and_park")
      self.assertEqual(keywords['user_id'], None)
      self.assertEqual(keywords['kernel_mode'], True)

      return defer.succeed(True)

    # Create a driver instance to test with
    test_pipeline = MagicMock()
    test_pipeline.id = "test_pipeline"
    test_cp = MagicMock()
    test_cp.parse_command = mock_parse_command
    test_device = mxl_antenna_controller.MXL_Antenna_Controller({'id': 'test_device'}, test_cp)
    test_device._session_pipeline = test_pipeline

    # Create a mock 'tracker' service
    test_pipeline.load_service = MagicMock()

    # Run prepare_for_session and check results
    test_deferred = test_device.cleanup_after_session()
    result = yield test_deferred

    # Make sure the tracker state was reset
    self.assertEqual(test_device._current_position, None)
    self.assertEqual(test_device._tracker_service, None)
    self.assertEqual(test_device._session_pipeline, None)
    self.assertEqual(test_device._controller_state['timestamp'], None)
    self.assertEqual(test_device._controller_state['azimuth'], 0)
    self.assertEqual(test_device._controller_state['elevation'], 0)
    self.assertEqual(test_device._controller_state['state'], "inactive")

  def test_process_new_position(self):
    """ Verifies that the process_new_position() method correctly responds to new targeting information. """

    # Create a test pipeline
    test_pipeline = MagicMock()
    test_pipeline.id = "test_pipeline"
    test_pipeline.current_session.user_id = "test_user"

    def mock_parse_command(command_request, **keywords):
      self.assertEqual(command_request['command'], "move")
      self.assertEqual(command_request['destination'], test_pipeline.id+".test_device")
      self.assertEqual(command_request['parameters']['azimuth'], 42)
      self.assertEqual(command_request['parameters']['elevation'], 42)
      self.assertEqual(keywords['user_id'], test_pipeline.current_session.user_id)

      return defer.succeed(True)

    # Create a test device
    test_cp = MagicMock()
    test_cp.parse_command = mock_parse_command
    test_device = mxl_antenna_controller.MXL_Antenna_Controller({'id': 'test_device'}, test_cp)
    test_device._session_pipeline = test_pipeline

    # Create a mock target_position and submit it
    target_position = {
      "azimuth": 42.1,
      "elevation": 42.1
    }
    command_deferred = test_device.process_new_position(target_position)

    return command_deferred

  def test_process_new_position_error(self):
    """ Verifies that the process_new_position method can correctly handle problems with the provided target position.
    """

    # Create a driver instance to test with
    test_device = mxl_antenna_controller.MXL_Antenna_Controller({'id': 'test_device'}, MagicMock())

    # Create an invalid mock target_position and submit it
    target_position = {
      "azimuth": 42.1
    }
    self.assertRaises(mxl_antenna_controller.InvalidTargetPosition, test_device.process_new_position, target_position)

  @inlineCallbacks
  def test_update_state(self):
    """ Tests the _update_state() method of the antenna controller driver, which is responsible for periodically 
    querying the antenna controller for its current orientation. """

    # Create a mock pipeline to test with
    test_pipeline = MagicMock()
    test_pipeline.id = "test_pipeline"
    test_pipeline.current_session.user_id = "test_user"

    def mock_parse_command(command_request, **keywords):
      self.assertEqual(command_request['command'], "get_state")
      self.assertEqual(command_request['destination'], test_pipeline.id+".test_device")
      self.assertEqual(keywords['user_id'], test_pipeline.current_session.user_id)

      test_response = {
        'response': {
          'status': 'okay',
          'azimuth': 42,
          'elevation': 42
        }
      }

      return defer.succeed(test_response)

    # Create a test device
    test_cp = MagicMock()
    test_cp.parse_command = mock_parse_command
    test_device = mxl_antenna_controller.MXL_Antenna_Controller({'id': 'test_device'}, test_cp)
    test_device._session_pipeline = test_pipeline

    # Try updating the state
    self.assertEqual(test_device._controller_state['timestamp'], None)
    result = yield test_device._update_state()

    # Check results
    self.assertTrue(result['timestamp'] is not None)
    self.assertEqual(result['azimuth'], 42)
    self.assertEqual(result['elevation'], 42)

  @inlineCallbacks
  def test_update_state_command_error(self):
    """ Tests that the _update_state() method of the antenna controller driver responds correctly to an error from the
    antenna controller device. """

    # Create a mock pipeline to test with
    test_pipeline = MagicMock()
    test_pipeline.id = "test_pipeline"
    test_pipeline.current_session.user_id = "test_user"

    def mock_parse_command(command_request, **keywords):
      self.assertEqual(command_request['command'], "get_state")
      self.assertEqual(command_request['destination'], test_pipeline.id+".test_device")
      self.assertEqual(keywords['user_id'], test_pipeline.current_session.user_id)

      test_response = {
        'response': {
          'status': 'error'
        }
      }

      return defer.succeed(test_response)

    # Create a test device
    test_cp = MagicMock()
    test_cp.parse_command = mock_parse_command
    test_device = mxl_antenna_controller.MXL_Antenna_Controller({'id': 'test_device'}, test_cp)
    test_device._session_pipeline = test_pipeline

    # Try updating the state
    self.assertEqual(test_device._controller_state['timestamp'], None)
    result = yield test_device._update_state()

    # Check results
    self.assertEqual(result, None)

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

class TestMXLAntennaControllerHandler(unittest.TestCase):
  """ Tests the command handler for the MXL antenna controller. """

  def setUp(self):
    # Set a local reference to Configuration (how other modules should typically access Config)
    self.config = Configuration
    self.config.verbose_startup = False
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    self.config.read_configuration(self.source_data_directory+'/core/tests/data/test_config_basic.yml')

    # Backup a urllib2 method that gets monkey-patched so that it can be restored between tests
    self.old_build_opener = urllib2.build_opener

    # Setup a test driver and command handler
    self.test_driver = MagicMock()
    self.test_driver._controller_state = {}
    self.test_handler = mxl_antenna_controller.AntennaControllerHandler(self.test_driver)
    self.test_driver.antenna_controller_api_endpoint = "http://actest.local"
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Restore urllib2 functions
    urllib2.build_opener = self.old_build_opener

    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  def test_build_request(self):
    """ Tests the _build_request method, which is responsible for building individual requests for the antenna
    controller API. """

    # Build a request for a command with arguments and check results
    test_request = self.test_handler._build_request("TC", {'param1': "waffles"})
    self.assertEqual(test_request['command'], "TC")
    self.assertEqual(test_request['arguments']['param1'], "waffles")

    # Build a request for a command without arguments and check results
    test_request = self.test_handler._build_request("TC")
    self.assertEqual(test_request['command'], "TC")
    self.assertTrue("arguments" not in test_request)

  def test_send_commands(self):
    """ Tests that the _send_commands method, which is responsible for sending commands to the antenna controller API,
    correctly packages commands and returns the response. """

    def mock_request_handler(request):
      form_params = urlparse.parse_qs(request.get_data())
      request_json = json.loads(form_params['request'][0])
      
      # Make sure the request arrived in the correct format
      self.assertEqual(request_json[0]['command'], "TC")
      self.assertEqual(request_json[0]['arguments']['param1'], "waffles")
      self.assertEqual(request_json[1]['command'], "TC2")

      response = urllib2.addinfourl(StringIO("{\"status\":\"okay\",\"responses\":[{\"timestamp\":1384814185,\"command\":\"move\"}]}"), "mock headers", request.get_full_url())
      response.code = 200
      response.msg = "OK"
  
      return response

    # Build and submit some mock commands
    self._set_mock_request_builder(mock_request_handler)
    test_req_1 = self.test_handler._build_request("TC", {'param1': "waffles"})
    test_req_2 = self.test_handler._build_request("TC2")
    results = self.test_handler._send_commands([test_req_1, test_req_2])

    # Verify the results
    self.assertEqual(results['status'], "okay")
    self.assertEqual(results['responses'][0]['timestamp'], 1384814185)
    self.assertEqual(results['responses'][0]['command'], "move")

  def test_send_commands_errors(self):
    """ Tests that the _send_commands method can correctly handle connection errors if they arise. """

    def mock_request_handler(request):
      raise TypeError("Test error yo.")

    # Build and submit some mock commands
    self._set_mock_request_builder(mock_request_handler)
    test_req_1 = self.test_handler._build_request("TC", {'param1': "waffles"})
    results = self.test_handler._send_commands([test_req_1])

    # Check results
    self.assertEqual(results['status'], "error")
    self.assertEqual(results['message'], "An error occured downloading the response from the antenna controller.")

  def test_send_commands_malformed_response(self):
    """ Tests that the _send_commands method can correctly handle malformed responses. """

    def mock_request_handler(request):
      response = urllib2.addinfourl(StringIO("{\"invalid_json\":True}"), "mock headers", request.get_full_url())
      response.code = 200
      response.msg = "OK"
  
      return response

    # Build and submit some mock commands
    self._set_mock_request_builder(mock_request_handler)
    test_req_1 = self.test_handler._build_request("TC", {'param1': "waffles"})
    results = self.test_handler._send_commands([test_req_1])

    # Check results
    self.assertEqual(results['status'], "error")
    self.assertEqual(results['message'], "An error occured parsing the JSON response from the antenna controller.")

  def test_move_command(self):
    """ Verifies the functionality of the 'move' command. """

    # Submit a mock command
    self._set_mock_request_builder(mock_ac_success)
    test_command = MagicMock()
    test_command.parameters = {'azimuth': 42.0, 'elevation': 42.0}
    results = self.test_handler.command_move(test_command)

    # Validate results
    self.assertEqual(self.test_driver._controller_state['state'], "active")
    self.assertEqual(results['message'], "The antenna is being moved.")

    # Now submit a mock failed command
    self._set_mock_request_builder(mock_ac_failure)
    self.assertRaises(command.CommandError, self.test_handler.command_move, test_command)

  def test_park_command(self):
    """ Verifies the functionality of the 'park' command. """

    # Submit a mock command
    self._set_mock_request_builder(mock_ac_success)
    test_command = MagicMock()
    results = self.test_handler.command_park(test_command)

    # Validate results
    self.assertEqual(self.test_driver._controller_state['state'], "parking")
    self.assertEqual(results['message'], "The antenna is being parked.")

    # Now submit a mock failed command
    self._set_mock_request_builder(mock_ac_failure)
    test_command = MagicMock()
    self.assertRaises(command.CommandError, self.test_handler.command_park, test_command)

  def test_calibrate_command(self):
    """ Verifies the functionality of the 'calibrate' command. """

    # Submit a mock command
    self._set_mock_request_builder(mock_ac_success)
    test_command = MagicMock()
    results = self.test_handler.command_calibrate(test_command)

    # Validate results
    self.assertEqual(self.test_driver._controller_state['state'], "calibrating")
    self.assertEqual(results['message'], "The antenna is being calibrated.")

    # Now submit a mock failed command
    self._set_mock_request_builder(mock_ac_failure)
    test_command = MagicMock()
    self.assertRaises(command.CommandError, self.test_handler.command_calibrate, test_command)

  def test_calibrate_vert_command(self):
    """ Verifies the functionality of the 'calibrate_vert' command. """

    # Submit a mock command
    self._set_mock_request_builder(mock_ac_success)
    test_command = MagicMock()
    results = self.test_handler.command_calibrate_vert(test_command)

    # Validate results
    self.assertEqual(self.test_driver._controller_state['state'], "calibrating")
    self.assertEqual(results['message'], "The antenna is being vertically calibrated.")

    # Now submit a mock failed command
    self._set_mock_request_builder(mock_ac_failure)
    test_command = MagicMock()
    self.assertRaises(command.CommandError, self.test_handler.command_calibrate_vert, test_command)

  def test_calibrate_and_park_command(self):
    """ Verifies the functionality of the 'calibrate_and_park' command. """

    # Submit a mock command
    self._set_mock_request_builder(mock_ac_success_multiple)
    test_command = MagicMock()
    results = self.test_handler.command_calibrate_and_park(test_command)

    # Validate results
    self.assertEqual(self.test_driver._controller_state['state'], "calibrating")
    self.assertEqual(results['message'], "The antenna is being fully calibrated and will be parked at an Az/El of 270/0.")

    # Now submit a mock failed command
    self._set_mock_request_builder(mock_ac_failure_multiple)
    test_command = MagicMock()
    self.assertRaises(command.CommandError, self.test_handler.command_calibrate_and_park, test_command)

  def test_get_state_command(self):
    """ Verifies the functionality of the 'get_state' command. """

    # Submit a mock command
    self._set_mock_request_builder(mock_ac_state)
    test_command = MagicMock()
    results = self.test_handler.command_get_state(test_command)

    # Validate results
    self.assertEqual(results['azimuth'], 42.0)
    self.assertEqual(results['elevation'], 42.0)

    # Now submit a mock failed command
    self._set_mock_request_builder(mock_ac_failure)
    test_command = MagicMock()
    self.assertRaises(command.CommandError, self.test_handler.command_get_state, test_command)

  def test_stop_command(self):
    """ Verifies the functionality of the 'stop' command. """

    # Submit a mock command
    self._set_mock_request_builder(mock_ac_success)
    test_command = MagicMock()
    results = self.test_handler.command_stop(test_command)

    # Validate results
    self.assertEqual(self.test_driver._controller_state['state'], "stopped")
    self.assertEqual(results['message'], "The antenna controller has been stopped.")

    # Now submit a mock failed command
    self._set_mock_request_builder(mock_ac_failure)
    test_command = MagicMock()
    self.assertRaises(command.CommandError, self.test_handler.command_stop, test_command)

  def test_stop_emergency_command(self):
    """ Verifies the functionality of the 'stop_emergency' command. """

    # Submit a mock command
    self._set_mock_request_builder(mock_ac_success)
    test_command = MagicMock()
    results = self.test_handler.command_stop_emergency(test_command)

    # Validate results
    self.assertEqual(self.test_driver._controller_state['state'], "emergency_stopped")
    self.assertTrue("The antenna has been stopped and placed in emergency mode." in results['message'])

    # Now submit a mock failed command
    self._set_mock_request_builder(mock_ac_failure)
    test_command = MagicMock()
    self.assertRaises(command.CommandError, self.test_handler.command_stop_emergency, test_command)

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

  def _set_mock_request_builder(self, mock_request_handler):
    """ This method modifies the global urllib2 module to return a handler that we constructed that uses a custom 
    request handler to simulate network events.
    """

    urllib2.build_opener = self.old_build_opener
    test_build_opener = urllib2.build_opener(MockAntennaControllerHandler)
    urllib2.build_opener = lambda : test_build_opener
    for temp_handler in test_build_opener.handlers:
      if isinstance(temp_handler, MockAntennaControllerHandler):
        temp_handler.mock_request_builder = mock_request_handler
        break

    return test_build_opener

class MockAntennaControllerHandler(urllib2.HTTPHandler):
  """ A mock HTTP handler for simulating antenna controller API queries. """
  
  def http_open(self, req):
    return self.mock_request_builder(req)

def mock_ac_success(request):
  """ A mock urllib2 request handler that returns a simulated successful antenna controller API response for a single
  move command.
  """

  response = urllib2.addinfourl(StringIO("{\"status\":\"okay\",\"responses\":[{\"timestamp\":1384814185,\"command\":\"move\"}]}"), "mock headers", request.get_full_url())
  response.code = 200
  response.msg = "OK"
  
  return response

def mock_ac_success_multiple(request):
  """ A mock urllib2 request handler that returns a simulated successful antenna controller API response for sequential
  move and park commands.
  """

  response = urllib2.addinfourl(StringIO("{\"status\":\"okay\",\"responses\":[{\"timestamp\":1384814185,\"command\":\"move\"},{\"timestamp\":1384814185,\"command\":\"park\"}]}"), "mock headers", request.get_full_url())
  response.code = 200
  response.msg = "OK"
  
  return response

def mock_ac_failure(request):
  """ A mock urllib2 request handler that returns a simulated failed antenna controller API response for a single 
  command.
  """

  response = urllib2.addinfourl(StringIO("{\"status\":\"error\",\"message\":\"waffles\",\"responses\": []}"), "mock headers", request.get_full_url())
  response.code = 200
  response.msg = "OK"
  
  return response

def mock_ac_failure_multiple(request):
  """ A mock urllib2 request handler that returns a simulated failed antenna controller API response for sequential
  move and park commands.
  """

  response = urllib2.addinfourl(StringIO("{\"status\":\"error\",\"message\":\"waffles\",\"responses\":[{\"timestamp\":1384814185,\"command\":\"move\"}]}"), "mock headers", request.get_full_url())
  response.code = 200
  response.msg = "OK"
  
  return response

def mock_ac_state(request):
  """ A mock urllib2 request handler that returns a simulated successful antenna controller API response for a single
  state command.
  """

  response = urllib2.addinfourl(StringIO("{\"status\":\"okay\",\"responses\":[{\"timestamp\":1384814185,\"command\":\"state\",\"azimuth\":42.0,\"elevation\":42.0}]}"), "mock headers", request.get_full_url())
  response.code = 200
  response.msg = "OK"
  
  return response
