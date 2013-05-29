""" @package hwm.core.configuration
Contains a class to store the hardware manager configuration.

This module contains a class that provides methods for storing, modifying, and retrieving application configuration and
some other shared state for the hardware manager. Access it by importing the Configuration variable (defined at the end
of the module).
"""

# Load the required libraries
import logging
import yaml

class Config:
  """ Provides access to the hardware manager application configuration.
  
  This class stores and provides access to the configuration and various shared state used by the hardware manager. In 
  addition, it allows users to store their own configuration options as needed. To use this class, import this module 
  (configuration) and assign a local variable to 'Configuration' (makes code easier to test).
  
  @note Although this class does store raw pipeline and hardware configuration settings (defined in the configuration 
        files), all interactions with the pipelines and hardware occur in the PipelineManager and DeviceManager classes,
        respectively.
  """
  
  def __init__(self):
    """ Initializes the Config class.
    
    @note Only user_options can be modified during program execution (using the setter/getter). This prevents
          configuration options specified in a file from getting altered/deleted.
    """
    
    # Program metadata
    self.version = "1.0dev"
    self.verbose_startup = True
    self.data_directory = '/var/local/Mercury2HWM'
    
    # This dictionary stores all pre-set configuration options (read from files)
    self.options = {}
    
    # This dictionary stores all user defined configuration options (set during execution)
    self.user_options = {}
  
  def read_configuration(self, configuration_file):
    """ Loads and parses the specified configuration file.
    
    Reads in all configuration settings from the specified YAML file and stores them in the 'options' dictionary.
    
    @throws IOError            Thrown if the specified file can't be loaded.
    @throws ConfigFileInvalid  Thrown if the specified file can't be parsed by the YAML parser.
    
    @note All configuration files are in YAML format.
    @note All configuration files are assumed to be required (i.e. this throws an exception if the file can't be 
          loaded).
    @note If a file is loaded that contains a previously defined protected option, the previous value will be overridden
          by the new value.
    @see http://en.wikipedia.org/wiki/YAML
    
    @param configuration_file  The YAML configuration file to load. This is an absolute path.
    """
    
    # Attempt to load the specified configuration file
    config_stream = open(configuration_file, 'r')
    
    # Attempt to parse the file
    try:
      config = yaml.load(config_stream)
    except:
      raise ConfigFileInvalid("Error parsing the configuration file: '"+configuration_file+"'")
    
    # Merge the dictionaries
    self.options = dict(self.options.items() + config.items())
    
    # Log & announce the configuration file load 
    if self.verbose_startup:
      print "- Read in configuration file: '"+configuration_file+"'."
    
    logging.info("Configuration: Read configuration file: '"+configuration_file+"'.")
  
  def process_configuration(self):
    """ Loads default values for unspecified configuration options and verifies that the required configuration elements
    have been set.
    
    This method first sets a default value for any unspecified option with an registered default value. It then verifies
    that the required configuration elements have all been set. These elements were probably loaded from a YAML 
    configuration file via read_configuration().
    
    @throw May pass on RequiredOptionNotFound exceptions if a required option can't be located in the loaded 
           configuration.
    
    @note Only configuration options loaded before this method is called will be processed. It should be called after
          all of the main configuration has been loaded (otherwise the required options check may fail).
    """
    
    # Set the default configuration options
    self._set_default_configuration()
    
    # Validate that the required options have been set
    self._check_required_configuration()
  
  def set(self, option_key, option_value):
    """ Sets the indicated configuration option to the provided value.
    
    @throws OptionProtected thrown if the user tries to modify or set a protected run-time option.
    
    @param option_key    The key (name) of the option to set.
    @param option_value  The value to assign to the indicated option.
    @return Returns True if the option was successfully set.
    """
    
    # Make sure the key isn't protected (i.e. that it wasn't loaded from a configuration file)
    if option_key in self.options:
      raise OptionProtected("The option you tried to set ("+option_key+") is protected and can't be set or modified.")
    
    # Set the option value
    self.user_options[option_key] = option_value
    
    # Log the event
    logging.info("Set the value of a configuration option ("+option_key+").")
    
    return True
  
  def get(self, option_key):
    """ Retrieves the specified configuration option.
    
    This method returns the value of the specified option whether it is a user defined option or an option loaded from 
    a YAML configuration file.
    
    @throws OptionNotFound Thrown if the specified option can't be located.
    
    @param option_key  The key of the option to query for.
    @return Returns the value of the specified option if it exists.
    """
    
    # Check if the option was pre-set
    if option_key in self.options:
      return self.options[option_key]
    
    # Check if the option is a user option
    if option_key in self.user_options: 
      return self.user_options[option_key]
    
    # Option not found
    raise OptionNotFound("The specified configuration option ("+option_key+") could not be found.")
  
  def delete(self, option_key):
    """ Removes the specified configuration option from the user options dictionary.
    
    @note Only user defined configuration options can be removed.
    
    @throws OptionProtected thrown if the user tries to delete a protected option (originally defined in a YAML 
            configuration file).
    @throws OptionNotFound thrown if the requested option can't be located.
    
    @param option_key  The key of the option to remove.
    @return Returns True if the option was successfully deleted.
    """
    
    # Check if the option was pre-set (protected)
    if option_key in self.options:
      raise OptionProtected("The option you tried to set ("+option_key+") is protected and can't be deleted.")
    
    # Check if the option is a valid user option
    if option_key in self.user_options:
      # Delete the option
      del self.user_options[option_key]
      logging.info("Deleted a user configuration option ("+option_key+").")
      return True
    
    # Option not found
    raise OptionNotFound("The specified configuration option ("+option_key+") could not be found.")
  
  def _set_default_configuration(self):
    """ Sets the default values for configuration elements that have not been set.
    
    @note If a configuration option with a default value has been set (most likely from a file by read_configuration), 
          that value will be used instead of the default.
    @note The default values for network or local locations are prefixed with the user interface base URL and the base 
          application data directory, respectively. This allows the station admin to set these to whatever they'd like 
          (e.g. somewhere not in self.data_directory).
    """
    
    # Set the UI location for the default location parameters. If this isn't set, then just use a blank string and 
    # _check_required_configuration will take care of it.
    if 'mercury2-ui-location' in self.options:
      ui_location = self.options['mercury2-ui-location']
    else:
      ui_location = ''
    
    # Specify the option defaults
    default_options = {
      'offline-mode': False,
      'schedule-update-period': 60, # seconds
      'schedule-update-timeout': 15, # seconds
      'schedule-location-local': self.data_directory + '/schedules/offline_schedule.yml',
      'schedule-location-network': ui_location + '/test_schedule.json',
      'permissions-update-period': 300, # seconds 
      'permissions-update-timeout': 15, # seconds
      'permissions-location-local': self.data_directory + '/permissions/offline_permissions.yml',
      'permissions-location-network': ui_location + '/test_permissions.json',
      'ssl-private-key-location': self.data_directory + '/ssl/mercury2_hwm-key.pem',
      'ssl-public-cert-location': self.data_directory + '/ssl/mercury2_hwm-cert.pem',
      'ssl-ca-cert-location': self.data_directory + '/ssl/ca-cert.pem',
      'network-command-port': 8080
    }
    
    # Set the defaults
    for default_option in default_options:
      if default_option not in self.options:
        self.options[default_option] = default_options[default_option]
    
    # Log and announce
    if self.verbose_startup:
      print "- Set default configuration options."
    logging.info("Configuration: Successfully set default configuration options.")
  
  def _check_required_configuration(self):
    """ Verifies that the required configuration elements have been set.
    
    This method verifies that the required configuration elements have properly been set.
    
    @throw Throws RequiredOptionNotFound if a required option can't be located in the loaded configuration. 
    
    @note Network locations must start with http (either http or https).
    """
    
    # Set some default error messages
    missing_option_error = "Required configuration option not set: '{}'. Please specify it in a configuration file."
    
    # List the required configuration options
    required_options = [
      'station-name', 'station-longitude', 'station-latitude', 'station-altitude', # Station parameters
      'offline-mode', 'network-command-port', 'mercury2-ui-location', # General networking
      'ssl-private-key-location', 'ssl-public-cert-location', 'ssl-ca-cert-location', # Security
      'schedule-update-period', 'schedule-update-timeout', 'schedule-location-local', 'schedule-location-network', # Schedule
      'permissions-update-period', 'permissions-update-timeout', 'permissions-location-local', 'permissions-location-network', # Permissions
      'devices', 'pipelines' # Devices & Pipelines
    ]
    
    # Validate the options
    for required_option in required_options:
      if required_option not in self.options:
        raise RequiredOptionNotFound(missing_option_error.format(required_option))
    
    # Log and announce
    if self.verbose_startup:
      print "- Validated required configuration options."
    logging.info("Configuration: Successfully validated required configuration options.")

# Define configuration exceptions
class ConfigFileInvalid(Exception):
  pass
class OptionProtected(Exception):
  pass
class RequiredOptionNotFound(Exception):
  pass
class OptionNotFound(Exception):
  pass

## Stores a 'singleton' instance of the Config object. Assign local references to this instance to access the 
# configuration. Because this is a top level module variable, it will only be initialized the first time this module
# is included.
Configuration = Config()
