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
    
    This constructor sets up the pipeline manager and calls a method that initializes the available pipelines.
    
    @note This constructor may pass on exceptions from the pipeline initialization (see _initialize_pipelines).
    """
    
    # Set the local configuration reference
    self.config = configuration.Configuration
    
    # Initialize class variables
    self.pipelines = {}
    
    # Initialize 
    self._initialize_pipelines()
  
  def get_pipeline(self, pipeline_id):
    """Returns a reference to the specified pipeline.
    
    @note This method does not perform any pipeline locking. That occurs when the session manager creates a new session.
    
    @throw Throws PipelineNotFound when the requested pipeline can't be found.
    
    @param pipeline_id  The ID of the requested pipeline.
    @return Returns a reference to the specified pipeline object.
    """
    
    # Verify that the pipeline exists
    if pipeline_id not in self.pipelines:
      raise PipelineNotFound
    
    return self.pipelines[pipeline_id]
  
  def _initialize_pipelines(self):
    """Initializes the configured pipelines.
    
    This method initializes all of the configured pipelines (i.e. available in the configuration) and adds their 
    references to a class attribute.
    
    @throw Throws PipelinesAllReadyInitialized if this method is called after pipelines have been initialized.
    @throw Throws PipelinesNotDefined if no pipelines are defined in the runtime configuration.
    @throw May pass on PipelineConfigInvalid if a pipeline constructor is supplied with an invalid configuration 
          dictionary.
    
    @note If no pipelines are defined in the configuration by the time this class is initialized, an exception will be
          generated.
    """
    
    # Verify that no pipelines have been initialized yet
    if len(self.pipelines) > 0:
      logging.error("The PipelineManager has all ready initialized the pipelines.")
      raise PipelinesAllReadyInitialized
    
    # Load the pipeline configuration
    try:
      pipeline_settings = self.config.get('pipelines')
    except configuration.OptionNotFound:
      logging.error("Pipeline configuration missing, pipeline manager not initialized.")
      raise PipelinesNotDefined
    
    # Verify at least one pipeline has been defined
    if len(pipeline_settings) == 0:
      logging.error("Can't initialize PipelineManager because no pipelines have been configured.")
      raise PipelinesNotDefined
    
    # Loop through and create a Pipeline object for each configured pipeline
    for pipeline_config in pipeline_settings:
      # Initialize the new pipeline. If the configuration contains an error, the pipeline initializer will deal with it.
      temp_pipeline = pipeline.Pipeline(pipeline_config)
      self.pipelines[temp_pipeline.id] = temp_pipeline

# Define PipelineManager exceptions
class PipelinesNotDefined(Exception):
  pass
class PipelinesAllReadyInitialized(Exception):
  pass
class PipelineNotFound(Exception):
  pass
