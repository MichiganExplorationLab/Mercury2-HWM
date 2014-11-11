""" @package hwm.network.state.state 
This module contains the state reporter, which is used to report the ground station's state to the UI via its API.
"""

from twisted.internet import threads, defer, logging
from hwm.core.configuration import Configuration

class StateReporter:
  """ Records and reports various state elements back to the User Interface. 

  The StateReporter class provides methods for recording various substation state attributes, which it will periodically
  send to the User Interface via its REST API.
  """

  def __init__(self, state_endpoint, update_frequency):
    """ Sets up the state reporter.

    @param state_endpoint    The API endpoint that state updates should be sent to. This is most likely specified in the 
                             substation's main configuration file.
    @param update_frequency  How often the substation's state should be sent to the API in seconds. Note that this 
                             doesn't apply to the static configuration, which is sent just once on start and requires a
                             restart to resend.
    """

    # Set the local configuration object reference
    self.config = Configuration

    self.state_endpoint = state_endpoint
    self.update_frequency = update_frequency
    self.offline_mode = self.config.get('offline-mode')

  def send_substation_configuration(self, config, pipeline_config, device_config, command_config):
    """ Sends the substation's static configuration to the User Interface via the API. 

    This method sends the substation's static configuration to the UI, typically on start. The information that is 
    included in this update includes: the substation configuration, pipeline configuration, device configuration, and
    command meta-data.

    @param config           A dictionary containing the substation's general substation configuration. 
    @param pipeline_config  A dictionary containing the substation's pipeline configuration.
    @param device_config    A dictionary containing the substation's device configuration.
    @param command_config   A dictionary containing command meta-data for both system and device commands.

    @return Returns a Deferred for the POST request.
    """

    # Send the configuration settings to the API
    substation_configuration = {
      'configuration': {
        'substation': config,
        'pipelines': pipeline_config,
        'devices': device_config,
        'commands': command_config
      }
    }
    configuration_update = threads.deferToThread(self._POST_to_api, substation_configuration)
    configuration_update.addErrback(self._api_error)

    logging.update("Sending substation configuration to the user interface API.")

    return configuration_update

  def send_current_state(self):
    """ Sends the current state of the ground station to the UI's API.

    This method is responsible for sending short-lived substation state to the user interface such as active sessions
    and alerts. It will be called periodically as specified by the update frequency.
    """

    pass

  def record_alert(self):

    pass 

  def start_state_updates(self):

    pass

  def _api_error(self, failure):
    """ Handles possible errors when sending data to the API.

    @param failure  A Failure instance containing information about the error.  
    """

    logging.error("An error occured while sending substation state to the user interface: "+str(failure.value))

  def _POST_to_api(self, data):
    """ POSTs the specified data to the user interface and returns the response. 

    This method makes a blocking HTTP request to the substation "state" API endpoint. The data should consist of a
    dictionary indexed by the type of data, e.g. "configuration" or "state".  

    @throw May raise an exception if there is an error contacting the API or parsing the response.

    @param data  A dictionary containing the data to be POSTed to the API.

    @return Returns the API response.
    """
    
    # POST the data to the API
    state_request = urllib2.Request(self.state_endpoint)
    state_opener = urllib2.build_opener()
    state_opener.addheaders = [('Authorization', 'Token: '+self.config.get('mercury2-api-token'))]
    response = state_opener.open(state_request, None, self.config.get('state-update-timeout'))
    
    # Parse the response
    api_response = json.load(response)

    return api_response



