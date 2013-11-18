""" @package hwm.hardware.devices.drivers.test_driver.test_driver
Contains a simple empty driver for unit testing purposes. Do not use this for anything besides testing.
"""

# Import required modules
from hwm.hardware.devices.drivers import driver
from hwm.command.tests import utilities

class Test_Driver(driver.HardwareDriver):
  """ A simple test driver used by unit tests to test the correctness of the device manager and base driver class.
  """
  
  def __init__(self, device_configuration, command_parser):
    """ Initialize the dummy driver.
    
    @param device_configuration  A dictionary containing the device configuration settings.
    @param command_parser        A reference to the active CommandParser.
    """
    
    # Call the default constructor
    super(Test_Driver,self).__init__(device_configuration, command_parser)
    
    # Set the device name
    self.device_name = device_configuration['id']

    # Initialize the command handler
    self._command_handler = utilities.TestCommandHandler('Test_Driver')
  
  def test_value(self):
    """ Simply returns a static value for testing purposes.
    """
    
    return "QWERTY"

  def get_command_handler(self):
    """ Returns a test command handler.

    @return Returns the TestCommandHandler command handler.
    """

    return self._command_handler

