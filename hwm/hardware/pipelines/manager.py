""" @package hwm.hardware.pipelines.manager
Manages access to the hardware pipeline pool.

This module contains a class that is responsible for initializing, and providing access to, the configured hardware
pipelines.
"""

# Import required modules
import logging, jsonschema
from hwm.core import configuration
from hwm.hardware.pipelines import pipeline
from hwm.hardware.devices import manager as device_manager

class PipelineManager:
  """ Provides access the collection of available hardware pipelines.
  
  This class initializes and manages the collection of loaded hardware pipelines.
  """
  
  def __init__(self, device_manager, command_parser):
    """ Sets up the pipeline manager.
    
    This constructor sets up the pipeline manager and calls a method that initializes the available pipelines.
    
    @note This constructor may pass on exceptions from the pipeline initialization (see _initialize_pipelines).
    @note This class does not load the pipeline configuration file itself. Instead, Configuration is instructed to load
          it at runtime and this class accesses it via configuration. Therefore, if this class is initialized before the 
          pipeline configuration has been loaded an exception will be generated.
    """
    
    # Setup class attributes
    self.config = configuration.Configuration
    self.pipelines = {}
    self.devices = device_manager
    self.commands = command_parser
    
    # Initialize the configured pipelines
    self._initialize_pipelines()
  
  def get_pipeline(self, pipeline_id):
    """ Returns a reference to the specified pipeline.
    
    @note This method does not perform any pipeline locking. That is managed by the individual pipeline classes and is
          typically done by the session coordinator.
    
    @throw Throws PipelineNotFound when the requested pipeline can't be found.
    
    @param pipeline_id  The ID of the requested pipeline.
    @return Returns a reference to the specified pipeline object.
    """
    
    # Verify that the pipeline exists
    if pipeline_id not in self.pipelines:
      raise PipelineNotFound
    
    return self.pipelines[pipeline_id]
  
  def _initialize_pipelines(self):
    """ Initializes the configured pipelines.
    
    This method initializes all of the configured pipelines (i.e. available in the configuration) and saves their
    references.
    
    @throw Throws PipelinesAllReadyInitialized if this method is called after pipelines have been initialized.
    @throw Throws PipelinesNotDefined if no pipelines are defined in the runtime configuration.
    @throw May pass on PipelineConfigInvalid from _validate_pipelines() if the loaded pipeline configuration is invalid.
    """
    
    # Verify that no pipelines have been initialized yet
    if len(self.pipelines) > 0:
      logging.error("The PipelineManager has already initialized the pipelines.")
      raise PipelinesAlreadyInitialized("The pipeline manager initialization procedure was called twice.")
    
    # Load the pipeline configuration
    try:
      pipeline_settings = self.config.get('pipelines')
    except configuration.OptionNotFound:
      logging.error("No pipeline configurations defined, pipeline manager not initialized.")
      raise PipelinesNotDefined("No pipeline definitions were found in the configuration files.")
    
    # Validate the pipeline configuration
    self._validate_pipelines(pipeline_settings)
    
    # Loop through and create a Pipeline object for each configured pipeline
    for pipeline_config in pipeline_settings:
      temp_pipeline = pipeline.Pipeline(pipeline_config, )
      self.pipelines[temp_pipeline.id] = temp_pipeline
  
  def _validate_pipelines(self, pipeline_configuration):
    """ Validates the provided pipeline configuration.
    
    This method validates the provided pipeline configuration (loaded from the configuration files) by comparing it
    against the defined schema.
    
    @note Each pipeline class may perform additional validations when initialized. This method simply checks the 
          pipeline configuration schema as a whole.
    
    @throw Throws PipelineConfigInvalid if the provided pipeline configuration is invalid.
    
    @param pipeline_configuration  An object containing the pipeline configuration from the YAML configuration files.
    """
    
    # Define a schema that species the format of the YAML pipeline configuration. Note that, because YAML is a superset
    # of JSON, the JSON draft 3 schema validator can validate most simple YAML files.
    pipeline_schema = {
      "type": "array",
      "$schema": "http://json-schema.org/draft-03/schema",
      "required": True,
      "minItems": 1,
      "additionalItems": False,
      "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
          "id": {
            "type": "string",
            "required": True
          },
          "mode": {
            "type": "string",
            "enum": ["transmit", "receive", "transceive"],
            "required": True
          },
          "hardware": {
            "type": "array",
            "required": True,
            "minItems": 1,
            "additionalItems": False,
            "items": {
              "type": "object",
              "additionalProperties": False,
              "properties": {
                "device_id": {
                  "type": "string",
                  "required": True
                },
                "pipeline_input": {
                  "type": "boolean",
                  "required": False
                },
                "pipeline_output": {
                  "type": "boolean",
                  "required": False
                }
              }
            }
          },
          "setup_commands": {
            "type": "array",
            "required": False,
            "additionalItems": False,
            "items": {
              "type": "object",
              "additionalProperties": False,
              "properties": {
                "command": {
                  "type": "string",
                  "id": "command",
                  "required": True
                },
                "destination": {
                  "type": "string",
                  "id": "destination",
                  "required": True
                },
                "parameters": {
                  "type": "object",
                  "additionalProperties": True,
                  "required": False
                }
              }
            }
          }
        }
      }
    }
    
    # Validate the JSON schema
    config_validator = jsonschema.Draft3Validator(pipeline_schema)
    try:
      config_validator.validate(pipeline_configuration)
    except jsonschema.ValidationError:
      # Invalid pipeline configuration
      logging.error("Failed to initialize the pipeline manager because the pipeline configuration was invalid.")
      raise PipelineConfigInvalid("The loaded pipeline configuration does not conform to the defined schema.")

# Define PipelineManager exceptions
class PipelinesNotDefined(Exception):
  pass
class PipelinesAlreadyInitialized(Exception):
  pass
class PipelineNotFound(Exception):
  pass
class PipelineConfigInvalid(Exception):
  pass
