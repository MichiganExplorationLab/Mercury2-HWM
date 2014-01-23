""" @package hwm.core.configuration
Contains a class to store the hardware manager configuration.

This module contains a class that provides methods for storing, modifying, and retrieving application configuration and
some other shared state for the hardware manager. Access it by importing the Configuration variable (defined at the end
of the module).
"""

# Load the required libraries
import logging, yaml, jsonschema

class Config:
  """ Provides access to the hardware manager application configuration.
  
  This class stores and provides access to the configuration and various shared state used by the hardware manager. In 
  addition, it allows users to store their own configuration options as needed. To use this class, import this module 
  (configuration) and assign a local variable to 'Configuration' (makes code easier to test).
  
  @note Although this class does store raw pipeline and hardware configuration settings (defined in the configuration 
        files), all interactions with the pipelines and hardware occur in the PipelineManager and DeviceManager classes,
        respectively.
  @note Only user_options can be modified during program execution (using the setter/getter). This prevents
        configuration options specified in a file from getting altered/deleted.
  """
  
  def __init__(self):
    """ Initializes the Config class with some initial static configuration.
    """
    
    # Basic configuration options
    self.version = "1.0dev"
    self.verbose_startup = True
    self._set_hwm_directories()
    
    # This dictionary stores all pre-set configuration options (read from files)
    self.options = {}
    
    # This dictionary stores all user defined configuration options (set during execution)
    self.user_options = {}
  
  def read_configuration(self, configuration_file):
    """ Loads and parses the specified configuration file.
    
    Reads in all configuration settings from the specified YAML file and stores them in the 'options' dictionary.
    
    @throws IOError              Thrown if the specified file can't be loaded.
    @throws ConfigFileMalformed  Thrown if the specified file can't be parsed by the YAML parser.
    
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
      raise ConfigFileMalformed("Error parsing the configuration file: '"+configuration_file+"'")
    
    # Merge the dictionaries
    self.options = dict(self.options.items() + config.items())
    
    # Log & announce the configuration file load 
    logging.info("Loaded configuration file: '"+configuration_file+"'.")
  
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

  def validate_configuration(self):
    """ Verifies that the loaded configuration conforms to the schema.

    This method compares the currently loaded configuration settings against the defined configuration schema. This 
    ensures that all required options have been set and that they meet formatting requirements.
    
    @note All configuration files that contain methods defined in this schema must be loaded before this method is
          called.
    @note In the schema, all required options that have an associated default value must have "required" set to False,
          otherwise the schema validation will fail when it should just use the default value.

    @throws May throw ConfigInvalid if the loaded configuration set does not conform to the schema.
    """

    # Define the configuration schema
    configuration_schema = {
      "type": "object",
      "$schema": "http://json-schema.org/draft-03/schema",
      "additionalProperties": True,
      "properties": {
        "station-name": {
          "type": "string",
          "required": True,
          "maxLength": 100
        },
        "station-longitude": {
          "type": "number",
          "required": True,
          "minimum": -180,
          "maximum": 180
        },
        "station-latitude": {
          "type": "number",
          "required": True,
          "minimum": -90,
          "maximum": 90
        },
        "station-altitude": {
          "type": "number",
          "required": True
        },
        "offline-mode": {
          "type": "boolean",
          "default": False
        },
        "command-port": {
          "type": "integer",
          "minimum": 1,
          "default": 45500
        },
        "pipeline-data-port": {
          "type": "integer",
          "minimum": 1,
          "default": 45501
        },
        "pipeline-telemetry-port": {
          "type": "integer",
          "minimum": 1,
          "default": 45502
        },
        "mercury2-ui-location": {
          "type": "string",
          "required": True
        },
        "tls-private-key-location": {
          "type": "string",
          "default": self.config_directory + "ssl/mercury2_hwm-key.pem"
        },
        "tls-public-cert-location": {
          "type": "string",
          "default": self.config_directory + "ssl/mercury2_hwm-cert.pem"
        },
        "tls-ca-cert-location": {
          "type": "string",
          "default": self.config_directory + "ssl/ca-cert.pem"
        },
        "schedule-update-period": {
          "type": "integer",
          "default": 30
        },
        "schedule-update-timeout": {
          "type": "integer",
          "default": 10
        },
        "schedule-location-local": {
          "type": "string",
          "default": self.data_directory + "schedules/offline_schedule.json"
        },
        "schedule-location-network": {
          "type": "string",
          "default": "test_schedule.json"
        },
        "permissions-update-period": {
          "type": "integer",
          "minimum": 1,
          "default": 60
        },
        "permissions-update-timeout": {
          "type": "integer",
          "minimum": 1,
          "maximum": 60,
          "default": 10
        },
        "permissions-location-local": {
          "type": "string",
          "default": self.data_directory + "permissions/offline_permissions.json"
        },
        "permissions-location-network": {
          "type": "string",
          "default": "test_permissions.json"
        }
      }
    }

    # Validate the loaded configuration against the schema
    configuration_validator = jsonschema.Draft3Validator(configuration_schema)
    try:
      configuration_validator.validate(self.options)

      logging.info("Validated the main configuration file. The pipeline and device configuration files will be "+
                   "validated later.")
    except jsonschema.ValidationError as config_error:
      # The loaded configuration did not conform to the schema
      logging.error("The core configuration file did not conform to the configuration schema: "+str(config_error))
      raise ConfigInvalid("The core configuration file was invalid (did not conform to the configuration schema): "+
                          str(config_error))

    # Copy over the required default values
    self._process_defaults(configuration_schema)

  def _process_defaults(self, configuration_schema):
    """ Copies the default values from the configuration schema to the options dictionary.

    This method copies the default values for unspecified options from the defined configuration schema to the options
    dictionary.

    @note The JSON schema validation class does not currently provide this functionality, so it must be done using this 
          method.

    @see https://github.com/Julian/jsonschema/issues/4

    @param configuration_schema  A dictionary containing the configuration schema to use when copying default values.
    """

    for option_name, option_schema in configuration_schema['properties'].iteritems():
      if option_name not in self.options and "default" in option_schema:
        self.options.update({option_name: option_schema['default']})

  def _set_hwm_directories(self):
    """ Sets the location of the Mercury2 HWM configuration and data directories.
    
    This method sets the locations of the various Mercury2 configuration and data directories, which contain the HWM 
    configuration files, logs, and telemetry dumps, among other things.
    """

    application_folder = "Mercury2-HWM"

    # Set the directory locations
    self.config_directory = "/etc/"+application_folder+"/"
    self.data_directory = "/var/local/"+application_folder+"/"
    self.log_directory = "/var/log/"+application_folder+"/"

# Define configuration exceptions
class ConfigFileMalformed(Exception):
  pass
class ConfigInvalid(Exception):
  pass
class OptionProtected(Exception):
  pass
class OptionNotFound(Exception):
  pass

## Stores a 'singleton' instance of the Config object. Assign local references to this instance to access the 
# configuration. Because this is a top level module variable, it will only be initialized the first time this module
# is included.
Configuration = Config()
