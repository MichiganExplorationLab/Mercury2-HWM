import logging, time
from pkg_resources import Requirement, resource_filename
from mock import MagicMock, patch
from twisted.trial import unittest
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks
from hwm.core.configuration import *
from hwm.command import command
from hwm.hardware.pipelines import pipeline
from hwm.hardware.devices.drivers.mxl_usrp import mxl_usrp

# Some globals that apply across test classes
standard_device_configuration = {
  'id': "test_usrp",
  'settings': {
    'rx_device_address': "serial=E7R11Y3B1",
    'tx_device_address': "serial=E7R11Y3B1",
    'usrp_host': "localhost",
    'usrp_data_port': 12400,
    'usrp_doppler_port': 12401,
    'bit_rate': 9600,
    'interpolation': 3,
    'decimation': 5,
    'sampling_rate': 256000,
    'rx_gain': 20,
    'tx_gain': 10,
    'fm_dev': 3000,
    'tx_fm_dev': 8000
  }
}

class TestMXLUSRPDriver(unittest.TestCase):
  """ This test suite tests the functionality of the custom MXL USRP driver.

  @note None of the tests in this module test the functionality of the GNU Radio USRP driver. 
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

  def _mock_connectProtocol(endpoint, protocol):
    """ A mock of the twisted.internet.endpoints.connectProtocol function that immediately returns the Protocol in a 
    deferred.
    """

    return defer.succeed(protocol)

  def test_initialization(self):
    """ This test verifies that the USRP driver correctly initializes itself. """

    # Create a mock pipeline and initialize the driver
    test_pipeline = MagicMock()
    test_device = mxl_usrp.MXL_USRP(standard_device_configuration, MagicMock())
    tracker_service = MagicMock()
    test_pipeline.load_service = lambda service_id : tracker_service

    # Verify the results
    default_settings = standard_device_configuration['settings']
    self.assertEqual(test_device.settings['rx_device_address'], default_settings['rx_device_address'])
    self.assertEqual(test_device.settings['tx_device_address'], default_settings['tx_device_address'])
    self.assertEqual(test_device.settings['usrp_host'], default_settings['usrp_host'])
    self.assertEqual(test_device.settings['usrp_data_port'], default_settings['usrp_data_port'])
    self.assertEqual(test_device.settings['usrp_doppler_port'], default_settings['usrp_doppler_port'])
    self.assertEqual(test_device.settings['bit_rate'], default_settings['bit_rate'])
    self.assertEqual(test_device.settings['interpolation'], default_settings['interpolation'])
    self.assertEqual(test_device.settings['decimation'], default_settings['decimation'])
    self.assertEqual(test_device.settings['sampling_rate'], default_settings['sampling_rate'])
    self.assertEqual(test_device.settings['rx_gain'], default_settings['rx_gain'])
    self.assertEqual(test_device.settings['tx_gain'], default_settings['tx_gain'])
    self.assertEqual(test_device.settings['fm_dev'], default_settings['fm_dev'])
    self.assertEqual(test_device.settings['tx_fm_dev'], default_settings['tx_fm_dev'])
    self.assertTrue(isinstance(test_device._command_handler, mxl_usrp.USRPHandler))

  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.USRPTopBlock')
  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.TCP4ClientEndpoint')
  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.connectProtocol', new = _mock_connectProtocol)
  @inlineCallbacks
  def test_prepare_for_session(self, mock_TCP4ClientEndpoint, mock_USRPTopBlock):
    """ This test verifies that the USRP driver can successfully prepare for a new session. """

    # Create a mock driver and pipeline to test with
    test_pipeline = MagicMock()
    test_device = mxl_usrp.MXL_USRP(standard_device_configuration, MagicMock())
    tracker_service = MagicMock()
    test_pipeline.load_service = lambda service_id : tracker_service

    # Prepare for the session
    protocol_deferreds = test_device.prepare_for_session(test_pipeline)
    result = yield protocol_deferreds

    # Verify the results
    default_settings = standard_device_configuration['settings']
    tracker_service.register_position_receiver.assert_called_once_with(test_device.process_tracker_update)
    test_device._usrp_flow_graph.run.assert_called_once_with(True)
    self.assertTrue(test_device._usrp_flow_graph_running)

    self.assertTrue(isinstance(result[0][1], mxl_usrp.USRPData))
    self.assertTrue(isinstance(result[1][1], mxl_usrp.USRPDoppler))

  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.USRPTopBlock')
  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.TCP4ClientEndpoint')
  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.connectProtocol', new = _mock_connectProtocol)
  @inlineCallbacks
  def test_prepare_for_session_missing_service(self, mock_TCP4ClientEndpoint, mock_USRPTopBlock):
    """ This test verifies that the USRP driver correctly responds to a missing 'tracker' service when preparing for a 
    new session. It should ignore the error and continue setting up the driver. """

    # Create a mock driver and pipeline to test with
    test_pipeline = MagicMock()
    test_device = mxl_usrp.MXL_USRP(standard_device_configuration, MagicMock())
    tracker_service = MagicMock()
    test_pipeline.load_service = MagicMock(side_effect=pipeline.ServiceTypeNotFound)

    # Prepare for the session
    protocol_deferreds = test_device.prepare_for_session(test_pipeline)
    result = yield protocol_deferreds

    # Verify the results
    test_pipeline.load_service.assert_called_once_with("tracker")
    test_device._usrp_flow_graph.run.assert_called_once_with(True)
    self.assertTrue(test_device._usrp_flow_graph_running)

  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.USRPTopBlock')
  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.TCP4ClientEndpoint')
  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.connectProtocol', new = _mock_connectProtocol)
  @inlineCallbacks
  def test_cleanup_after_session(self, mock_TCP4ClientEndpoint, mock_USRPTopBlock):
    """ This test verified that the 'cleanup_after_session' method behaves as expected. """

    # Create a mock driver and pipeline to test with
    test_pipeline = MagicMock()
    test_device = mxl_usrp.MXL_USRP(standard_device_configuration, MagicMock())
    tracker_service = MagicMock()
    test_pipeline.load_service = lambda service_id : tracker_service

    # Prepare for the session
    protocol_deferreds = test_device.prepare_for_session(test_pipeline)
    result = yield protocol_deferreds

    # Clean up after the session
    old_usrp_flow_graph = test_device._usrp_flow_graph
    test_device.cleanup_after_session()

    # Verify the results
    old_usrp_flow_graph.stop.assert_called_once_with()
    self.assertTrue(not test_device._usrp_flow_graph_running)

  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.USRPTopBlock')
  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.TCP4ClientEndpoint')
  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.connectProtocol', new = _mock_connectProtocol)
  @inlineCallbacks
  def test_writing_to_radio(self, mock_TCP4ClientEndpoint, mock_USRPTopBlock):
    """ This test verifies that the radio can be written to. """

    # Create a mock driver and pipeline to test with
    test_pipeline = MagicMock()
    test_device = mxl_usrp.MXL_USRP(standard_device_configuration, MagicMock())

    # Pepare for a new session
    protocol_deferreds = test_device.prepare_for_session(test_pipeline)
    result = yield protocol_deferreds

    # Mock the USRP's data transport
    test_device._usrp_data.transport = MagicMock()

    # Attempt to write to the USRP and verify
    test_device.write("waffles")
    test_device._usrp_data.transport.write.assert_called_once_with("waffles")

  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.USRPTopBlock')
  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.TCP4ClientEndpoint')
  @patch('hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp.connectProtocol', new = _mock_connectProtocol)
  @inlineCallbacks
  def test_doppler_update_processing(self, mock_TCP4ClientEndpoint, mock_USRPTopBlock):
    """ This method tests the process_tracker_update callback, which receives new tracking and doppler offset
    information from the active tracker.
    """

    # Create a mock driver and pipeline to test with
    test_pipeline = MagicMock()
    test_device = mxl_usrp.MXL_USRP(standard_device_configuration, MagicMock())

    # Prepare for a new session
    protocol_deferreds = test_device.prepare_for_session(test_pipeline)
    result = yield protocol_deferreds

    # Mock the USRP's doppler transport
    test_device._usrp_doppler.transport = MagicMock()

    # Send a doppler update to the driver and verify the results
    test_device._usrp_state['rx_freq'] = 100
    position_update = {'doppler_multiplier': 0.95}
    test_device.process_tracker_update(position_update)

    # Verify that the doppler update string was passed to the USRP's socket
    self.assertEqual(test_device._usrp_state['corrected_rx_freq'], 95)
    test_device._usrp_doppler.transport.write.assert_called_once_with('-f 95')

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

class TestMXLUSRPHandler(unittest.TestCase):
  """ This test suite tests the functionality of the MXL USRP driver.

  @note The tests in this class test the functionality of the USRP's command handler without calling 
  prepare_for_session, which requires the _mock_protocol_tools and _mock_connectProtocol decorators.
  """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    self.config.read_configuration(self.source_data_directory+'/core/tests/data/test_config_basic.yml')

    # Mock the USRP driver and GNU Radio USRP driver
    test_pipeline = MagicMock()
    self.test_device = mxl_usrp.MXL_USRP(standard_device_configuration, MagicMock())
    self.test_device._usrp_flow_graph = MagicMock()
    self.test_device._usrp_flow_graph.usrp_block = MagicMock()
    self.command_handler = self.test_device._command_handler
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  @inlineCallbacks
  def test_set_rx_freq_command(self):
    """ Verifies that the 'set_rx_freq' command correctly sets the USRP's RX frequency and that it handles possible 
    errors that may occur. """

    def mock_set_rxfreq(new_freq):
      raise TypeError("Test USRP error")

    # Attempt to set the frequency
    test_frequency = 500000000
    test_command = MagicMock()
    test_command.parameters = {'rx_freq': test_frequency}
    command_deferred = self.command_handler.command_set_rx_freq(test_command)
    results = yield command_deferred
    
    # Verify the results
    self.assertTrue("RX frequency has been set" in results['message'])
    self.test_device._usrp_flow_graph.lock.assert_called_once_with()
    self.test_device._usrp_flow_graph.usrp_block.set_rxfreq.assert_called_once_with(test_frequency)
    self.test_device._usrp_flow_graph.unlock.assert_called_once_with()

    # Try again with a simulated USRP error
    self.test_device._usrp_flow_graph.usrp_block.set_rxfreq = mock_set_rxfreq
    command_deferred_error = self.command_handler.command_set_rx_freq(test_command)
    yield self.assertFailure(command_deferred_error, command.CommandError)

  @inlineCallbacks
  def test_set_tx_freq_command(self):
    """ Verifies that the 'set_tx_freq' command correctly sets the USRP's TX frequency and that it handles possible 
    errors that may occur. """

    def mock_set_txfreq(new_freq):
      raise TypeError("Test USRP error")

    # Attempt to set the frequency
    test_frequency = 500000000
    test_command = MagicMock()
    test_command.parameters = {'tx_freq': test_frequency}
    command_deferred = self.command_handler.command_set_tx_freq(test_command)
    results = yield command_deferred
    
    # Verify the results
    self.assertEqual("TX frequency has been set" in results['message'])
    self.test_device._usrp_flow_graph.lock.assert_called_once_with()
    self.test_device._usrp_flow_graph.usrp_block.set_txfreq.assert_called_once_with(test_frequency)
    self.test_device._usrp_flow_graph.unlock.assert_called_once_with()

    # Try again with a simulated USRP error
    self.test_device._usrp_flow_graph.usrp_block.set_txfreq = mock_set_txfreq
    command_deferred_error = self.command_handler.command_set_tx_freq(test_command)
    yield self.assertFailure(command_deferred_error, command.CommandError)

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}
