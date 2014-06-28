""" @package hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp
Contains the driver and command handler for MXL's homebrew USRP interface. 
"""

import logging, time, json
from twisted.internet import task, defer, threads
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import Protocol
from hwm.hardware.devices.drivers import driver
from hwm.hardware.pipelines import pipeline
from hwm.command import command
from hwm.command.handlers import handler

class MXL_USRP(driver.HardwareDriver):
  """ A driver for the MXL USRP.

  This driver enables communication with a USRP (software defined radio) using MXL's homebrew USRP interface.

  @note Currently, this driver only supports the USRP B100 (serial based).
  """

  def __init__(self, device_configuration, command_parser):
    """ Sets up the USRP driver. 

    @param device_configuration  A dictionary containing the USRP's basic configuration options. 
    @param command_parser        A reference to the active CommandParser instance.
    """

    super(MXL_USRP,self).__init__(device_configuration, command_parser)

    # Set configuration settings
    self.rx_device_address = device_configuration['rx_device_address']
    self.tx_device_address = device_configuration['tx_device_address']
    self.usrp_data_port = device_configuration['usrp_data_port']
    self.usrp_doppler_port = device_configuration['usrp_doppler_port']
    self.bit_rate = device_configuration['bit_rate']
    self.interpolation = device_configuration['interpolation']
    self.decimation = device_configuration['decimation']
    self.sampling_rate = device_configuration['sampling_rate']
    self.rx_gain = device_configuration['rx_gain']
    self.tx_gain = device_configuration['tx_gain']
    self.fm_dev = device_configuration['fm_dev']
    self.tx_fm_dev = device_configuration['tx_fm_dev']

    # Initialize the driver's command handler
    self._command_handler = USRPHandler(self)

    self._reset_driver_state()

  def prepare_for_session(self, session_pipeline):
    """ Prepares the USRP for a new session. 

    This method prepares the USRP driver for a new session by loading a 'tracker' service from its pipeline, which will
    be used to provide doppler correction information to the USRP interface. If no 'tracker' service is found the driver
    will still be set up, but it will not receive doppler corrections.

    @param session_pipeline  The Pipeline associated with the new session. 
    @return Returns True if the driver can locate a 'tracker' service from the session pipeline, and False otherwise. 
    """

    # Load the session pipeline's 'tracker' service
    self._session_pipeline = session_pipeline
    self._tracker_service = None
    try:
      self._tracker_service = session_pipeline.load_service("tracker")
    except pipeline.ServiceTypeNotFound as e:
      # A tracker service isn't available
      logging.warning("The '"+self.id+"' device could not load a 'tracker' service from the session's pipeline.")
      return False
    self._tracker_service.register_position_receiver(self.process_tracker_update)

    # Configure and run the GNU Radio block


    # Connect to the USRP's data and doppler update ports


    pass

  def cleanup_after_session(self):
    """ Puts the USRP back into its idle state after the active session has ended.

    This method cleans up after the active session has expired by stopping the GNU Radio block and resetting the radio
    state.
    """

    pass

  def get_state(self):
    """ Returns a dictionary containing information about the current state of the USRP such as its set frequencies and 

    @return Returns a dictionary containing the state of the USRP.
    """

    return self._usrp_state

  def process_tracker_update(self, new_position):
    """ This callback processes position updates from the session's pipeline's 'tracker' service, if available.

    When new tracking information is available, the included doppler multiplier will be used to calculate the corrected 
    RX frequency. 

    @param new_position  A dictionary containing new target position information from the tracker.
    """

    self._usrp_state['corrected_rx_freq'] = long(self._usrp_state['rx_freq']*new_position['doppler_multiplier'])


    self._usrp_doppler.write_doppler_correction(self._usrp_state['corrected_rx_freq'])


  def write(self, input_data):
    """ Writes the specified data chunk to the USRP via the USRPData protocol.

    @param input_data  A data chunk that should be sent to the USRP for transmission.
    """

    self._usrp_data.write(input_data)

  def _reset_driver_state(self):
    """ Resets the driver's state initially and in between sessions. """

    self._tracker_service = None
    self._session_pipeline = None
    self._usrp_data = None
    self._usrp_doppler = None
    self._usrp_state = {
      'decimation': 0,
      'interpolation': 0,
      'sampling_rate': 0,
      'bit_rate': 0,
      'rx_gain': 0.0,
      'tx_gain': 0.0,
      'rx_freq': 0, # Hz
      'corrected_rx_freq': 0, # Hz
      'tx_freq': 0 # Hz
    }

class USRPHandler(handler.DeviceCommandHandler):
  """ This command handler processes commands for the USRP radio. """

  pass

class USRPData(Protocol):
  """ This TCP Protocol is used to send and receive data to and from the USRP via its data port. """

  def __init__(self, driver):
    """ Sets up the USRP data protocol. 

    @param driver  The active USRP driver instance.
    """

    self.driver = driver

  def dataReceived(self, data):
    """ Receives a data chunk from the USRP and writes it to the driver's active pipeline.
    
    @param data  A chunk of data received by the USRP.
    """

    self.driver.write_output(data)

  def write(self, data):
    """ Writes the specified data chunk to the USRP for transmission.

    @param data  A user supplied data chunk from the session's pipeline. 
    """

    self.transport.write(data)

class USRPDoppler(Protocol):
  """ This TCP Protocol is used to send frequency updates to the USRP via its doppler correction port. """

  def write_doppler_correction(self, corrected_frequency):
    """ Writes the specified doppler corrected frequency to the USRP. 

    @param corrected_frequency  The corrected RX frequency in Hz.
    """

    self.transport.write("-f {0}".format(corrected_frequency))
