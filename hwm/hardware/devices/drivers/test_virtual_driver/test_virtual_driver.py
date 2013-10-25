""" @package hwm.hardware.devices.drivers.test_virtual_driver.test_virtual_driver
Contains a simple empty virtual driver for unit testing purposes. Do not use this for anything besides testing.
"""

# Import required modules
from hwm.hardware.devices.drivers import driver

class Test_Virtual_Driver(driver.VirtualDriver):
  """ A simple test virtual driver used by unit tests to test the correctness of the device manager and the virtual
  device mechanisms.

  @note This test driver does not have a command handler (some tests depend on this).
  """
  
  def __init__(self, device_configuration):
    """ Initialize the dummy driver.
    
    @param device_configuration  A dictionary containing the device configuration settings.
    """
    
    # Call the default constructor
    super(Test_Virtual_Driver,self).__init__(device_configuration)
    
    # Set some device attributes to play with
    self.device_name = device_configuration['id']
    self.is_virtual_driver = True
  
  def test_value(self):
    """ Simply returns a static value for testing purposes.
    """
    
    return "VIRTUAL_DRIVER"
