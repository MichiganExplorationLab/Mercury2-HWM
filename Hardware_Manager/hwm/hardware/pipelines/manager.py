""" @package hwm.hardware.pipelines.manager
Manages access to the hardware pipeline pool.

This module contains a class that is responsible for managing access to the hardware pipelines.
"""

# Import required modules
import logging
from hwm.core import configuration
from hwm.hardware.pipelines import pipeline

class PipelineManager:
  """Provides access the collection of available hardware pipelines.
  
  This class manages the collection of loaded hardware pipelines. When initialized, this class uses the available 
  runtime pipeline configuration to setup each pipeline. It also provides methods to query for pipelines.
  
  @note This class does not load the pipeline configuration file itself. Instead, Configuration is instructed to load
        it at runtime and this class accesses it via configuration.
  """
  
  def __init__(self):
    """Sets up the pipeline manager.
    
    This constructor sets up the pipeline manager. It is responsible for initializing the available pipelines (defined
    in the pipeline configuration file).
    
    @throw Throws PipelinesNotDefined if no pipelines are defined in the runtime configuration.
    @throw May pass on PipelineConfigInvalid if a pipeline constructor is supplied with an invalid configuration 
          dictionary.
    
    @note If no pipelines are defined in the configuration by the time this class is initialized, and exception will be
          generated.
    """
    
    # Set the local configuration reference
    self.config = configuration.Configuration
    
    # Initialize class variables
    self.pipelines = {}
    
    # Load the pipeline configuration
    try:
      pipeline_settings = self.config.get('pipelines')
    except configuration.OptionNotFound:
      logging.error("Pipeline configuration missing, pipeline manager not initialized.")
      raise PipelinesNotDefined
    
    # Verify at least one pipeline has been defined
    if len(pipeline_settings) == 0:
      raise PipelinesNotDefined
    
    # Loop through and create a Pipeline object for each configured pipeline
    for pipeline_config in pipeline_settings:
      # Initialize the new pipeline. If the configuration contains an error, the pipeline initializer will deal with it.
      temp_pipeline = pipeline.Pipeline(pipeline_config)

# Define PipelineManager exceptions
class PipelinesNotDefined(Exception):
  pass
