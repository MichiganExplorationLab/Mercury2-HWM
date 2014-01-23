""" @package hwm.hardware.devices.drivers.kantronics_tnc.kantronics_tnc
This module contains a simple driver for Kantronics TNCs as well as a service that it uses to report its state to other 
pipeline devices.
"""

# Import required modules
import logging, time
from twisted.internet import task, defer, reactor
from twisted.internet import serialport
from twisted.protocols.basic import LineReceiver
from hwm.hardware.devices.drivers import driver, service

class Kantronics_TNC(driver.HardwareDriver):
  """" A driver for the Kantronics TNC.

  This class provides a driver for the Kantronics TNC. It is designed to work in conjunction with a radio and serves as 
  the pipeline's input and output device (i.e. the device that pipeline data flows into and out of).

  @note This driver is currently very simple and not capable of sending commands on demand like other drivers. It is 
        simply responsible for setting up the TNC, relaying the pipeline data stream to and from it, and for providing 
        a service to the pipeline to check the state of the TNC (to make sure it's safe to change the radio frequency, 
        for example).
  """

  def __init__(self, device_configuration, command_parser):
    """ Sets up the TNC hardware driver.

    @param device_configuration  A dictionary containing the TNC's configuration options.
    @param command_parser        A reference to the active CommandParser instance.
    """

    super(Kantronics_TNC,self).__init__(device_configuration, command_parser)

    # Set configuration settings
    self.tnc_device = self.settings['tnc_device']
    self.tnc_port = self.settings['tnc_port']
    self.callsign = self.settings['callsign']

    # Initialize the 'tnc_state' service that can report the state of the TNC
    self._tnc_state_service = TNCStateService('sgp4_propagation_service', 'tnc_state', self)

    self._reset_TNC_state()

  def prepare_for_session(self, session_pipeline):
    """ Resets the TNC before each session.

    This method resets the TNC before each session by sending the necessary configuration settings.

    @note Generally, the TNC must be reset before each session because it may have been rebooted between sessions, 
          loosing the saved configuration settings in the process.

    @param session_pipeline  The Pipeline associated with the new session.
    @return Returns True once the configuration commands have been sent.
    """

    # Bind a protocol instance to the Serial port
    self._tnc_protocol = KantronicsTNCProtocol(self)
    self._serial_port_connection = serialport.SerialPort(self._tnc_protocol, self.tnc_device, reactor, baudrate='38400')

    # Write the configuration settings to the TNC using the command protocol
    self._tnc_protocol.setLineMode()
    self._tnc_protocol.sendLine(self.callsign)
    self._tnc_protocol.sendLine("txdelay 30/100")
    self._tnc_protocol.sendLine("intface terminal")
    self._tnc_protocol.sendLine("xmitlvl 100/20")
    self._tnc_protocol.sendLine("port "+str(self.tnc_port))
    self._tnc_protocol.sendLine("abaud 38400")
    self._tnc_protocol.sendLine("intface kiss")
    self._tnc_protocol.sendLine("reset")
    self._tnc_protocol.setRawMode()
  
  def cleanup_after_session(self):
    """ Resets the TNC to its idle state after the session using it has ended.
    """

    # Reset the device
    self._tnc_protocol.clearLineBuffer()
    self._serial_port_connection.loseConnection()
    self._reset_TNC_state()

  def get_state(self):
    """ Provides a dictionary that contains the current state of the TNC.

    @return Returns a dictionary containing elements of the TNC's state.
    """

    return self._tnc_state

  def write(self, input_data):
    """ Writes the specified chunk of input data to the TNC.

    @note Any radio drivers that interface with this driver should take care to not change the uplink frequency while
          data is being written to the device (the 'tnc_state' service can be used to check if the TNC is currently 
          receiving or likely to receive data).

    @param input_data  A user provided data chunk that is to be sent to the TNC.
    """

    # Write the data to the TNC
    self._tnc_protocol.transport.write(input_data)
    self._tnc_state['last_transmitted'] = int(time.time())

  def _register_services(self, session_pipeline):
    """ Registers the TNC's tnc_state service with the session pipeline.

    @param session_pipeline  The pipeline being used by the new session.
    """

    session_pipeline.register_service(self._tnc_state_service)

  def _reset_TNC_state(self):
    """ Resets the TNC driver's state.
    """

    # Reset protocol attributes
    self._tnc_protocol = None
    self._serial_port_connection = None
    self._tnc_state = {
      "last_transmitted": None,
      "output_buffer_size_bytes": 0
    }

class TNCStateService(service.Service):
  """ Provides a service that reveals the state of the TNC buffer. This is used to make sure it is safe to change the 
  uplink frequency on the device.
  """

  def __init__(self, service_id, service_type, tnc_driver):
    """ Sets up the TNC state reporting service.

    @param service_id            The unique service ID.
    @param service_type          The service type. Other drivers, such as the antenna controller driver, will search the
                                 active pipeline for this when looking for this service.
    @param tnc_driver            The HardwareDriver representing the TNC.
    """

    super(TNCStateService,self).__init__(service_id, service_type)

    self.tnc_driver = tnc_driver

  def get_state(self):
    """ Returns a dictionary containing properties of the TNC connection such as it's buffer and last time modified.

    @note This method also updates the state of the TNC driver with the newly measured buffer size, which is measured 
          each time this method is called.
    """

    self.tnc_driver._tnc_state['output_buffer_size_bytes'] = self.tnc_driver._serial_port_connection._serial.outWaiting()

    return self.tnc_driver.get_state()

class KantronicsTNCProtocol(LineReceiver):
  """ A protocol that is used to relay command and pipeline data streams to and from the TNC.
  """

  def __init__(self, tnc_driver):
    """ Sets up the protocol.

    @param tnc_driver  The Kantronics_TNC using this connection.
    """

    self.tnc_driver = tnc_driver

  def rawDataReceived(self, data):
    """ Passes data received by the TNC to the driver.

    @param data  A data chunk of arbitrary size from the TNC.
    """

    # Pass the data up the pipeline
    self.tnc_driver.write_output(data)