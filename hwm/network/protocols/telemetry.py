""" @package hwm.network.protocols.telemetry
This module contains the Twisted Protocol (and related classes) used to broadcast pipeline telemetry to its users.
"""

# Import required modules
import base64, json
from twisted.internet.protocol import Protocol, Factory
from hwm.network.protocols import mixins

class PipelineTelemetry(Protocol, mixins.AuthUtilities):
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
    method that will wait and load the user's certificate after the TLS handshake has been performed.

    @note Because this method may be (and probably will be) called before the connection's TLS handshake is complete,
          it calls an additional method that periodically checks if the client's certificate is available. Until it is,
          any data that the user tries to pass to the connection will be dropped. However, the TLS handshake process is 
          normally pretty fast and only occurs once per connection.
    """

    # Wait for the user's certificate and load the requested session
    self._wait_for_session()

  def connectionLost(self):
    """ Called when the connection to the user is lost.
    """

    return

  def _perform_registrations(self):
    """ Performs the necessary registrations with the protocol's Session instance.

    This method makes the necessary registrations between the pipeline telemetry protocol and the associated Session 
    instance. It is automatically called by self._wait_for_session() after the requested session has been loaded.
    """

    # Perform the registrations between the data protocol and its associated session
    if self.session is not None:
      try:
        self.session.register_telemetry_protocol(self)
      except session.ProtocolAlreadyRegistered:
        logging.error("A pipeline telemetry protocol for the '"+self.session.id+"' reservation tried to register "+
                      "itself with its session twice.")

      # Register the telemetry producer with the protocol's transport
      telemetry_producer = self.session.get_pipeline_telemetry_producer()
      self.transport.registerProducer(telemetry_producer, True)

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
      'telemetry': payload
    }

    # Append the additional headers (if any)
    telemetry_point.update(extra_headers)

    return json.dumps(telemetry_point)

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
