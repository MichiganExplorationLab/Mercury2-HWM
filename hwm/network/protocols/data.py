""" @package hwm.network.protocols.data
This module contains the Twisted Protocol and related classes used to pass pipeline data to and from the session user.
"""

# Import required modules
import logging
from twisted.internet.protocol import Protocol, Factory
from hwm.network.protocols import mixins
from hwm.sessions import coordinator, session

class PipelineData(Protocol, mixins.AuthUtilities):
  """ Represents a Pipeline data connection.

  This Protocol represents a Pipeline data stream connection to the pipeline's active user (through its currently active
  session). It is responsible for sending the pipeline's output to the end user as well as passing the user's input to 
  the pipeline. It uses a basic TCP protocol.

  @note This Protocol only routes the pipeline data stream (what "flows" in and out of the pipeline). All other data, 
        such as the pipeline telemetry stream and station commands, pass through different protocols. 
  """

  def __init__(self, session_coordinator):
    """ Sets up the PipelineData protocol instance.

    @param session_coordinator  A SessionCoordinator instance that will be used to locate requested sessions.
    """

    # Set the protocol attributes
    self.session_coordinator = session_coordinator
    self.session = None

  def write_output(self, output_data):
    """ Sends a chunk of pipeline output to the user.

    This method writes the provided chunk of data (output from the pipeline) to the end user.

    @note Because all pipeline output must reach the end user, any data received by this function is passed to the
          transport regardless of the buffer state. All data in the transport's buffer will eventually be sent to the 
          pipeline user (unless the connection is lost).

    @see https://twistedmatrix.com/documents/8.1.0/api/twisted.internet.interfaces.ITransport.html#write

    @param output_data  A chunk of pipeline output of arbitrary size that is to be sent to the pipeline user.
    """

    # Write the data to the transport
    self.transport.write(output_data)

  def dataReceived(self, data):
    """ Receives data that the user is trying to write to the pipeline.

    This method receives data from the pipeline user and passes it along to the target pipeline via the associated
    session.

    @note If the session specified in the user's SSL certificate is not yet active, any data that they send will be 
          discarded until the session is made active active.

    @param data  A chunk of data of indeterminate size that is to be passed to the session.
    """

    # Make sure the connection is allowed to write to the session
    if self.session is not None:
      self.session.write(data)

  def connectionMade(self):
    """ Sets up the data protocol before any data transfer occurs.

    This method sets up the protocol right after the connection has been established. It is responsible for calling a
    method that will wait and load the user's certificate after the TLS handshake has been performed.

    @note Because this method may be (and probably will be) called before the connection's TLS handshake is complete,
          it calls an additional method that periodically checks if the client's certificate is available. Until it is,
          any data that the user tries to pass to the connection will be dropped. However, the TLS handshake process is 
          normally pretty fast and only occurs once per connection.
    """

    # Wait for the user's certificate and load the requested session
    self._wait_for_session()

  def connectionLost(self):
    """ Called when the pipeline data connection is lost.
    """

    return

  def _perform_registrations(self):
    """ Performs the necessary registrations with the protocol's Session instance.

    This method makes the necessary registrations between the pipeline data protocol and the associated Session 
    instance. It is automatically called by self._wait_for_session() after the requested session has been loaded.
    """

    # Perform the registrations between the data protocol and its associated session
    if self.session is not None:
      try:
        self.session.register_data_protocol(self)
      except session.ProtocolAlreadyRegistered:
        logging.error("A pipeline data protocol for the '"+self.session.id+"' reservation tried to register itself "+
                      "with its session twice.")

class PipelineDataFactory(Factory):
  """ Constructs PipelineData protocol instances for pipeline data stream connections.

  This factory constructs PipelineData protocols as users attempt to connect to their reserved pipelines.
  """

  # Setup some factory attributes
  protocol = PipelineData

  def __init__(self, session_coordinator):
    """ Sets up the PipelineData protocol factory.

    @param session_coordinator  An instance of SessionCoordinator that will be used to locate user sessions.
    """

    self.session_coordinator = session_coordinator

  def buildProtocol(self, addr):
    """ Constructs a new PipelineData instance.

    This method creates a new PipelineData instance intialized with the active SessionCoordinator instance.

    @param addr  An object that implements twisted.internet.interfaces.IAddress.
    @return Returns a new instance of the PipelineData class representing a new pipeline data stream connection.
    """

    # Initialize and return a new PipelineData protocol
    data_protocol = self.protocol(self.session_coordinator)
    data_protocol.factory = self

    return data_protocol
