# Import required modules
import logging, time, json
from pkg_resources import Requirement, resource_filename
from twisted.trial import unittest
from twisted.test import proto_helpers
from hwm.core.configuration import *
from hwm.network.security import permissions

class TestPermissionManager(unittest.TestCase):
  """ This test suite tests the permission manager class, which is used to manage and cache downloaded user command
  execution permissions.
  """
  
  def setUp(self):
    # Set a local reference to Configuration (how other modules should typically access Config)
    self.config = Configuration
    self.config.verbose_startup = False
    
    # Set the source data directory
    self.source_data_directory = resource_filename(Requirement.parse("Mercury2HWM"),"hwm")
    
    # Disable logging for most events
    logging.disable(logging.CRITICAL)
  
  def tearDown(self):
    # Reset the recorded configuration values
    self.config.options = {}
    self.config.user_options = {}
    
    # Reset the object references
    self.config = None
  
  def test_local_file_load_missing(self):
    """ Verifies that the correct error is generated when the offline permissions file can't be found.
    """
    
    # Initialize the permission manager
    permission_manager = permissions.PermissionManager(self.source_data_directory+'/network/security/tests/data/test_permissions_doesnt_exist.json')
    
    # Force a file load
    update_deferred = permission_manager.add_user_permissions('test_user')
    
    return self.assertFailure(update_deferred, permissions.PermissionsError)
