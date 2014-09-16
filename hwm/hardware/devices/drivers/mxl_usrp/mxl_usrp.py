""" @package hwm.hardware.devices.drivers.mxl_usrp.mxl_usrp
Contains the driver and command handler for MXL's homebrew USRP interface. 
"""

import logging, time, json
from twisted.internet import task, defer, threads, reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from hwm.hardware.devices.drivers import driver
from hwm.hardware.pipelines import pipeline
from hwm.command import command
from hwm.command.handlers import handler
from hwm.hardware.devices.drivers.mxl_usrp.GNURadio_top_block import USRPTopBlock

class MXL_USRP(driver.HardwareDriver):
  """ A driver for the MXL USRP.

  This driver enables communication with a USRP (software defined radio) using MXL's homebrew USRP interface.

  @note Currently, this driver supports just the USRP B100 (serial based).
  """

  def __init__(self, device_configuration, command_parser):
    """ Sets up the USRP driver. 

    @param device_configuration  A dictionary containing the USRP's basic configuration options. 
    @param command_parser        A reference to the active CommandParser instance.
    """

    super(MXL_USRP,self).__init__(device_configuration, command_parser)

    # Initialize the driver's command handler
    self._command_handler = USRPHandler(self)

    self._reset_driver_state()

  def prepare_for_session(self, session_pipeline):
    """ Prepares the USRP for a new session.

    This method prepares the USRP driver for a new session by loading a 'tracker' service from the session pipeline, 
    which will be used to provide doppler correction information to the USRP. It also initializes and starts the GNU 
    Radio top-level block (with default parameters) and connects to the USRP's data and doppler correction ports.

    @note If no 'tracker' service is found the radio will still be set up but it will not receive any doppler
          corrections.

    @throws May throw exceptions if the USRP GNU Radio block can't be initialized or started.

    @param session_pipeline  The Pipeline associated with the new session.
    @return Returns a DeferredList containing the USRP data and doppler port deferred connections.
    """

    # Load the session pipeline's 'tracker' service
    self._session_pipeline = session_pipeline
    self._tracker_service = None
    try:
      self._tracker_service = session_pipeline.load_service("tracker")
      self._tracker_service.register_position_receiver(self.process_tracker_update)
    except pipeline.ServiceTypeNotFound as e:
      # A tracker service isn't available
      logging.warning("The '"+self.id+"' device could not load a 'tracker' service from the session's pipeline.")

    # Initialize the GNU Radio top-block with default values
    self._usrp_flow_graph = USRPTopBlock(rx_device_address = self.settings['rx_device_address'],
                                         tx_device_address = self.settings['tx_device_address'],
                                         data_port = self.settings['usrp_data_port'],
                                         doppler_port = self.settings['usrp_doppler_port'],
                                         bit_rate = self.settings['bit_rate'], 
                                         interpolation = self.settings['interpolation'],
                                         decimation = self.settings['decimation'], 
                                         sampling_rate = self.settings['sampling_rate'],
                                         rx_freq = 435.0e6,
                                         tx_freq = 435.0e6,
                                         rx_gain = self.settings['rx_gain'],
                                         tx_gain = self.settings['tx_gain'],
                                         fm_dev = self.settings['fm_dev'],
                                         tx_fm_dev = self.settings['tx_fm_dev'])
    self._usrp_flow_graph.run(True)
    self._usrp_flow_graph_running = True

    # Connect to the data and doppler correction ports
    data_endpoint = TCP4ClientEndpoint(reactor, self.settings['usrp_host'], self.settings['usrp_data_port'])
    self._usrp_data = USRPData(self)
    data_endpoint_deferred = connectProtocol(data_endpoint, self._usrp_data)
    doppler_endpoint = TCP4ClientEndpoint(reactor, self.settings['usrp_host'], self.settings['usrp_doppler_port'])
    self._usrp_doppler = USRPDoppler()
    doppler_endpoint_deferred = connectProtocol(doppler_endpoint, self._usrp_doppler)

    return defer.DeferredList([data_endpoint_deferred, doppler_endpoint_deferred], consumeErrors = False)

  def cleanup_after_session(self):
    """ Puts the USRP back into its idle state after the active session has ended.

    This method cleans up after the active session has expired by stopping the GNU Radio block and resetting the radio
    state.

    @throws May raise exceptions if the flow graph can not be stopped.
    """

    # Stop the GNU Radio flow graph
    if self._usrp_flow_graph_running:
      self._usrp_flow_graph.stop()

    self._reset_driver_state()

  def get_state(self):
    """ Returns a dictionary containing information about the current state of the USRP such as its set frequencies and 

    @return Returns a dictionary containing the state of the USRP.
    """

    return self._usrp_state

  def write(self, input_data):
    """ Writes the specified data chunk to the USRP via the USRPData protocol.

    @param input_data  A data chunk that should be sent to the USRP for transmission.
    """

    self._usrp_data.write(input_data)

  def process_tracker_update(self, new_position):
    """ This callback processes position updates from the session's pipeline's 'tracker' service, if available.

    When new tracking information is available, the included doppler multiplier will be used to calculate the corrected 
    RX frequency. 

    @param new_position  A dictionary containing new target position information from the tracker.
    """

    self._usrp_state['corrected_rx_freq'] = long(self._usrp_state['rx_freq']*new_position['doppler_multiplier'])
    self._usrp_doppler.write_doppler_correction(self._usrp_state['corrected_rx_freq'])

  def _reset_driver_state(self):
    """ Resets the driver's state initially and in between sessions. """

    self._tracker_service = None
    self._session_pipeline = None
    self._usrp_flow_graph = None
    self._usrp_flow_graph_running = False
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

  def command_set_rx_freq(self, command):
    """ Updates the USRP's receive frequency.

    @throws Raises CommandError if the RX frequency can't be set.

    @param command  The currently executing command instance.
    @return Returns a deferred that will be fired with a dictionary containing the command results.
    """

    # Lock the flow graph and try to update the RX frequency
    self.driver._usrp_flow_graph.lock()
    try:
      self.driver._usrp_flow_graph.usrp_block.set_rxfreq(command.parameters['rx_freq'])
    except Exception as usrp_error:
      raise command.CommandError("An error occured while setting the USRP's RX frequency to {0} hz: {1}".format(
                                 command.parameters['rx_freq'], str(usrp_error)))
    self.driver._usrp_flow_graph.unlock()

    return defer.returnValue({'message': "The USRP's RX frequency has been set."})

  def settings_set_rx_freq(self):
    """ Returns command meta-data for the 'set_rx_freq' command.

    @return Returns a dictionary containing the command meta-data.
    """

    # Define the command parameters
    command_parameters = [
      {
        "type": "number",
        "integer": True,
        "required": True,
        "title": "RX frequency",
        "description": "The desired RX frequency of the USRP in hertz."
      }
    ]

    return build_metadata_dict(command_parameters, 'set_rx_freq', self.name, requires_active_session = True,
                               schedulable = True, use_as_initial_value = True)

  def command_set_tx_freq(self, command):
    """ Updates the USRP's transmit frequency.

    @throws Raises CommandError if the TX frequency can't be set.

    @param command  The currently executing command instance.
    @return Returns a deferred that will be fired with a dictionary containing the command results.
    """

    # Lock the flow graph and try to update the RX frequency
    self.driver._usrp_flow_graph.lock()
    try:
      self.driver._usrp_flow_graph.usrp_block.set_txfreq(command.parameters['tx_freq'])
    except Exception as usrp_error:
      raise command.CommandError("An error occured while setting the USRP's TX frequency to {0} hz: {1}".format(
                                 command.parameters['rx_freq'], str(usrp_error)))
    self.driver._usrp_flow_graph.unlock()

    return defer.returnValue({'message': "The USRP's TX frequency has been set."})

  def settings_set_tx_freq(self):
    """ Returns command meta-data for the 'set_tx_freq' command. 

    @return Returns a dictionary containing the command meta-data.
    """

    # Define the command parameters
    command_parameters = [
      {
        "type": "number",
        "integer": True,
        "required": True,
        "title": "TX frequency",
        "description": "The desired TX frequency of the USRP in hertz."
      }
    ]

    return build_metadata_dict(command_parameters, 'set_tx_freq', self.name, requires_active_session = True,
                               schedulable = True, use_as_initial_value = True)

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
