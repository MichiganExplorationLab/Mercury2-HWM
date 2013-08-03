""" @package hwm.hardware.devices.drivers.service
Provides a base abstract class that driver services may implement.
"""

class Service(object):
  """ Provides the base automated service abstract class.

  This class provides a base abstract class that driver services may implement.

  @note The properties defined by this interface are required for the Pipeline class (among others) to function
        properly. If you decide not to use this class, make sure to implement these properties.
  """

  @property
  def id(self):
    """ Returns the ID of the service.

    This property returns the ID of the service which, when combined with the service type, forms a unique identifier.
    """

    return None

  @property
  def type(self):
    """ Returns the service type.

    This property returns the service's type as a string. There are several standard service types (such as 'tracker')
    that the service can use, or it can define its own. However, if a service defines its own type other devices will
    only be able to use it if they query that specific type and if they know how to use the interface.
    """

    return None
