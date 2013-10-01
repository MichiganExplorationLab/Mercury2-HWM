""" @package hwm.network.protocols.telemetry
This module contains the Twisted Protocol (and related classes) used to broadcast pipeline telemetry to its users.
"""

# Import required modules
import base64, json, logging
from twisted.internet.protocol import Protocol, Factory
from hwm.network.protocols import utilities
from hwm.sessions import session

class PipelineTelemetry(Protocol):
  """ Represents a pipeline telemetry connection.

  This Protocol is used to represent a connection to a pipeline's telemetry stream. It is responsible for relaying
  telemetry data (provided by the Session) to the connected pipeline user. Typically, the user will connect to a
  pipeline's telemetry stream via their browser as they monitor the pass using the Mercury2 User Interface. Because 
  pipeline telemetry is inherently message based, and because it needs to be easily accessible by a web browser, this
  Protocol uses the WebSocket protocol.

  @note Because this protocol is inherently one way, any data sent by the user will simply be dropped.

  @see https://en.wikipedia.org/wiki/WebSocket
  """

  def __init__(self, session_coordinator):
    """ Sets up the PipelineTelemetry protocol instance.

    @param session_coordinator  A SessionCoordinator instance that will be used to locate requested sessions.
    """

    # Set protocol attributes
    self.session_coordinator = session_coordinator
    self.session = None

  def write_telemetry(self, source_id, stream, timestamp, telemetry_datum, binary=False, **extra_headers):
    """ Sends a telemetry data point to the user.

    This method sends the specified telemetry data point to the protocol's connected user. It will first package up the 
    telemetry point into a JSON string and then send it to the user. 

    @param source_id        The ID of the device or pipeline that generated the telemetry datum.
    @param stream           A string identifying which of the device's telemetry streams the datum should be associated 
                            with.
    @param timestamp        A unix timestamp specifying when the telemetry point was assembled.
    @param telemetry_datum  The actual telemetry datum. Can take many forms (e.g. a dictionary or binary webcam image).
    @param binary           Whether or not the telemetry payload consists of binary data. If set to true, the data will
                            be encoded before being sent to the user.
    @param **extra_headers  A dictionary containing extra keyword arguments that should be included as additional
                            headers when sending the telemetry datum.
    """

    # Assemble a JSON string containing the telemetry point
    telemetry_json = self._package_telemetry(source_id, stream, timestamp, telemetry_datum, binary=binary, 
                                             **extra_headers)

    # Send the telemetry point to the user
    self.transport.write(telemetry_json)

  def dataReceived(self, data):
    """ Receives any data that the user may try to send over the connection.

    @note Because the telemetry stream is one way, any data received by this function will simply be ignored.

    @param data  A chunk of data of arbitrary size from the user that will be ignored.
    """

    return

  def connectionMade(self):
    """ Sets up the telemetry protocol before any data transfer occurs.

    This method sets up the protocol right after the connection has been established. It is responsible for calling a
    function that will wait and load the user's certificate after the TLS handshake has been performed.

    @note Because this method may be (and probably will be) called before the connection's TLS handshake is complete,
          it calls an additional function that periodically checks if the client's certificate is available and, once it
          is, returns it via a deferred. Any data that the user tries to pass to the connection before the TLS handshake
          has completed will be dropped.
    @return Returns a deferred that will be fired with the requested Session.
    """

    # Wait for the user's certificate and load the requested session
    tls_handshake_deferred = utilities.load_session_after_tls_handshake(self)
    tls_handshake_deferred.addCallback(self.perform_registrations)
    tls_handshake_deferred.addErrback(self._connection_setup_error)

    return tls_handshake_deferred

  def connectionLost(self):
    """ Called when the connection to the user is lost.
    """

    return

  def perform_registrations(self, requested_session):
    """ Performs the necessary registrations between the protocol and its associated session.

    This callback makes the necessary registrations between the pipeline data protocol, its Session, and its pipeline's
    telemetry producer. It will be called with session specified in the client's TLS certificate after the TLS handshake
    is complete.

    @throw May pass along session.ProtocolAlreadyRegistered exceptions when trying to register this protocol with its
           session.

    @param requested_session  The session associated with the protocol.
    @return Returns the newly loaded Session that was passed to this callback.
    """

    # Store the session
    self.session = requested_session

    # Perform the registrations between the data protocol and its associated session
    if self.session is not None:
      self.session.register_telemetry_protocol(self)

      # Register the telemetry producer with the protocol's transport
      telemetry_producer = self.session.get_pipeline_telemetry_producer()
      self.transport.registerProducer(telemetry_producer, True)

    return requested_session

  def _package_telemetry(self, source_id, stream, timestamp, telemetry_datum, binary=False, **extra_headers):
    """ Packages a telemetry point into a JSON string.

    This method packages up the provided telemetry data point into a JSON string in preparation for transmission. The 
    extra_headers will be included as top level attributes in the resulting JSON object.

    @note If the telemetry point consists of binary data, it will be BASE64 encoded before being returned.
    
    @param source_id        The ID of the device or pipeline that generated the telemetry datum.
    @param stream           A string identifying which of the device's telemetry streams the datum should be associated 
                            with.
    @param timestamp        A unix timestamp specifying when the telemetry point was assembled.
    @param telemetry_datum  The actual telemetry datum. Can take many forms (e.g. a dictionary or binary webcam image).
    @param binary           Whether or not the telemetry payload consists of binary data. If set to true, the data will
                            be encoded before being sent to the user.
    @param **extra_headers  A dictionary containing extra keyword arguments that should be included as additional
                            headers when sending the telemetry datum.
    @return Returns a JSON string encapsulating the telemetry data point.
    """

    # Encode the payload if required
    if binary:
      payload = base64.b64encode(telemetry_datum)
    else:
      payload = telemetry_datum

    # Assemble a dictionary encapsulating the telemetry point
    telemetry_point = {
      'source': source_id,
      'stream': stream,
      'generated_at': timestamp,
      'binary': binary,
      'telemetry': payload
    }

    # Append the additional headers (if any)
    telemetry_point.update(extra_headers)

    return json.dumps(telemetry_point)

  def _connection_setup_error(self, failure):
    """ Handles errors that arise during the telemetry protocol connection setup.

    This callback handles errors that may occur when authenticating the protocol user and loading their requested
    session. It logs the error and cleans up the protocol's connection.

    @param failure  A Failure object encapsulating the error.
    @return Returns None after handling the error.
    """

    # Close the connection and log the error
    self.transport.abortConnection()
    logging.error("An error occured setting up a pipeline telemetry connection: '"+str(failure.value)+"'")

    return None

class PipelineTelemetryFactory(Factory):
  """ Constructs PipelineTelemetry protocol instances for pipeline telemetry stream connections.

  This factory constructs PipelineTelemetry protocol instances as users attempt to connect to their reserved pipeline's
  telemetry stream. Typically, the Mercury2 user interface will connect to the pipeline's telemetry stream on the user's
  behalf because it includes a suite of tools for parsing the raw telemetry stream data.
  """

  # Setup some factory attributes
  protocol = PipelineTelemetry

  def __init__(self, session_coordinator):
    """ Sets up the PipelineTelemetry protocol factory.

    @param session_coordinator  An instance of SessionCoordinator that will be used to locate user sessions.
    """

    self.session_coordinator = session_coordinator

  def buildProtocol(self, addr):
    """ Constructs a new PipelineTelemetry protocol.
    
    This method creates and returns a new PipelineTelemetry instance initialized with the active SessionCoordinator
    instance.

    @param addr  An object that implements twisted.internet.interfaces.IAddress.
    @return Returns a new instance of the PipelineTelemetry class representing a new pipeline telemetry stream 
            connection.
    """

    # Initialize and return a new PipelineTelemetry protocol
    telemetry_protocol = self.protocol(self.session_coordinator)
    telemetry_protocol.factory = self

    return telemetry_protocol
