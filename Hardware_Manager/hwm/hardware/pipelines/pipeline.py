""" @package hwm.hardware.pipelines.pipeline
Represents individual hardware pipelines.

This modules contains the class that represents individual hardware pipelines and associated helper functions.
"""

# Import required packages

class Pipeline:
  """Represents and provides access to hardware pipelines.
  
  This class represents and provides an interface to the hardware pipelines and associated hardware devices.
  """
  
  def __init__(self, config):
    """Initializes the pipeline with the supplied configuration.
    
    @note The pipelines are initialized by the pipeline manager, not individually.
    
    @param config  A dictionary containing the settings to initialize the pipeline with. This is supplied by the 
                   pipeline manager and is loaded from the pipeline configuration file.
    """
    
    print "Kalach shal tek."
    
    
