""" @package hwm.hardware.devices.manager
Manages access to hardware devices.

This class is used to manage access to configured hardware devices. It is responsible for initializing the drivers for
each hardware device and provides an interface that the rest of the application uses to locate devices.
"""

# Import required modules
import logging
from hwm.core import configuration

class DeviceManager:
  """ Manages access to configured hardware devices.
  
  This class is responsible for providing access to the hardware device drivers currently configured at the ground
  station. Like the other "manager" classes, there will only be a single instance of this class created early on. When 
  initialized, the device manager initializes the appropriate drivers for the hardware devices specified in the 
  configuration.
  
  @note Like the pipeline manager, all device usage locking is done by the device driver. See the driver base class for
        more.
  """
  
  def __init__(self):
    """ Initializes the device manager and all configured devices.
    
    This constructor initializes the device manager and creates the appropriate driver class instances for all
    configured hardware devices. 
    
    @throw This constructor may pass exceptions raised during the device driver initialization process
           (see _initialize_devices).
    """
    
    # Set the local configuration reference
    self.config = configuration.Configuration
    
    # Initialize class variables
    self.devices = {}
    
    # Initialize 
    self._initialize_devices()
  
  def get_device_driver(self, device_id):
    """ Loads and returns the driver for the specified device.
    
    This method returns a reference to the driver class associated with the 'device_id' device.
    
    @throw Throws DeviceNotFound if the specified device can't be located.
    
    @param device_id  The ID of the device associated with the returned driver.
    @return Returns a reference to the driver class for the specified device.
    """
    
    if device_id not in self.devices:
      logging.error("The '"+device_id+"' device hasn't been loaded into the device manager.")
      raise DeviceNotFound("The '"+device_id+"' device hasn't been loaded into the device manager.")
    
    return self.devices[device_id]
  
  def _initialize_devices(self):
    """ Initializes the drivers for each device.
    
    This method initializes the drivers for every available device specified in the device configuration.
    
    @note Device drivers should be named so that the lower case version of the driver name (as specified in devices.yml)
          refers to the package and module in hwm.devices.drivers. Underscores are allowed to improve readability. For 
          example, the driver "Test_Driver" refers to the "Test_Driver" class in the "test_driver" module in the
          "test_driver" package.
    
    @throw Throws DevicesAlreadyInitialized if drivers have already been loaded into the device manager.
    @throw Throws InvalidDeviceConfig in the event that device configuration specified in self.config is invalid (wrong
           format).
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
      raise InvalidDeviceConfig("Device configuration not found in any loaded configuration files.")
    
    # Make sure at least one device has been defined
    if len(device_settings) == 0:
      logging.error("Can't initialize the device manager because no devices have been configured.")
      raise InvalidDeviceConfig("No devices configured (none found in any loaded configuration files).")
    
    # Loop through the device configuration and initialize the driver for each device
    for device_config in device_settings:
      # Perform initial validations on the device configuration (driver class will perform more if needed)
      if ('device_id' not in device_config) or ('driver' not in device_config):
        logging.error("A device's configuration was invalid (missing required fields).")
        raise InvalidDeviceConfig("A device's configuration was invalid (missing required fields).")
      if (device_config['device_id'] in self.devices):
        logging.error("Duplicate devices were found in the device configuration.")
        raise InvalidDeviceConfig("Could not initialize the '"+device_config['device_id']+"' device because it is a "+
              "duplicate of a previously initialized device.")
      
      # Try to import the device's driver package
      package_name = device_config['driver'].lower()
      try:
        _drivers = __import__('hwm.hardware.devices.drivers.'+package_name, globals(), locals(), [package_name], -1)
        driver_module = getattr(_drivers, package_name)
      except ImportError:
        logging.error("The package or module '"+package_name+"' could not be loaded for device '"+
                      device_config['device_id']+"'.")
        raise DriverNotFound("The package or module for the device '"+device_config['device_id']+"' could not be "+
                             "located.")
      
      # Attempt to initialize the driver
      if not hasattr(driver_module, device_config['driver']):
        logging.error("The driver class '"+device_config['driver']+"' could not be located in the '"+
                      driver_module+"' module.")
        raise DriverNotFound("The driver class '"+device_config['driver']+"' could not be located for the '"+
                             device_config['device_id']+"' device.")
      
      device_driver_class = getattr(driver_module, device_config['driver'])
      try:
        self.devices[device_config['device_id']] = device_driver_class(device_config)
      except Exception, driver_exception:
        logging.error("An error occured initializing the driver for device '"+device_config['device_id']+"': "+
                      str(driver_exception))
        raise DriverInitError("Failed to initialize the driver for the '"+device_config['device_id']+"' device. "+
                              "Received error message: "+str(driver_exception))

# Define schedule related exceptions
class InvalidDeviceConfig(Exception):
  pass
class DriverNotFound(Exception):
  pass
class DriverInitError(Exception):
  pass
class DevicesAlreadyInitialized(Exception):
  pass
class DeviceNotFound(Exception):
  pass
