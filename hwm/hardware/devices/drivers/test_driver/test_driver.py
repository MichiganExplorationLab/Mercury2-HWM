""" @package hwm.hardware.devices.drivers.test_driver.test_driver
Contains a simple empty driver for unit testing purposes. Do not use this for anything besides testing.
"""

# Import required modules
from hwm.hardware.devices.drivers import driver

class Test_Driver(driver.Driver):
  """ A simple test driver used by unit tests to test the correctness of the device manager and base driver class.
  """
  
  def __init__(self, device_configuration):
    """ Initialize the dummy driver.
    
    @param device_configuration  A dictionary containing the device configuration settings.
    """
    
    # Set the device name
    self.device_name = device_configuration['id']
    
    # Call the default constructor
    driver.Driver.__init__(self, device_configuration)
  
  def test_value(self):
    """ Simply returns a static value for testing purposes.
    """
    
    return "QWERTY"
