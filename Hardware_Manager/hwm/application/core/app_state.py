""" @package hwm.application.core
Contains a class to store the hardware manager state.

This module contains a class that provides methods for storing, modifying, and retrieving application state for the 
hardware manager. Access it by importing the ManagerState variable.
"""

# Load the required libraries
import yaml

class State:
  """Provides access to the hardware manager application state.
  
  This class stores and provides access to the application state used by the hardware manager such as the 
  configuration, reservation schedules, and pipeline configuration. To use this class import this module (app_state) 
  and assign a local variable to ManagerState (makes code easier to test).
  """
  
  def __init__(self):
    """Initializes all of the available state variables to their default values."""
    
    # Program metadata
    self.version = "0.1.0";
    self.verbose_startup = True;
    
    # Ground station parameters
    self.station_name = None
    self.longitude = None
    self.latitude = None
    self.altitude = None
  
  def read_configuration(self, configuration_file):
    """Loads and parses the specified configuration file.
    
    @note All configuration files are in YAML format.
    @see http://en.wikipedia.org/wiki/YAML
    
    @param configuration_file  The YAML configuration file to load.
    """
    
    # Load the configuration file and run it through the YAML parser
    #config_stream = open(configuration_file, 'r')
    #config = yaml.load(config_stream)
    
    # Log & announce the configuration file load 
    #if self.verbose_startup:
    #  print "\n"
    
# Declare the ManagerState instance
ManagerState = State()
