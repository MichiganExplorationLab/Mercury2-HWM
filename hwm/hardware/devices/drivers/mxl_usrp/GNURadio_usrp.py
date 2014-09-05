""" @package hwm.hardware.devices.drivers.mxl_usrp.GNURadio_usrp
This module contains the GNU Radio block responsible for interacting with the USRP and processing its output.
"""

import math, time
import expgs
import sdham
import numpy
from numpy import array, convolve
from gnuradio import analog
from gnuradio import blks2
from gnuradio import blocks
from gnuradio import digital
from gnuradio import filter
from gnuradio import gr
from gnuradio import uhd
from gnuradio import extras as gr_extras
from gnuradio.filter import firdes
from gnuradio.gr import firdes

class MXLGS_v21(gr.hier_block2):
  """ This GNU Radio block is the central block responsible for interacting with the USRP and processing it's data 
  stream. It also provides methods for retrieving and setting the block parameters.
  """

  def __init__(self, rxdevice_addr="serial=E7R11Y3B1", txdevice_addr="serial=E7R11Y3B1", data_port=12600,
               doppler_port=12800, bit_rate=9600, I_decimation=5, I_interpolation=3, samp_rate=256000, fmdev=3000,
               rxgain=20, txfmdev=8000, rxfreq=435.0e6, txfreq=435.0e6, txgain=11.5):
    """ Initializes the USRP with the supplied parameters and builds the GNU Radio flow graph. """

    super(MXLGS_v21, self).__init__(
      self, "MXLGS_v21",
      gr.io_signature(0, 0, 0),
      gr.io_signature(1, 1, gr.sizeof_gr_complex*1),
    )

    ##################################################
    # Parameters
    ##################################################
    self.rxdevice_addr = rxdevice_addr
    self.txdevice_addr = txdevice_addr
    self.data_port = data_port
    self.doppler_port = doppler_port
    self.bit_rate = bit_rate
    self.I_decimation = I_decimation
    self.I_interpolation = I_interpolation
    self.samp_rate = samp_rate
    self.fmdev = fmdev
    self.rxgain = rxgain
    self.txfmdev = txfmdev
    self.rxfreq = rxfreq
    self.txfreq = txfreq
    self.txgain = txgain

    ##################################################
    # Variables
    ##################################################
    self.resamp_rate = resamp_rate = samp_rate*I_interpolation/I_decimation
    self.bit_oversampling = bit_oversampling = resamp_rate/bit_rate
    self.sqwave = sqwave = (1,)*(resamp_rate/bit_rate)
    self.mu = mu = 0.5
    self.gaussian_taps = gaussian_taps = gr.firdes.gaussian(1, bit_oversampling, 1, 4*bit_oversampling)
    self.gain_mu = gain_mu = 0.05
    self.fmk = fmk = samp_rate/(2*math.pi*fmdev)
    self.alpha = alpha = 0.0001

    ##################################################
    # Blocks
    ##################################################
    self.uhd_usrp_source_0 = uhd.usrp_source(
      device_addr=rxdevice_addr,
      stream_args=uhd.stream_args(
        cpu_format="fc32",
        channels=range(1),
      ),
    )
    self.uhd_usrp_source_0.set_samp_rate(samp_rate)
    self.uhd_usrp_source_0.set_center_freq(rxfreq-50e3, 0)
    self.uhd_usrp_source_0.set_gain(rxgain, 0)
    self.uhd_usrp_source_0.set_antenna("RX2", 0)
    self.uhd_usrp_sink_0 = uhd.usrp_sink(
      device_addr=txdevice_addr,
      stream_args=uhd.stream_args(
        cpu_format="fc32",
        channels=range(1),
      ),
    )
    self.uhd_usrp_sink_0.set_samp_rate(samp_rate)
    self.uhd_usrp_sink_0.set_center_freq(txfreq, 0)
    self.uhd_usrp_sink_0.set_gain(txgain, 0)
    self.single_pole_iir_filter_xx_0 = filter.single_pole_iir_filter_ff(alpha, 1)
    self.sdham_doppler_correction_cc_0 = sdham.doppler_correction_cc(samp_rate, self.doppler_port, 50000, long(rxfreq-50e3))
    self.rational_resampler_base_xxx_0 = filter.rational_resampler_base_fff(I_interpolation, I_decimation, (blks2.design_filter(I_interpolation,I_decimation,0.4)))
    self.interp_fir_filter_xxx_0 = filter.interp_fir_filter_fff(resamp_rate/bit_rate, (convolve(array(gaussian_taps),array(sqwave))))
    self.fir_filter_xxx_1 = filter.fir_filter_fff(1, (firdes.low_pass(1,resamp_rate, bit_rate*0.7, 4e3, firdes.WIN_HANN)))
    self.fir_filter_xxx_0 = filter.fir_filter_ccf(1, (firdes.low_pass(1, samp_rate, bit_rate*1.1, 2000, firdes.WIN_HANN)))
    self.extras_multiply_const_0 = gr_extras.multiply_const_v_fc32_fc32((1, ))
    self.extras_add_const_0 = gr_extras.add_const_v_f32_f32((-0.5, ))
    self.expgs_stream_to_pdu_0 = expgs.stream_to_pdu(True)
    self.expgs_ax25_packetization_0 = expgs.ax25_packetization(1000, 50)
    self.digital_clock_recovery_mm_xx_0 = digital.clock_recovery_mm_ff(bit_oversampling, 0.25*gain_mu*gain_mu, mu, gain_mu, 0.05)
    self.digital_binary_slicer_fb_0 = digital.binary_slicer_fb()
    self.blocks_uchar_to_float_0 = blocks.uchar_to_float()
    self.blocks_sub_xx_0 = blocks.sub_ff(1)
    self.blocks_socket_pdu_0 = blocks.socket_pdu("TCP_SERVER", "localhost", str(self.data_port), 10000)
    self.blocks_pdu_to_tagged_stream_0 = blocks.pdu_to_tagged_stream(blocks.byte_t)
    self.blks2_rational_resampler_xxx_0 = blks2.rational_resampler_fff(
      interpolation=I_decimation,
      decimation=I_interpolation,
      taps=(blks2.design_filter(I_decimation, I_interpolation,0.4)),
      fractional_bw=None,
    )
    self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf(fmk)
    self.analog_frequency_modulator_fc_0 = analog.frequency_modulator_fc(2*math.pi*txfmdev/(samp_rate))

    ##################################################
    # Connections
    ##################################################
    self.connect((self.uhd_usrp_source_0, 0), (self.sdham_doppler_correction_cc_0, 0))
    self.connect((self.sdham_doppler_correction_cc_0, 0), (self.fir_filter_xxx_0, 0))
    self.connect((self.fir_filter_xxx_0, 0), (self.analog_quadrature_demod_cf_0, 0))
    self.connect((self.analog_quadrature_demod_cf_0, 0), (self.single_pole_iir_filter_xx_0, 0))
    self.connect((self.analog_quadrature_demod_cf_0, 0), (self.blocks_sub_xx_0, 0))
    self.connect((self.single_pole_iir_filter_xx_0, 0), (self.blocks_sub_xx_0, 1))
    self.connect((self.blocks_sub_xx_0, 0), (self.rational_resampler_base_xxx_0, 0))
    self.connect((self.rational_resampler_base_xxx_0, 0), (self.fir_filter_xxx_1, 0))
    self.connect((self.fir_filter_xxx_1, 0), (self.digital_clock_recovery_mm_xx_0, 0))
    self.connect((self.digital_clock_recovery_mm_xx_0, 0), (self.digital_binary_slicer_fb_0, 0))
    self.connect((self.blocks_pdu_to_tagged_stream_0, 0), (self.expgs_ax25_packetization_0, 0))
    self.connect((self.digital_binary_slicer_fb_0, 0), (self.expgs_stream_to_pdu_0, 0))
    self.connect((self.expgs_ax25_packetization_0, 0), (self.blocks_uchar_to_float_0, 0))
    self.connect((self.blocks_uchar_to_float_0, 0), (self.extras_add_const_0, 0))
    self.connect((self.extras_add_const_0, 0), (self.interp_fir_filter_xxx_0, 0))
    self.connect((self.interp_fir_filter_xxx_0, 0), (self.blks2_rational_resampler_xxx_0, 0))
    self.connect((self.blks2_rational_resampler_xxx_0, 0), (self.analog_frequency_modulator_fc_0, 0))
    self.connect((self.analog_frequency_modulator_fc_0, 0), (self.extras_multiply_const_0, 0))
    self.connect((self.extras_multiply_const_0, 0), (self.uhd_usrp_sink_0, 0))
    self.connect((self.sdham_doppler_correction_cc_0, 0), (self, 0))

    ##################################################
    # Asynch Message Connections
    ##################################################
    self.msg_connect(self.blocks_socket_pdu_0, "pdus", self.blocks_pdu_to_tagged_stream_0, "pdus")
    self.msg_connect(self.expgs_stream_to_pdu_0, "pdus", self.blocks_socket_pdu_0, "pdus")

  def get_bit_rate(self):
    return self.bit_rate

  def set_bit_rate(self, bit_rate):
    self.bit_rate = bit_rate
    self.fir_filter_xxx_1.set_taps((firdes.low_pass(1,self.resamp_rate, self.bit_rate*0.7, 4e3, firdes.WIN_HANN)))
    self.fir_filter_xxx_0.set_taps((firdes.low_pass(1, self.samp_rate, self.bit_rate*1.1, 2000, firdes.WIN_HANN)))
    self.set_bit_oversampling(self.resamp_rate/self.bit_rate)
    self.set_sqwave((1,)*(self.resamp_rate/self.bit_rate))

  def get_I_decimation(self):
    return self.I_decimation

  def set_I_decimation(self, I_decimation):
    self.I_decimation = I_decimation
    self.set_resamp_rate(self.samp_rate*self.I_interpolation/self.I_decimation)
    self.rational_resampler_base_xxx_0.set_taps((blks2.design_filter(self.I_interpolation,self.I_decimation,0.4)))

  def get_I_interpolation(self):
    return self.I_interpolation

  def set_I_interpolation(self, I_interpolation):
    self.I_interpolation = I_interpolation
    self.set_resamp_rate(self.samp_rate*self.I_interpolation/self.I_decimation)
    self.rational_resampler_base_xxx_0.set_taps((blks2.design_filter(self.I_interpolation,self.I_decimation,0.4)))

  def get_samp_rate(self):
    return self.samp_rate

  def set_samp_rate(self, samp_rate):
    self.samp_rate = samp_rate
    self.fir_filter_xxx_0.set_taps((firdes.low_pass(1, self.samp_rate, self.bit_rate*1.1, 2000, firdes.WIN_HANN)))
    self.set_resamp_rate(self.samp_rate*self.I_interpolation/self.I_decimation)
    self.set_fmk(self.samp_rate/(2*math.pi*self.fmdev))
    self.analog_frequency_modulator_fc_0.set_sensitivity(2*math.pi*self.txfmdev/(self.samp_rate))
    self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)
    self.uhd_usrp_sink_0.set_samp_rate(self.samp_rate)

  def get_fmdev(self):
    return self.fmdev

  def set_fmdev(self, fmdev):
    self.fmdev = fmdev
    self.set_fmk(self.samp_rate/(2*math.pi*self.fmdev))

  def get_rxgain(self):
    return self.rxgain

  def set_rxgain(self, rxgain):
    self.rxgain = rxgain
    self.uhd_usrp_source_0.set_gain(self.rxgain, 0)

  def get_txfmdev(self):
    return self.txfmdev

  def set_txfmdev(self, txfmdev):
    self.txfmdev = txfmdev
    self.analog_frequency_modulator_fc_0.set_sensitivity(2*math.pi*self.txfmdev/(self.samp_rate))

  def get_rxdevice_addr(self):
    return self.rxdevice_addr

  def set_rxdevice_addr(self, rxdevice_addr):
    self.rxdevice_addr = rxdevice_addr

  def get_txdevice_addr(self):
    return self.txdevice_addr

  def set_txdevice_addr(self, txdevice_addr):
    self.txdevice_addr = txdevice_addr

  def get_rxfreq(self):
    return self.rxfreq

  def set_rxfreq(self, rxfreq):
    self.rxfreq = rxfreq
    self.uhd_usrp_source_0.set_center_freq(self.rxfreq-50e3, 0)

  def get_txfreq(self):
    return self.txfreq

  def set_txfreq(self, txfreq):
    self.txfreq = txfreq
    self.uhd_usrp_sink_0.set_center_freq(self.txfreq, 0)

  def get_txgain(self):
    return self.txgain

  def set_txgain(self, txgain):
    self.txgain = txgain
    self.uhd_usrp_sink_0.set_gain(self.txgain, 0)

  def get_resamp_rate(self):
    return self.resamp_rate

  def set_resamp_rate(self, resamp_rate):
    self.resamp_rate = resamp_rate
    self.fir_filter_xxx_1.set_taps((firdes.low_pass(1,self.resamp_rate, self.bit_rate*0.7, 4e3, firdes.WIN_HANN)))
    self.set_bit_oversampling(self.resamp_rate/self.bit_rate)
    self.set_sqwave((1,)*(self.resamp_rate/self.bit_rate))

  def get_bit_oversampling(self):
    return self.bit_oversampling

  def set_bit_oversampling(self, bit_oversampling):
    self.bit_oversampling = bit_oversampling
    self.digital_clock_recovery_mm_xx_0.set_omega(self.bit_oversampling)
    self.set_gaussian_taps(gr.firdes.gaussian(1, self.bit_oversampling, 1, 4*self.bit_oversampling))

  def get_sqwave(self):
    return self.sqwave

  def set_sqwave(self, sqwave):
    self.sqwave = sqwave
    self.interp_fir_filter_xxx_0.set_taps((convolve(array(self.gaussian_taps),array(self.sqwave))))

  def get_mu(self):
    return self.mu

  def set_mu(self, mu):
    self.mu = mu
    self.digital_clock_recovery_mm_xx_0.set_mu(self.mu)

  def get_gaussian_taps(self):
    return self.gaussian_taps

  def set_gaussian_taps(self, gaussian_taps):
    self.gaussian_taps = gaussian_taps
    self.interp_fir_filter_xxx_0.set_taps((convolve(array(self.gaussian_taps),array(self.sqwave))))

  def get_gain_mu(self):
    return self.gain_mu

  def set_gain_mu(self, gain_mu):
    self.gain_mu = gain_mu
    self.digital_clock_recovery_mm_xx_0.set_gain_omega(0.25*self.gain_mu*self.gain_mu)
    self.digital_clock_recovery_mm_xx_0.set_gain_mu(self.gain_mu)

  def get_fmk(self):
    return self.fmk

  def set_fmk(self, fmk):
    self.fmk = fmk
    self.analog_quadrature_demod_cf_0.set_gain(self.fmk)

  def get_alpha(self):
    return self.alpha

  def set_alpha(self, alpha):
    self.alpha = alpha
    self.single_pole_iir_filter_xx_0.set_taps(self.alpha)