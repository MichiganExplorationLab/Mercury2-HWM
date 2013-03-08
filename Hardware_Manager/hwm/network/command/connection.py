""" @package hwm.network.command.connection
Contains the protocol and factory that provides access to ground station command connections.

This module contains a Twisted protocol and factory class that provide an interface to user command connections.
"""

# Import required modules
from twisted.web.http import HTTPClient, HTTPFactory

class CommandConnection(HTTPClient):
  """ Represents a command connection with a user.
  
  The hardware manager uses this Twisted protocol class to represent a single ground station command connection made 
  between the station and a user.
  """
  
  def rawDataReceived(self, data):
    """ Processes raw commands as they're received.
    
    This method processes raw commands from the client by passing them to the command parser.
    
    @param data  The body of the HTML request.
    """
    
    print 'Data Received: '+data

class CommandFactory(HTTPFactory):
  """ Manages command protocol instances as needed.
  
  This factory is responsible for creating and managing ground station command protocols as users connect and 
  disconnect.
  """
  
  # Setup class attributes
  protocol = CommandConnection
    
  def buildProtocol(self, address):
    """ Contructs a new command protocol when a connection is made.
    
    @param address  An Address object representing the new connection.
    @return Returns the new protocol instance.
    """
    
    # Create a new protocol
    command_protocol = HTTPFactory.buildProtocol(self, address)
    
    return command_protocol
