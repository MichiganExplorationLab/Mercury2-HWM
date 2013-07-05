""" @package hwm.hardware.devices.drivers.driver
This module defines the base driver classes available to Mercury2. Namely, the HardwareDriver and VirtualDriver classes
which are for are used to represent physical and virtual devices.
"""

# Import required modules
import logging, threading

class Driver(object):
  """ Provides the base driver class interface.
  
  This class provides the interface that all Mercury2 device drivers must be derived from. If defines several functions
  common to both virtual and physical devices as well as abstract methods that derived drivers must implement. Note that
  specific driver classes should instead inherit from either the HardwareDriver or VirtualDriver classes.
  """
  
  def __init__(self, device_configuration):
    """ Initializes the new device driver.
    
    @param device_configuration  A dictionary containing the device configuration (from the devices.yml configuration
                                 file).
    """
    
    # Set driver attributes
    self.settings = device_configuration
    self.id = self.settings['id']
    self.allow_concurrent_use = (False if ('allow_concurrent_use' not in self.settings) else 
                                 self.settings['allow_concurrent_use'])
    self.associated_pipelines = {}
  
  def current_state(self):
    """ Returns a dictionary containing the current state of the device.

    This method should return a dictionary containing all available/important state for this device. Any Pipeline using
    the device will use this to assemble a real time stream of the pipeline state.

    @throw Throws StateNotDefined if no state is available for a given device. This can happen if you forget to override
           this method or if the device genuinely doesn't have any state.

    @return Should return a dictionary containing the device's current state. 
    """

    raise StateNotDefined("The '"+self.id+"' device did not specify any device state.")

  def register_pipeline(self, pipeline, output_to_pipeline=False):
    """ Associates a pipeline with the device.

    This method registers the specified pipeline with the device. This allows the device driver to use the pipeline to 
    pass along device output, register and load services (provided by virtual devices), and register extra data streams.

    @note This method allows multiple pipelines to be registered with the device (by storing the references in a
          dictionary). This allows some devices (such as webcams) to be used concurrently by multiple pipelines.
    @note Drivers should only feed their main data stream (if they have one) to pipelines with the 'output_to_pipeline' 
          flag set.
    
    @throws Raises PipelineAlreadyRegistered in the event that the user tries to register the same pipeline twice with
            the device.

    @param pipeline            The Pipeline to register with the device.
    @param output_to_pipeline  A flag that indicates if the device should output its primary data stream (if it has one)
                               to the specified pipeline. If the device is marked as the output device for a given 
                               pipeline, this will be set to True.
    """

    # Make sure the pipeline hasn't been registered yet
    if pipeline.id in self.associated_pipelines:
      raise PipelineAlreadyRegistered("The '"+pipeline.id+"' pipeline has already been registered with the '"+self.id+
                                      "' device.")

    # Register the pipeline
    self.associated_pipelines[pipeline.id] = {"Pipeline": pipeline, "output_to_pipeline": output_to_pipeline}

class HardwareDriver(Driver):
  """ The base hardware driver interface.

  This class provides the base driver interface that must be implemented when developing physical hardware device
  drivers for the hardware manager.
  """

  def __init__(self, device_configuration):
    """ Sets up the physical hardware driver.

    @param device_configuration  A dictionary containing the device configuration (from the devices.yml configuration
                                 file).
    """

    # Call the base driver constructor
    super(HardwareDriver,self).__init__(device_configuration)

    # Set up attributes unique to physical devices
    self.access_lock = threading.Lock()

  def reserve_device(self):
    """ Reserves the device for a user reservation.

    This method tries to acquire the device lock and raises an exception if it can't. However, if the device is
    configured for concurrent access it will simply pass.
    
    @note Pipelines will typically use this method to lock their constituent hardware devices when a session requests a 
          specific pipeline. This prevents two different sessions from accidentally allowing access to the same device 
          at the same time while still allowing access to the driver for other things (like admin commands which can 
          arrive at any time and are independent of an active session).
    
    @throw Throws DeviceInUse if the device has already been reserved by another pipeline.
    """
    
    # Check if the device allows concurrent use
    if not self.allow_concurrent_use:
      # Check if the device is being used
      if not self.access_lock.acquire(False):
        raise DeviceInUse("The requested device is currently being used and can't be reserved.")
  
  def free_device(self):
    """ Frees the device lock.
    
    @note The pipeline that is currently using this device should call this during the sesssion cleanup process.
    @note If a device allows concurrent use, this method will have no effect.
    """
    
    # Check if the device allows concurrent use
    if not self.allow_concurrent_use:
      # Free the device
      try:
        self.access_lock.release()
      except ThreadError:
        pass

class VirtualDriver(Driver):
  """ Defines the base driver used for virtual devices.

  @note The VirtualDriver interface does not provide driver locking methods because virtual devices are created
        per-pipeline and can't be scheduled in a conflicting way (because pipelines can't be used concurrently).
  """

  def __init__(self, device_configuration):
    """ Sets up the virtual device driver.

    @param device_configuration  A dictionary containing the device configuration (from the devices.yml configuration
                                 file).
    """

    # Call the base driver constructor
    super(VirtualDriver,self).__init__(device_configuration)

# Define custom driver exceptions
class PipelineAlreadyRegistered(Exception):
  pass
class PipelineNotRegistered(Exception):
  pass
class StateNotDefined(Exception):
  pass
class DeviceInUse(Exception):
  pass
  