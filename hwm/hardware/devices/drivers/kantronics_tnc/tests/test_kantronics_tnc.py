# Import required modules
import logging, time
import mock
from mock import MagicMock, patch
from twisted.trial import unittest
from twisted.internet import defer
from twisted.internet import serialport
from twisted.test import proto_helpers
from StringIO import StringIO
from hwm.core.configuration import *
from hwm.hardware.devices.drivers.kantronics_tnc import kantronics_tnc

class TestKantronicsTNC(unittest.TestCase):
  """ This test suite verifies the functionality of the Kantronics TNC driver.
  """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.standard_tnc_config = {'id': "kantronics_tnc", 'settings': {'tnc_device': "ttySO", 'tnc_port': 2, 'callsign': "TSTCS"}}
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  def test_driver_init(self):
    """ Tests that the Kantronics_TNC constructor behaves as expected. It also tests the get_state() method in the 
    process.
    """

    # Create a TNC instance to test with
    test_cp = MagicMock()
    test_device = kantronics_tnc.Kantronics_TNC(self.standard_tnc_config, test_cp)

    # Make sure the constructor set the correct attributes
    self.assertEqual(test_device.tnc_device, self.standard_tnc_config['settings']['tnc_device'])
    self.assertEqual(test_device.tnc_port, self.standard_tnc_config['settings']['tnc_port'])
    self.assertEqual(test_device.callsign, self.standard_tnc_config['settings']['callsign'])
    self.assertEqual(test_device.get_state()['last_transmitted'], None)
    self.assertEqual(test_device.get_state()['output_buffer_size_bytes'], 0)

  @patch("twisted.internet.serialport.SerialPort")
  @patch("hwm.hardware.devices.drivers.kantronics_tnc.kantronics_tnc.KantronicsTNCProtocol")
  def test_prepare_for_session(self, mocked_KantronicsTNCProtocol, mocked_SerialPort):
    """ This test verifies that the driver for the Kantronics TNC properly resets the TNC before each session (in case 
    it was rebooted and lost its saved configuration, etc.).
    """

    # Create a TNC instance to test with
    test_cp = MagicMock()
    test_device = kantronics_tnc.Kantronics_TNC(self.standard_tnc_config, test_cp)

    # Prepare for the session and make sure the correct initialization commands are getting sent to the TNC
    # Note: Commands are checked in reverse order because 
    test_pipeline = MagicMock()
    test_device.prepare_for_session(test_pipeline)
    test_device._tnc_protocol.setLineMode.assert_called_once_with()
    test_device._tnc_protocol.sendLine.assert_has_calls([mock.call("txdelay 30/100"), mock.call("intface terminal"),
                                                         mock.call("xmitlvl 100/20"),
                                                         mock.call("port "+str(self.standard_tnc_config['settings']['tnc_port'])),
                                                         mock.call("abaud 38400"), mock.call("intface kiss"),
                                                         mock.call("reset")])
    test_device._tnc_protocol.setRawMode.assert_called_once_with()

  @patch("twisted.internet.serialport.SerialPort")
  @patch("hwm.hardware.devices.drivers.kantronics_tnc.kantronics_tnc.KantronicsTNCProtocol")
  def test_cleanup_after_session(self, mocked_KantronicsTNCProtocol, mocked_SerialPort):
    """ Verifies that the TNC driver correctly cleans up the TNC connection when instructed. """

    # Create a TNC instance to test with and start a session
    test_cp = MagicMock()
    test_device = kantronics_tnc.Kantronics_TNC(self.standard_tnc_config, test_cp)
    test_pipeline = MagicMock()
    test_device.prepare_for_session(test_pipeline)

    # Cleanup after the session and verify results
    old_tnc_protocol = test_device._tnc_protocol
    old_serial_port_connection = test_device._serial_port_connection
    test_device.cleanup_after_session()
    old_tnc_protocol.clearLineBuffer.assert_called_once_with()
    old_serial_port_connection.loseConnection.assert_called_once_with()
    self.assertEqual(test_device.get_state()['last_transmitted'], None)
    self.assertEqual(test_device.get_state()['output_buffer_size_bytes'], 0)

  def test_tnc_write(self):
    """ Tests that the TNC can be written to (i.e. that data gets sent to the serial port). """

    # Create a TNC driver to test with
    test_cp = MagicMock()
    test_device = kantronics_tnc.Kantronics_TNC(self.standard_tnc_config, test_cp)
    test_device._tnc_protocol = MagicMock()

    # Write some data to the TNC
    self.assertTrue(test_device._tnc_state['last_transmitted'] is None)
    test_device.write("waffles")
    test_device._tnc_protocol.transport.write.assert_called_once_with("waffles")
    self.assertTrue(test_device._tnc_state['last_transmitted'] is not None)

  def test_register_service(self):
    """ Tests that the TNC driver registers its 'tnc_state' service with the active pipeline. """

    # Create a TNC driver to test with
    test_cp = MagicMock()
    test_device = kantronics_tnc.Kantronics_TNC(self.standard_tnc_config, test_cp)
    
    # Register a mock pipeline with the device
    test_pipeline = MagicMock()
    test_device.register_pipeline(test_pipeline)
    test_pipeline.register_service.assert_called_once_with(test_device._tnc_state_service)

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

class TestKantronicsTNCStateService(unittest.TestCase):
  """ Tests the functionality of the Kantronics TNC driver's 'tnc_state' service, which provides information about the 
  TNC to other devices in the pipeline.
  """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.standard_tnc_config = {'id': "kantronics_tnc", 'settings': {'tnc_device': "ttySO", 'tnc_port': 2, 'callsign': "TSTCS"}}
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  def test_tnc_state_service(self):
    """ Tests the functionality of the 'tnc_state' service. """

    # Create a TNC driver to test with
    test_cp = MagicMock()
    test_device = kantronics_tnc.Kantronics_TNC(self.standard_tnc_config, test_cp)
    test_device._serial_port_connection = MagicMock()
    test_device._serial_port_connection._serial.outWaiting = MagicMock(return_value=10)

    # Create and test the service
    returned_state = test_device._tnc_state_service.get_state()
    self.assertEqual(returned_state['output_buffer_size_bytes'], 10)
    self.assertEqual(test_device._tnc_state['output_buffer_size_bytes'], 10)

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}

class TestKantronicsTNCProtocol(unittest.TestCase):
  """ Tests the Protocol that is used to connect to the TNC. """

  def setUp(self):
    # Set a local reference to Configuration and load a test config file
    self.config = Configuration
    self.config.verbose_startup = False
    self.standard_tnc_config = {'id': "kantronics_tnc", 'tnc_device': "ttySO", 'tnc_port': 2, 'callsign': "TSTCS"}
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)

  def tearDown(self):
    # Reset the recorded configuration values
    self._reset_config_entries()
    
    # Reset the configuration reference
    self.config = None

  def test_receiving_tnc_data(self):
    """ Verifies that the TNC serial protocol can correctly receive data from the TNC. Writing to the TNC just uses the 
    standard (already tested) transport.write method. """

    # Create a TNC driver to test with
    test_device = MagicMock()
    test_transport = proto_helpers.StringTransport()
    test_device._tnc_protocol = kantronics_tnc.KantronicsTNCProtocol(test_device)
    test_device._tnc_protocol.makeConnection(test_transport)
    
    # Mock some data coming from the TNC
    test_device._tnc_protocol.rawDataReceived("waffles")
    test_device.write_output.assert_called_once_with("waffles")

  def _reset_config_entries(self):
    # Reset the recorded configuration entries
    self.config.options = {}
    self.config.user_options = {}
