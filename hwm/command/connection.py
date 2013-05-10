""" @package hwm.command.connection
Contains a resource for processing commands.

This module contains a Twisted resource for responding to station commands received over the network.
"""

# Import required modules
import json
from twisted.web.resource import Resource
from twisted.web.http import HTTPClient, HTTPFactory
from twisted.web.server import NOT_DONE_YET

class CommandResource(Resource):
  """ Handles commands received over the network.
  
  This Resource handles commands received over the hardware manager's command connection.
  """
  
  # Set the resource attributes
  isLeaf = True
  
  def __init__(self, command_parser):
    """ Sets up the command resource.
    
    @param command_parser  A reference to the previously initialized command parser.
    """
    
    # Call the Resource constructor
    Resource.__init__(self)
    
    self.command_parser = command_parser
  
  def render_POST(self, request):
    """ Responds to POST'd command requests.
    
    @note All submitted commands must be POST'd to the hardware manager's root address.
    
    @param request  The request object for the submitted command.
    @return Returns NOT_DONE_YET, indicating that the results of the request may not be ready yet (results handled by
            _command_response_ready).
    """
    
    # Store the user's ID from the SSL certificate
    user_id = None
    user_certificate = self.transport.getPeerCertificate()
    if user_certificate:
      user_id = user_certificate.get_subject().commonName.decode()
    
    # Pass the request body to the parser
    response_deferred = self.command_parser.parse_command(request.content.read(), user_id=user_id)
    response_deferred.addCallback(self._command_response_ready, request)
    
    return NOT_DONE_YET
  
  def _command_response_ready(self, command_response, request):
    """ A callback that writes the response of a command back back to the protocol's transport.
    
    @param command_response  The results of the command. A dictionary containing the command response and the associated
                             request.
    @param request           The original HTTP request for the connection.
    """
    
    # Write the response to the client
    request.write(command_request['response'])
    
    # Close the request
    request.finish()
