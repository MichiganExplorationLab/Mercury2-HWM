""" @package hwm.hardware.pipelines.pipeline
Represents individual hardware pipelines.

This modules contains the class that represents individual hardware pipelines and provides associated helper functions.
"""

# Import required packages
import logging

class Pipeline:
  """ Represents and provides access to a hardware pipeline.
  
  This class provides an interface to the hardware pipeline and associated hardware devices.
  """
  
  def __init__(self, pipeline_configuration):
    """ Initializes the pipeline with the supplied configuration.
    
    @param pipeline_configuration  A dictionary containing the settings to initialize the pipeline with. This is 
                                   supplied by the pipeline manager and is loaded from the pipeline configuration file.
    """
    
    # Initialize pipeline attributes
    self.in_use = False
    self.configuration = pipeline_configuration
    self.id = pipeline_configuration['id']
  
  def reserve_pipeline(self):
    """ Locks the pipeline.
    
    This method is used primarily by the session coordinator to ensure that a pipeline is never used concurrently by two
    different sessions. However, to enable some more design flexibility, this is enforced purely by convention (unlike a
    mutex).
    
    @throw Raises PipelineInUse if the pipeline is currently being used and can't be locked.
    """
    
    # Check if the pipeline is being used
    if self.in_use:
      raise PipelineInUse("The pipeline requested is all ready in use and can not be reserved.")
    
    # Lock the pipeline
    self.in_use = True
  
  def free_pipeline(self):
    """ Frees the pipeline.
    
    This method is used to free a pipeline. This typically occurs at the conclusion of a usage session.
    """
    
    # Free the pipeline
    self.in_use = False

# Define the Pipeline exceptions
class PipelineInUse(Exception):
  pass
