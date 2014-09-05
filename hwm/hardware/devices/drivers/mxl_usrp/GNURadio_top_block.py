""" @package hwm.hardware.devices.drivers.mxl_usrp.GNURadio_top_block
This module contains the top-level GNU Radio block that is responsible for initializing and running the MXL USRP GNU
Radio driver.
"""

import wx
from gnuradio import eng_notation
from gnuradio import gr
from gnuradio import window
from gnuradio.eng_option import eng_option
from gnuradio.gr import firdes
from gnuradio.wxgui import fftsink2
from gnuradio.wxgui import waterfallsink2
from grc_gnuradio import wxgui as grc_wxgui
from GNURadio_usrp import MXLGS_v21

class USRPTopBlock(grc_wxgui.top_block_gui):
  """ This class represents the top-level GNU Radio block for MXL's GNU Radio based USRP driver. """

  def __init__(self,
               rx_device_address,
               tx_device_address,
               data_port,
               doppler_port,
               bit_rate,
               interpolation,
               decimation,
               sampling_rate,
               rx_freq,
               tx_freq,
               rx_gain,
               tx_gain,
               fm_dev,
               tx_fm_dev):

    # Initialize the top-level block
    super(USRPTopBlock, self).__init__(self, title="MXL USRP Driver")

    self.samp_rate = sampling_rate

    # Create the waterfall and FFT plot sinks
    self.wxgui_waterfallsink2_0 = waterfallsink2.waterfall_sink_c(
      self.GetWin(),
      baseband_freq=0,
      dynamic_range=100,
      ref_level=0,
      ref_scale=2.0,
      sample_rate=sampling_rate,
      fft_size=512,
      fft_rate=15,
      average=False,
      avg_alpha=None,
      title="Waterfall Plot"
    )
    self.Add(self.wxgui_waterfallsink2_0.win)
    self.wxgui_fftsink2_0 = fftsink2.fft_sink_c(
      self.GetWin(),
      baseband_freq=0,
      y_per_div=10,
      y_divs=10,
      ref_level=0,
      ref_scale=2.0,
      sample_rate=sampling_rate,
      fft_size=2048,
      fft_rate=15,
      average=False,
      avg_alpha=None,
      title="FFT Plot",
      peak_hold=False
    )
    self.Add(self.wxgui_fftsink2_0.win)

    # Initialize the USRP block and connect it with the waterfall and FFT sinks
    self.MXLGS_v21_0 = MXLGS_v21(
      rxdevice_addr=rx_device_address,
      txdevice_addr=tx_device_address,
      data_port=usrp_data_port,
      doppler_port=usrp_doppler_port,
      bit_rate=bit_rate,
      I_decimation=decimation,
      I_interpolation=interpolation,
      samp_rate=sampling_rate,
      fmdev=fm_dev,
      rxgain=rx_gain,
      txfmdev=tx_fm_dev,
      rxfreq=rx_freq,
      txfreq=tx_freq,
      txgain=tx_gain
    )
    self.usrp_block = self.MXLGS_v21_0 # Provide a consistent access point for Mercury2

    self.connect((self.MXLGS_v21_0, 0), (self.wxgui_waterfallsink2_0, 0))
    self.connect((self.MXLGS_v21_0, 0), (self.wxgui_fftsink2_0, 0))

  def get_samp_rate(self):
    return self.samp_rate

  def set_samp_rate(self, sampling_rate):
    # Update GNU Radio and the FFT & waterfall plots
    self.samp_rate = sampling_rate
    self.wxgui_fftsink2_0.set_sample_rate(self.samp_rate)
    self.wxgui_waterfallsink2_0.set_sample_rate(self.samp_rate)
