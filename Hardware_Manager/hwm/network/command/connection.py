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
  
  def set_command_parser(self, command_parser):
    """ Sets the protocol's command parser reference.
    
    @note This needs to be called before the protocol starts receiving data (i.e. in the factory's buildProtocol method).
    
    @param command_parser  A reference to the parser to use to process commands.
    """
    
    self.command_parser = command_parser

class CommandFactory(HTTPFactory):
  """ Manages command protocol instances as needed.
  
  This factory is responsible for creating and managing ground station command protocols as users connect and 
  disconnect.
  """
  
  # Setup class attributes
  protocol = CommandConnection
  
  def __init__(self, command_parser, logPath = None, timeout = 60*10):
    """  Constructor for the command protocol factory (CommandFactory).
    
    @param command_parser  The parser to use to parse received commands.
    @param logPath         The location of the log file.
    @param timeout         The default timeout in seconds.
    """
    
    # Call the HTTPFactory constructor
    HTTPFactory.__init__(self, logPath, timeout)
    
    # Set the local reference to the command parser
    self.command_parser = command_parser
  
  def buildProtocol(self, address):
    """ Contructs a new command protocol when a connection is made.
    
    @param address  An Address object representing the new connection.
    @return Returns the new protocol instance.
    """
    
    # Create a new protocol
    command_protocol = HTTPFactory.buildProtocol(self, address)
    command_protocol.set_command_parser(self.command_parser)
    
    return command_protocol
