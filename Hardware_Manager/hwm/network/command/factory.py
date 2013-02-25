""" @package hwm.network.command.factory
Provides a factory that creates command connection instances.

This module contains a Twisted factory class that creates and manages individual command connection protocol instances.
"""

# Import required modules
from twisted.internet.protocol import Factory

class CommandFactory(Factory):
  """ Manages command protocol instances as needed.
  
  This factory is responsible for creating and managing ground station command protocols as users connect and 
  disconnect.
  """
  
  def __init__(self):
    """ Sets up the command protocol factory.
    """
    
  def buildProtocol(self, address):
    """ Contructs a new command protocol when a connection is made.
    
    @param address  An Address object representing the new connection.
    """
    
    
