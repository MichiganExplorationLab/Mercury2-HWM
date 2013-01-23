## Sets up the Mercury2 Hardware Manager
# 
# This script uses setuptools to install the hardware manager, and its dependencies, on the system.

# Import the required packages
from setuptools import setup, find_packages

# Call the setup function
setup(
  # Project meta-data
  name = "Mercury2 Hardware Manager",
  version = "1.0dev",
  author = "Michigan Exploration Laboratory",
  description = "The hardware manager component of the Mercury2 ground station administration system.",
  keywords = "mercury2 hardware manager mxl michigan university of michigan",
  url = "http://exploration.engin.umich.edu/",
  
  # Specify which packages to include
  packages = find_packages(),
  
  # Specify the script entry locations
  entry_points = {
    'console_scripts': [
      'HardwareManager = hwm.application.core.initialization:initialize'
    ]
  },

  # Declare dependencies
  install_requires = ['Twisted>=12.3.0', 'PyYAML>=3.10', 'pyOpenSSL>=0.13', 'doxypy>=0.4.2'],
  
  # Specify patterns for data files to include
  package_data = {
    # Include all default configuration files and documentation
    '': ['*.default', 'docs/build/*']
  }
)