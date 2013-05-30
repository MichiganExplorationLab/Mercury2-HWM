""" @package hwm.hardware.devices.drivers.driver
Defines the base driver class that all other device drivers must extend.
"""

# Import required modules
import logging, threading

class Driver:
  """ Provides the base driver interface.
  
  This class contains the base driver implementation and defines several useful utility functions.
  
  @note All custom drivers must inherit from this class. It defines the interface that the hardware manager uses to 
        interface with devices.
  """
  
  def __init__(self, device_configuration):
    """ Initializes the new device driver.
    
    @param device_configuration  A dictionary containing the device configuration (from the devices.yml configuration
                                 file).
    """
    
    # Set driver attributes
    self.settings = device_configuration
    self.access_lock = threading.Lock()
  
  def reserve_device(self):
    """ Reserves the device for a reservation.
    
    This method checks if the device is currently being used and, if it isn't, updates the usage flag (in_use).
    
    @note Typically, only sessions should need to reserve devices for access. This prevents two sessions from 
          accidentally allowing access to the same device at the same time while still allowing access to the driver for
          other things (like admin non-session commands).
    
    @throw Throws DeviceInUse if the device has already been reserved by another session.
    """
    
    # Check if the device is being used
    if not self.access_lock.acquire(False):
      raise DeviceInUse("The requested device is currently being used and can't be reserved.")
  
  def free_device(self):
    """ Frees the device usage lock.
    
    @note Sessions should call this as they're being cleaned up after their reservation ends.
    """
    
    # Free the device
    try:
      self.access_lock.release()
    except ThreadError:
      pass
  
# Define custom driver exceptions
class DeviceInUse(Exception):
  pass
  