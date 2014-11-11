""" @package hwm.hardware.devices.manager
Manages access to hardware devices.

This class is used to manage access to configured hardware devices. It is responsible for initializing the drivers for
each hardware device and provides an interface that the rest of the application uses to locate devices.
"""

# Import required modules
import logging, jsonschema
from hwm.core import configuration
from hwm.hardware.devices.drivers import driver

class DeviceManager:
  """ Manages access to configured hardware devices.
  
  This class is responsible for providing access to the hardware device drivers currently configured at the ground
  station. Like the other "manager" classes, there will only be a single instance of this class created early on. When 
  initialized, the device manager initializes the appropriate drivers for the hardware devices specified in the 
  configuration.
  
  @note All device usage locking is done by the device driver. See the driver base class for more.
  """
  
  def __init__(self, command_parser):
    """ Initializes the device manager and all configured devices.
    
    This constructor initializes the device manager and creates the appropriate driver class instances for all
    configured hardware devices.

    @param command_parser  A reference to the active CommandParser instance.
    
    @note This class relies on configuration loaded into the configuration manager during the startup process.
          Therefore, if this class is initialized before the appropriate configuration files have been read, an 
          exception will be generated.
    @throw This constructor may pass exceptions raised during the device driver initialization process
           (see _initialize_devices).
    """
    
    # Set the local configuration reference
    self.config = configuration.Configuration
    
    # Initialize class variables
    self.devices = {}          # Stores references to instances of the physical device drivers
    self.virtual_devices = {}  # Stores references to the virtual device driver classes (initialized on the fly)
    self._command_parser = command_parser
    self._state_reporter = state_reporter
    
    # Initialize 
    self._initialize_devices()
  
  def get_device_driver(self, device_id):
    """ Loads and returns the driver for the specified device.
    
    This method returns an instance of the device driver class for the specified device. If the requested device is a 
    physical device a reference to a previously initialized driver will be returned. If the requested device is a 
    virtual device a new instance will be constructed and returned.

    @note This method is typically called by pipelines during initialization when loading their devices. Virtual device 
          driver instances are created on the fly because, unlike physical device drivers, they are typically tied to a 
          specific pipeline with each pipeline having its own instance.
    
    @throw Throws DeviceNotFound if the specified device can't be located.
    
    @param device_id  The ID of the device associated with the returned driver.
    @return Returns a reference to the driver class for the specified device.
    """
    
    if device_id not in self.devices and device_id not in self.virtual_devices:
      logging.error("The '"+device_id+"' device hasn't been loaded into the device manager.")
      raise DeviceNotFound("The '"+device_id+"' device hasn't been loaded into the device manager.")
    
    # Check if the device is a virtual device
    if device_id in self.virtual_devices:
      # Create and return a new instance of the virtual device driver
      return self.virtual_devices[device_id]['driver_class'](self.virtual_devices[device_id]['config'], 
                                                             self._command_parser)
    else:
      # Return the existing physical device driver
      return self.devices[device_id]
  
  def _initialize_devices(self):
    """ Initializes the drivers for each device.
    
    This method stores references to device driver instances or classes as defined by the device configuration. If a
    device is a physical device, then its driver will be initialized and stored. However, if the device is a virtual
    device then a reference to its class will be stored instead (so it can be initialized on the fly later).
    
    @note Device drivers should be named so that the lower case version of the driver name (as specified in devices.yml)
          refers to the package and module in hwm.devices.drivers. Underscores are allowed to improve readability. For 
          example, the driver "Test_Driver" refers to the "Test_Driver" class in the "test_driver" module in the
          "test_driver" package.
    
    @throw Throws DevicesAlreadyInitialized if drivers have already been loaded into the device manager.
    @throw Throws DeviceConfigInvalid in the event that device configuration specified in self.config is invalid (wrong
           format). This may be passed on from _validate_devices().
    @throw Throws DriverNotFound in the event that a driver class can't be located.
    @throw Throws DriverInitError in the event that a driver class can't be initialized (i.e. its constructor throws an
           exception).
    """
    
    # Verify that no drivers have been initialized
    if len(self.devices) > 0:
      logging.error("The DeviceManager has already initialized the station drivers.")
      raise DevicesAlreadyInitialized
    
    # Load the device configuration
    try:
      device_settings = self.config.get('devices')
    except configuration.OptionNotFound:
      logging.error("Device configuration missing, the device manager couldn't be initialized.")
      raise DeviceConfigInvalid("Device configuration not found in any loaded configuration files.")
    
    # Validate the device configuration
    self._validate_devices(device_settings)
    
    # Loop through the device configuration and initialize the driver for each device
    for device_config in device_settings:
      # Check for duplicates
      if (device_config['id'] in self.devices or device_config['id'] in self.virtual_devices):
        logging.error("Duplicate devices were found in the device configuration.")
        raise DeviceConfigInvalid("Could not initialize the '"+device_config['id']+"' device because it is a "+
              "duplicate of a previously initialized device.")
      
      # Try to import the device's driver package
      package_name = device_config['driver'].lower()
      try:
        _drivers = __import__('hwm.hardware.devices.drivers.'+package_name, globals(), locals(), [package_name], -1)
        driver_module = getattr(_drivers, package_name)
      except ImportError:
        logging.error("The driver package or module '"+package_name+"' could not be loaded for device '"+
                      device_config['id']+"'.")
        raise DriverNotFound("The driver package or module for the device '"+device_config['id']+"' could not be "+
                             "located.")
      
      # Attempt to load the driver
      if not hasattr(driver_module, device_config['driver']):
        logging.error("The driver class '"+device_config['driver']+"' could not be located in the '"+
                      str(driver_module)+"' module.")
        raise DriverNotFound("The driver class '"+device_config['driver']+"' could not be located for the '"+
                             device_config['id']+"' device.")
      device_driver_class = getattr(driver_module, device_config['driver'])

      # Check if the driver is a virtual driver
      if issubclass(device_driver_class, driver.VirtualDriver):
        # Virtual driver, just store a reference to the class and its configuration for later
        self.virtual_devices[device_config['id']] = {'driver_class':device_driver_class, 'config': device_config}
      else:
        # Physical driver, attempt to initialize
        try:
          self.devices[device_config['id']] = device_driver_class(device_config, self._command_parser)
        except Exception, driver_exception:
          logging.error("An error occured initializing the driver for device '"+device_config['id']+"': "+
                        type(driver_exception).__name__+" "+str(driver_exception))
          raise DriverInitError("Failed to initialize the driver for the '"+device_config['id']+"' device. "+
                                "Received error message: "+type(driver_exception).__name__+" "+str(driver_exception))
  
  def _validate_devices(self, device_configuration):
    """ Validates the provided device configuration.
    
    This method verifies that the provided device configuration conforms to the defined schema.
    
    @note This method doesn't validate any of the device settings. It is up to the device drivers to do this during
          initialization.
    
    @throw Throws DeviceConfigInvalid in the event that the device configuration is invalid.
    
    @param device_configuration  An array containing the available device configuration.
    """
    
    # Define a schema that species the format of the YAML pipeline configuration. Note that, because YAML is a superset
    # of JSON, the JSON draft 3 schema validator can validate most simple YAML files.
    device_schema = {
      "type": "array",
      "$schema": "http://json-schema.org/draft-03/schema",
      "required": True,
      "minItems": 1,
      "additionalItems": False,
      "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
          "id": {
            "type": "string",
            "required": True
          },
          "description": {
            "type": "string",
            "required": False
          },
          "driver": {
            "type": "string",
            "required": True
          },
          "allow_concurrent_use": {
            "type": "boolean",
            "required": False
          },
          "settings": {
            "type": "object",
            "required": False,
            "additionalProperties": True
          }
        }
      }
    }
    
    # Validate the JSON schema
    config_validator = jsonschema.Draft3Validator(device_schema)
    try:
      config_validator.validate(device_configuration)
    except jsonschema.ValidationError as driver_validation_error:
      # Invalid device configuration
      logging.error("Failed to initialize the device manager because the device configuration was invalid: "+
                    str(driver_validation_error))
      raise DeviceConfigInvalid("Failed to initialize the device manager because the device configuration was "+
                                "invalid: "+str(driver_validation_error))
  
# Define schedule related exceptions
class DeviceConfigInvalid(Exception):
  pass
class DriverNotFound(Exception):
  pass
class DriverInitError(Exception):
  pass
class DevicesAlreadyInitialized(Exception):
  pass
class DeviceNotFound(Exception):
  pass
