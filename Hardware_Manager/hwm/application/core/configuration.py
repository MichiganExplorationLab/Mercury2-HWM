""" @package hwm.application.core.configuration
Contains a class to store the hardware manager configuration.

This module contains a class that provides methods for storing, modifying, and retrieving application configuration and
shared state for the hardware manager. Access it by importing the Configuration variable.
"""

# Load the required libraries
import logging
import yaml

class Config:
  """Provides access to the hardware manager application configuration.
  
  This class stores and provides access to the configuration and shared state used by the hardware manager such as the 
  configuration, reservation schedules, and pipeline configuration. In addition, it allows users to store their own 
  configuration options as needed. To use this class import this module (configuration) and assign a local variable to 
  'Configuration' (makes code easier to test).
  """
  
  def __init__(self):
    """Initializes the dictionaries and other member variables used to hold the configuration.
    
    @note Only user_options can be modified during program execution (using the setter/getter). This keeps prevents
          configuration options from getting altered/deleted.
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
    """Loads and parses the specified configuration file.
    
    Reads in all configuration settings from the specified YAML file and stores them in the 'options' dictionary.
    
    @throws IOError    Thrown if the specified file can't be loaded.
    @throws Exception  Thrown if the specified file can't be parsed by the YAML parser.
    
    @note All configuration files are in YAML format.
    @note All configurations are assumed to be required (i.e. this throws an exception if the file can't be loaded)
    @note If a file is loaded that contains a previously defined protected option, the previous value will be overridden by the new value.
    @see http://en.wikipedia.org/wiki/YAML
    
    @param configuration_file  The YAML configuration file to load. This is an absolute path.
    """
    
    # Attempt to load the specified configuration file
    config_stream = open(configuration_file, 'r')
    
    # Attempt to parse the file
    try:
      config = yaml.load(config_stream)
    except:
      raise Exception("Error parsing the configuration file: '"+configuration_file+"'")
    
    # Merge the dictionaries
    self.options = dict(self.options.items() + config.items())
    
    # Log & announce the configuration file load 
    if self.verbose_startup:
      print "- Read in configuration file: '"+configuration_file+"'."
    logging.info("Configuration: Read configuration file: '"+configuration_file+"'.")
  
  def check_required_configuration(self):
    """Verifies that the required configuration elements have been set.
    
    This method verifies that the required configuration elements have properly been set. These elements were probably
    loaded from a YAML configuration file via read_configuration().
    
    @note If a configuration option is missing, an exception will be thrown detailing the error. This exception will be
          caught by the global exception handler.
    """
    
    # Set some default error messages
    error_missing_option = "Required configuration option not set: '{}'. Please add it to a configuration file."
    
    # Verify that the required ground station parameters have been set
    if 'station-name' not in self.options:
      raise Exception(error_missing_option.format('station-name'))
    if 'station-longitude' not in self.options:
      raise Exception(error_missing_option.format('station-longitude'))
    if 'station-latitude' not in self.options:
      raise Exception(error_missing_option.format('station-latitude'))
    if 'station-altitude' not in self.options:
      raise Exception(error_missing_option.format('station-altitude'))
    
    # Log and announce
    if self.verbose_startup:
      print "- Validated required configuration options."
    logging.info("Configuration: Successfully validated required configuration options.")
  
  def set(self, option_key, option_value):
    """Sets the indicated configuration option to the provided value.
    
    @throws OptionProtected Thrown if the user tries to modify or set a protected run-time key.
    
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
    logging.info("Configuration: Set the value of a configuration option ("+option_key+").")
    
    return True
  
  def get(self, option_key):
    """Retrieves the specified configuration option.
    
    This method returns the value of the specified option from either the user defined options or pre-set runtime 
    options.
    
    @throws OptionNotFound Thrown if the specified option can't be located in either configuration value dictionary.
    
    @param option_key  The key of the option to query for.
    @return Returns the value of the specified option if found.
    """
    
    # Check if the option was pre-set
    if option_key in self.options:
      logging.info("Configuration: Read a configuration option ("+option_key+").")
      return self.options[option_key]
    
    # Check if the option is a user option
    if option_key in self.user_options: 
      logging.info("Configuration: Read a user configuration option ("+option_key+").")
      return self.user_options[option_key]
    
    # Option not found
    raise OptionNotFound("The specified configuration option ("+option_key+") could not be found.")
  
  def delete(self, option_key):
    """Removes the specified configuration option from the user options dictionary.
    
    @throws OptionProtected Thrown if the user tries to delete a protected run-time option.
    @throws OptionNotFound Thrown if the option can't be located.
    
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
      logging.info("Configuration: Deleted a user configuration option ("+option_key+").")
      return True
    
    # Option not found
    raise OptionNotFound("The specified configuration option ("+option_key+") could not be found.")

# Define configuration exceptions
class OptionProtected(Exception):
  pass
class OptionNotFound(Exception):
  pass

## Stores a 'singleton' instance of the Config object. Assign local references to this instance to access the 
# configuration.
Configuration = Config()
