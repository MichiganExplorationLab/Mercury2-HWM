""" @package hwm.application.core
Contains a class to store the hardware manager state.

This module contains a class that provides methods for storing, modifying, and retrieving application state for the 
hardware manager. Access it by importing the ManagerState variable.
"""

# Load the required libraries
import logging
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
    
    # This dictionary stores all pre-built and user defined configuration settings
    self.options = {}
  
  def read_configuration(self, configuration_file):
    """Loads and parses the specified configuration file.
    
    @note All configuration files are in YAML format.
    @note All configurations are assumed to be required (i.e. this throws an uncaught exception if a file can't be loaded)
    @see http://en.wikipedia.org/wiki/YAML
    
    @param configuration_file  The YAML configuration file to load.
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
    logging.info("Startup: Read configuration file: '"+configuration_file+"'.")
    
# Declare the 'singleton' ManagerState instance
ManagerState = State()
