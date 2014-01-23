""" @package hwm.hardware.devices.drivers.icom_910.icom_910
This module contains a hardware driver and command handler for the ICOM 910 radio.
"""

# Import required modules
import logging, time
import Hamlib
from twisted.internet import task, defer
from twisted.internet.defer import inlineCallbacks
from hwm.core.configuration import *
from hwm.hardware.pipelines import pipeline
from hwm.hardware.devices.drivers import driver
from hwm.command import command
from hwm.command.handlers import handler

class ICOM_910(driver.HardwareDriver):
  """ A driver for the ICOM 910 radio.

  This class provides a hardware driver for the ICOM 910 series of radios. It is primarily responsible for controlling 
  the radio and automatically correcting its frequency for doppler shifts. In addition, it provides a command handler 
  capable of controlling the ICOM 910.

  @note This driver requires that Hamlib2 be installed and configured, including the Python bindings.
  @note This driver is not currently capable of sending or receiving data to or from the radio directly. It is designed 
        for pipelines that also contain a TNC, which will serve as the pipeline's input and output device.
  @note This driver is currently setup to operate in half-duplex mode. In half-duplex mode, only the MAIN VFO is set and
        the uplink frequency is specified via a split frequency.
  @note The ICOM 910 driver will work with the TNC driver to make sure that it doesn't change its frequency when the 
        TNC is receiving data. This will prevent the ICOM from entering an undefined state.
  """

  def __init__(self, device_configuration, command_parser):
    """ Sets up the ICOM 910h driver.

    @param device_configuration  A dictionary containing the radios's configuration options.
    @param command_parser        A reference to the active CommandParser instance. The driver will use this to
                                 automatically update the RX and TX frequencies as needed.
    """

    super(ICOM_910,self).__init__(device_configuration, command_parser)

    # Set configuration settings
    self.icom_device_path = self.settings['icom_device_path']
    self.doppler_update_frequency = self.settings['doppler_update_frequency'] # s
    self.doppler_update_inactive_tx_delay = self.settings['doppler_update_inactive_tx_delay'] # s

    # Initialize the driver's command handler
    self._command_handler = ICOM910Handler(self)

    self._reset_driver_state()

  def prepare_for_session(self, session_pipeline):
    """ Prepares the radio for use by a new session by loading the necessary services and setting up Hamlib.

    @note This method loads the active 'tracker' service from the session pipeline. The driver will use this service to 
          load the doppler shift multiplier for the active target. If a 'tracker' service can not be loaded, no doppler
          correction will be applied.
    @note This method loads the active 'tnc_state' service from the session pipeline. The driver will use this service 
          to make sure that it does not allow its uplink frequency to be changed if data is being transmitted. If this 
          service can't be located, no such protection will be provided (possibly putting the radio into an undefined 
          state).

    @param session_pipeline  The Pipeline associated with the new session.
    @return Returns True once the radio is ready for use by the session.
    """

    self._reset_driver_state()

    # Load the 'tracker' service
    self._session_pipeline = session_pipeline
    try:
      self._tracker_service = session_pipeline.load_service("tracker")
      self._tracker_service.register_position_receiver(self.process_new_doppler_correction)
    except pipeline.ServiceTypeNotFound as e:
      # A tracker service isn't available
      logging.error("The "+self.id+" driver could not load a 'tracker' service from the session's pipeline.")

    # Load the 'tnc_state' service
    try:
      self._tnc_state_service = session_pipeline.load_service("tnc_state")
    except pipeline.ServiceTypeNotFound as e:
      # A tnc_state service isn't available
      logging.error("The "+self.id+" driver could not load a 'tnc_state' service from the session's pipeline.")

    # Create a Hamlib rig for the radio
    Hamlib.rig_set_debug(Hamlib.RIG_DEBUG_NONE)
    self._command_handler.radio_rig = Hamlib.Rig(Hamlib.RIG_MODEL_IC910)
    self._command_handler.radio_rig.set_conf("rig_pathname",self.icom_device_path)
    self._command_handler.radio_rig.set_conf("retry","5")
    self._command_handler.radio_rig.open()

    return True

  def cleanup_after_session(self):
    """ Resets the radio to its idle state after the session using it has ended.
    """

    # Reset the device
    self._command_handler.radio_rig.close()
    self._command_handler.radio_rig = None
    self._reset_driver_state()

    return

  def get_state(self):
    """ Provides a dictionary that contains the current state of the radio.

    @return Returns a dictionary containing select elements of radio state.
    """

    return self._radio_state

  @inlineCallbacks
  def process_new_doppler_correction(self, target_position):
    """ Notifies the radio driver that new doppler correction information is available.

    This inline callback receives new target position information (including the doppler correction) from a 'tracker' 
    service. The driver will use this information to periodically (as defined in the configuration) update the uplink 
    and downlink frequencies on the radio.

    @note If the active tracker service doesn't provide a doppler correction, this method will not update the radio's
          frequency.
    @note Because this method uses the set_uplink_freq command, it will only update the uplink frequency if the radio is
          not currently transmitting (as determined by the pipeline's tnc_state service). If the TNC is receiving data 
          when the command is received, it will be ignored.

    @param target_position  A dictionary containing details about the target's position, including its doppler 
                            correction.
    @return Returns True after updating both the uplink and download frequencies or False if an error occurs.
    """

    # Verify the the target position
    if 'doppler_multiplier' not in target_position:
      logging.error("The target position provided to the '"+self.id+"' driver did not contain a doppler correction multiplier.")
      yield defer.returnValue(False)

    # Make sure it's been long enough since the last update
    if (int(time.time()) - self._last_doppler_update) > self.doppler_update_frequency:
      downlink_freq_set = False
      uplink_freq_set = False

      # Send the command to update the downlink frequency
      new_downlink_freq = target_position['doppler_multiplier'] * self._radio_state['set_rx_freq']
      command_request = {
        'command': "set_rx_freq",
        'destination': self._session_pipeline.id+"."+self.id,
        'parameters': {
          'frequency': new_downlink_freq
        }
      }
      command_deferred = self._command_parser.parse_command(command_request, 
                                                            user_id = self._session_pipeline.current_session.user_id)
      results = yield command_deferred

      # Send the command to update the uplink frequency
      if results['response']['status'] is not 'error':
        downlink_freq_set = True
      new_uplink_freq = target_position['doppler_multiplier'] * self._radio_state['set_tx_freq']
      command_request = {
        'command': "set_tx_freq",
        'destination': self._session_pipeline.id+"."+self.id,
        'parameters': {
          'frequency': new_uplink_freq
        }
      }
      command_deferred = self._command_parser.parse_command(command_request, 
                                                            user_id = self._session_pipeline.current_session.user_id)
      results = yield command_deferred

      # Verify the results
      if results['response']['status'] is not 'error':
        uplink_freq_set = True

      if uplink_freq_set and downlink_freq_set:
        self._last_doppler_update = time.time()
        yield defer.returnValue(True)
      else:
        logging.error("The '"+self.id+"' driver did not update its doppler correction because one or both of the "+
                      "'set_rx_freq' and 'set_tx_freq' commands failed.")
        yield defer.returnValue(False)

  def _reset_driver_state(self):
    """ Resets the radio driver's state.
    """

    # Set the driver's attributes
    self._tracker_service = None
    self._tnc_state_service = None
    self._session_pipeline = None
    self._last_doppler_update = 0
    self._radio_state = {
      "set_tx_freq": 0.0,
      "set_rx_freq": 0.0,
      "shifted_tx_freq": 0.0,
      "shifted_rx_freq": 0.0,
      "mode": None
    }

class ICOM910Handler(handler.DeviceCommandHandler):
  """ A command handler that handles basic commands for the ICOM 910 series of radios.

  @note Most of the commands in this handler require that Hamlib be installed with the Python bindings.
  """

  def __init__(self, driver):
    """ Sets up the ICOM 910 command handler.

    @param driver  The Driver instance that offers this command handler.
    """

    super(ICOM910Handler,self).__init__(driver)

    # Set handler state
    self.radio_rig = None

  def command_set_mode(self, active_command):
    """ Sets the radio's mode and updates the driver's state appropriately.
    
    @note Currently, this command can only set the mode to: "FM"

    @throws Raises CommandError if the command fails for some reason.

    @param active_command  The executing Command. Contains the command parameters.
    @return Returns a dictionary containing the command response.
    """

    if self.radio_rig is not None:
      if 'mode' in active_command.parameters:
        # Set the mode in Hamlib
        new_mode = active_command.parameters['mode']
        if new_mode == "FM":
          response = self.radio_rig.set_mode(Hamlib.RIG_MODE_FM)
        else:
          raise command.CommandError("An unrecognized mode was specified.")

        # Check for errors
        if response is not Hamlib.RIG_OK:
          raise command.CommandError("An error occured setting the radio's mode.")

        # Get the mode and update the driver state
        mode, width = self.radio_rig.get_mode()
        self.driver._radio_state['mode'] = Hamlib.rig_strrmode(mode)

        return {'message': "The radio mode has been set.", 'mode': new_mode}
      else:
        raise command.CommandError("No mode specified for the 'set_mode' command.")
    else:
      raise command.CommandError("The "+self.driver.id+" command handler does not have an initialized Hamlib rig.")

  def settings_set_mode(self):
    """ Meta-data for the "set_mode" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    command_parameters = [
      {
        "type": "select",
        "required": True,
        "title": "mode",
        "description": "The Icom 910's mode.",
        "multiselect": False,
        "options": [
          ['FM', 'FM']
        ]
      }
    ]

    return build_metadata_dict(command_parameters, 'set_mode', self.name, requires_active_session = True)

  def command_set_rx_freq(self, active_command):
    """ Sets the downlink frequency of the radio.

    @note This driver works in half-duplex mode with the RX frequency set on the main VFO and the TX frequency set via 
          a split mode.

    @throws Raises CommandError if the command fails for some reason.
    
    @param active_command  The executing Command. Contains the command parameters.
    @return Returns a dictionary containing the command response.
    """

    if self.radio_rig is not None:
      if 'rx_freq' in active_command.parameters:
        # Set the rx frequency as the main VFO frequency
        response = self.radio_rig.set_freq(int(active_command.parameters['rx_freq']*1000000), Hamlib.RIG_VFO_MAIN)

        if response is not Hamlib.RIG_OK:
          raise command.CommandError("An error occured while setting the radio's RX frequency on the main VFO.")

        # Get the main VFO frequency and update the driver state
        radio_freq = self.radio_rig.get_freq()
        if self.driver._radio_state['set_rx_freq'] == 0:
          self.driver._radio_state['set_rx_freq'] = radio_freq
        else:
          self.driver._radio_state['shifted_rx_freq'] = radio_freq
        return {'message': "The radio's RX frequency has been set.", 'frequency': (radio_freq/1000000)}
      else:
        raise command.CommandError("No RX frequency specified for the 'rx_freq' command.")
    else:
      raise command.CommandError("The "+self.driver.id+" command handler does not have an initialized Hamlib rig.")

  def settings_set_rx_freq(self):
    """ Meta-data for the "set_rx_freq" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    command_parameters = [
      {
        "type": "number",
        "required": True,
        "title": "rx_frequency",
        "description": "The Icom 910's downlink frequency (in Mhz).",
        "integer": False
      }
    ]

    return build_metadata_dict(command_parameters, 'set_rx_freq', self.name, requires_active_session = True)

  def command_set_tx_freq(self, active_command):
    """ Sets the uplink frequency for the radio.

    @note This driver works in half-duplex mode and sets the TX frequency via a split.
    @note If someone attempts to change the TX frequency while transmitting (as determined by the 
          'doppler_update_inactive_tx_delay' configuration setting), this command will fail. If the driver doesn't have 
          any tnc_state service set, this protection will not take place.

    @throws Raises CommandError if the command fails for some reason.
    
    @param active_command  The currently executing Command.
    @return Returns a dictionary containing the command response.
    """

    # Stop the service if it is running
    if self.radio_rig is not None:
      if 'tx_freq' in active_command.parameters:
        # Make sure the TNC isn't transmitting
        if self.driver._tnc_state_service is not None:
          tnc_state = self.driver._tnc_state_service.get_state()
          tnc_last_transmitted = tnc_state['last_transmitted']
          tnc_buffer_len = tnc_state['output_buffer_size_bytes']
          if (int(time.time()) - tnc_last_transmitted) < self.driver.doppler_update_inactive_tx_delay or tnc_buffer_len > 0:
            raise command.CommandError("The pipeline's TNC has recently transmitted data or has pending data in its "+
                                       "output buffer and is not ready to have its uplink frequency changed.")

        response = self.radio_rig.set_split_freq(Hamlib.RIG_VFO_MAIN, int(active_command.parameters['tx_freq']*1000000))

        if response is not Hamlib.RIG_OK:
          raise command.CommandError("An error occured while setting the radio's split TX frequency.")

        # Get the main VFO frequency and update the driver state
        radio_freq = self.radio_rig.get_split_freq()
        if self.driver._radio_state['set_tx_freq'] == 0.0:
          self.driver._radio_state['set_tx_freq'] = radio_freq
        else:
          self.driver._radio_state['shifted_tx_freq'] = radio_freq
        return {'message': "The radio's TX frequency has been set using a split.", 'frequency': radio_freq/1000000}
      else:
        raise command.CommandError("No RX frequency specified for the 'rx_freq' command.")
    else:
      raise command.CommandError("The "+self.driver.id+" command handler does not have an initialized Hamlib rig.")

  def settings_set_tx_freq(self):
    """ Meta-data for the "set_tx_freq" command.

    @return Returns a dictionary containing meta-data about the command.
    """

    command_parameters = [
      {
        "type": "number",
        "required": True,
        "title": "tx_frequency",
        "description": "The Icom 910's uplink frequency (in Mhz).",
        "integer": False
      }
    ]

    return build_metadata_dict(command_parameters, 'set_tx_freq', self.name, requires_active_session = True)

class ICOM910Error(Exception):
  pass
class InvalidTargetPosition(ICOM910Error):
  pass