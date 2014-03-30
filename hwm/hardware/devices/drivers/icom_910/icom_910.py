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
  capable of controlling some features of the ICOM 910.

  @note This driver requires that Hamlib2 be installed and configured, including the Python bindings.
  @note This driver is not currently capable of sending or receiving data to or from the radio directly. It is designed 
        for pipelines that also contain a TNC, which will serve as the pipeline's input and output device.
  @note This driver is currently setup to operate in half-duplex mode. In half-duplex mode, only the MAIN VFO is set and
        the uplink frequency is specified via a split frequency on VFO B.
  @note The ICOM 910 driver will work with the TNC driver to make sure that it doesn't change its frequency when the 
        TNC is sending data to the radio. This will prevent the ICOM from entering an undefined state.
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
    self._command_handler.radio_rig.set_conf("rig_pathname", self.icom_device_path)
    self._command_handler.radio_rig.set_conf("retry", "5")
    self._command_handler.radio_rig.open()

    # Enable frequency split on the MAIN band
    self._command_handler.radio_rig.set_split_vfo(Hamlib.RIG_VFO_A, Hamlib.RIG_SPLIT_ON, Hamlib.RIG_VFO_B)

    if self._command_handler.radio_rig.error_status != 0:
      raise ICOM910Error("An error occured while initializing the radio for a new session, "+
                         Hamlib.rigerror(self._command_handler.radio_rig.error_status))

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
    """ Updates the radio's frequencies when new doppler shift information is available.

    This inline callback receives new target position information (including a doppler correction) from a 'tracker' 
    service. The driver will use this information to periodically (as defined by doppler_update_frequency) update 
    the uplink and downlink frequencies on the radio.

    @note Because this method uses the set_tx_freq command, it will only update the uplink frequency if the radio has
          not recently transmitted. See the set_tx_freq command method for more information.
    
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
      # Send the command to update the downlink frequency
      new_downlink_freq = target_position['doppler_multiplier'] * self._radio_state['set_rx_freq']
      command_request = {
        'command': "set_rx_freq",
        'destination': self._session_pipeline.id+"."+self.id,
        'parameters': {
          'rx_freq': new_downlink_freq/1000000
        }
      }
      command_deferred = self._command_parser.parse_command(command_request, 
                                                            user_id = self._session_pipeline.current_session.user_id)
      try:
        results = yield command_deferred
        downlink_freq_set = True
      except Exception as command_error:
        downlink_freq_set = False

      # Send the command to update the uplink frequency
      new_uplink_freq = target_position['doppler_multiplier'] * self._radio_state['set_tx_freq']
      command_request = {
        'command': "set_tx_freq",
        'destination': self._session_pipeline.id+"."+self.id,
        'parameters': {
          'tx_freq': new_uplink_freq/1000000
        }
      }
      command_deferred = self._command_parser.parse_command(command_request, 
                                                            user_id = self._session_pipeline.current_session.user_id)
      try:      
        results = yield command_deferred
        uplink_freq_set = True
      except Exception as command_error:
        uplink_freq_set = False

      # Verify the results
      if uplink_freq_set and downlink_freq_set:
        self._last_doppler_update = time.time()
        yield defer.returnValue(True)
      else:
        if not uplink_freq_set:
          logging.error("An error occured while applying a doppler correction to "+self.id+"'s TX frequency.")
        
        if not downlink_freq_set:
          logging.error("An error occured while applying a doppler correction to "+self.id+"'s RX frequency.")
        
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
          raise command.CommandError("An unrecognized mode was specified: "+new_mode)

        if self.radio_rig.error_status != 0:
          raise command.CommandError("An error occured while setting the radio's mode, "+
                                     Hamlib.rigerror(self.radio_rig.error_status))

        # Get the mode and update the driver state
        mode, width = self.radio_rig.get_mode()

        if self.radio_rig.error_status != 0:
          raise command.CommandError("An error occured while reading the radio's mode, "+
                                     Hamlib.rigerror(self.radio_rig.error_status))
        self.driver._radio_state['mode'] = Hamlib.rig_strrmode(mode)

        return {'message': "The radio's mode has been set.", 'mode': new_mode}
      else:
        raise command.CommandError("The mode was not specified in the command parameters.")
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
          ['FM']
        ]
      }
    ]

    return build_metadata_dict(command_parameters, 'set_mode', self.name, requires_active_session = True)

  def command_set_rx_freq(self, active_command):
    """ Sets the downlink frequency of the radio.

    @note This driver works in half-duplex mode with the RX frequency set on VFO A and the TX frequency set via 
          a split frequency on VFO B.

    @throws Raises CommandError if the command fails for some reason.
    
    @param active_command  The executing Command. Contains the command parameters.
    @return Returns a dictionary containing the command response.
    """

    if self.radio_rig is not None:
      if 'rx_freq' in active_command.parameters:
        # Set the rx frequency on VFO A
        self.radio_rig.set_vfo(Hamlib.RIG_VFO_A)
        response = self.radio_rig.set_freq(float(active_command.parameters['rx_freq'])*1000000)

        if self.radio_rig.error_status != 0:
          raise command.CommandError("An error occured while setting the radio's RX frequency on VFO A, "+
                                     Hamlib.rigerror(self.radio_rig.error_status))

        # Get the VFO A frequency
        radio_freq = self.radio_rig.get_freq(Hamlib.RIG_VFO_A)

        if self.radio_rig.error_status != 0:
          raise command.CommandError("Couldn't read the radio's RX frequency from VFO A on the main band, "+
                                     Hamlib.rigerror(self.radio_rig.error_status))

        if not self.driver._radio_state['set_rx_freq']:
          self.driver._radio_state['set_rx_freq'] = radio_freq
        else:
          self.driver._radio_state['shifted_rx_freq'] = radio_freq
        return {'message': "The radio's main band RX frequency has been set on VFO A.",
                'frequency': (radio_freq/1000000)}
      else:
        raise command.CommandError("The RX was not frequency specified in the command parameters.")
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
        "title": "set_rx_freq",
        "description": "The Icom 910's downlink frequency (in Mhz). Must be in 430(440) band.",
        "integer": False
      }
    ]

    return build_metadata_dict(command_parameters, 'set_rx_freq', self.name, requires_active_session = True)

  def command_set_tx_freq(self, active_command):
    """ Sets the uplink frequency for the radio.

    @note The TX frequency is set in VFO B on the main band via a split.
    @note If the user or driver attempts to change the TX frequency while transmitting (as determined by the 
          'tnc_state' service and 'doppler_update_inactive_tx_delay' configuration setting), this command will fail.
          If the driver failed to load a 'tnc_state' service from the pipeline, this protection will not take place.

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
          if (int(time.time()) - tnc_last_transmitted) < self.driver.doppler_update_inactive_tx_delay:
            raise command.CommandError("The pipeline's TNC has recently transmitted data and is not ready to have "+
                                       "its uplink frequency changed.")

        # Set the TX frequency on VFO B of the main band
        self.radio_rig.set_vfo(Hamlib.RIG_VFO_B)
        self.radio_rig.set_freq(float(active_command.parameters['tx_freq'])*1000000)      

        if self.radio_rig.error_status != 0:
          raise command.CommandError("An error occured while setting the radio's TX frequency on VFO B, "+
                                     Hamlib.rigerror(self.radio_rig.error_status))

        # Get the main VFO frequency and switch back to VFO A (so that transmit will be on VFO B)
        radio_freq = self.radio_rig.get_freq(Hamlib.RIG_VFO_B)
        self.radio_rig.set_vfo(Hamlib.RIG_VFO_A)

        if self.radio_rig.error_status != 0:
          raise command.CommandError("Couldn't read the radio's TX frequency from VFO B on the main band, "+
                                     Hamlib.rigerror(self.radio_rig.error_status))

        if not self.driver._radio_state['set_tx_freq']:
          self.driver._radio_state['set_tx_freq'] = radio_freq
        else:
          self.driver._radio_state['shifted_tx_freq'] = radio_freq
        return {'message': "The radio's main band TX frequency has been set VFO B.", 'frequency': radio_freq/1000000}
      else:
        raise command.CommandError("The TX frequency was not specified in the command parameters.")
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
        "title": "set_tx_freq",
        "description": "The Icom 910's uplink frequency (in Mhz). Must be in the 144 band.",
        "integer": False
      }
    ]

    return build_metadata_dict(command_parameters, 'set_tx_freq', self.name, requires_active_session = True)

class ICOM910Error(Exception):
  pass
class InvalidTargetPosition(ICOM910Error):
  pass
