""" @package hwm.hardware.devices.drivers.service
Provides a base abstract class that driver services may implement.
"""

class Service(object):
  """ Provides the base automated service abstract class.

  This class provides a base abstract class that driver services may implement.

  @note The properties defined by this interface are required for the Pipeline class (among others) to function
        properly. If you decide not to use this class, make sure to implement these properties.
  """

  def __init__(self, service_id, service_type):
    """ Sets up the service instance.

    @param service_id    The service ID (what other pipeline devices will search for when looking for the service).
    @param service_type  The service type.
    """

    self._service_id = service_id
    self._service_type = service_type

  @property
  def id(self):
    """ Returns the ID of the service.

    This property returns the ID of the service which, when combined with the service type, forms a unique identifier
    for a given pipeline.
    """

    return self._service_id
  
  @property
  def type(self):
    """ Returns the service type.

    This property returns the service's type as a string. There are several standard service types (such as 'tracker')
    that the service can use, or it can define its own. However, if a service defines its own type other devices will
    only be able to use it if they query that specific type and if they know how to use the interface.
    """

    return self._service_type
