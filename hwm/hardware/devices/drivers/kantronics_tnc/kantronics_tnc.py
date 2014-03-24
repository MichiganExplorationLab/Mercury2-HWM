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
  """

  def __init__(self, device_configuration, command_parser):
    """ Sets up the TNC hardware driver.

    @param device_configuration  A dictionary containing the TNC's configuration options.
    @param command_parser        A reference to the active CommandParser instance.
    """

    super(Kantronics_TNC,self).__init__(device_configuration, command_parser)

    # Set configuration settings
    self.tnc_device = self.settings['tnc_device']

    # Initialize the 'tnc_state' service that can report the state of the TNC
    self._tnc_state_service = TNCStateService('kantronics_tnc_state', 'tnc_state', self)

    self._reset_TNC_state()

  def prepare_for_session(self, session_pipeline):
    """ Resets the TNC before each session.

    This method creates a Protocol that will be used to communicate with the TNC.

    @note The TNC must be configured (with a callsign, baud rate, etc.) before it can be used. If it has not been
          configured the TNC will probably not be able to send or receive data.

    @param session_pipeline  The Pipeline associated with the new session.
    @return Returns True once the configuration commands have been sent.
    """

    # Bind a protocol instance to the Serial port
    self._tnc_protocol = KantronicsTNCProtocol(self)
    self._serial_port_connection = serialport.SerialPort(self._tnc_protocol, self.tnc_device, reactor, baudrate='38400')
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

    @note Any radio drivers that interface with the TNC should take care to not change the uplink frequency while
          data is being written to the device. The 'tnc_state' service can be used to check if the TNC is currently 
          sending or likely to send data.

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
      'last_transmitted': 0,
    }

class TNCStateService(service.Service):
  """ Provides a service that reveals some state of the TNC. This is primarily used to make sure it is safe to change 
  the uplink frequency on the associated radio.
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
    """ Provides a dictionary containing the current state of the TNC such as the last time it transmitted data.

    @return Returns the TNC's state dictionary.
    """

    return self.tnc_driver.get_state()

class KantronicsTNCProtocol(LineReceiver):
  """ Used to pass data to and from the TNC over a serial transport.
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

