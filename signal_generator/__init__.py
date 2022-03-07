"""
================
Signal Generator
================

Multi-purpose signal generator for The SyDeKick. Can generate sine waves and
pulse-shape signals.

"""

import os
import sys
if not (os.path.abspath('../../thesdk') in sys.path):
    sys.path.append(os.path.abspath('../../thesdk'))

import numpy as np
import scipy.signal as scsig
import tempfile
import pdb

from thesdk import *
from vhdl import *

class signal_generator(thesdk):
    """
    Attributes
    ----------

    IOS.Members['out'].Data: np.array
        Generated signal of shape (nsamp+extra_sampl,2), where column 0 is a
        time-vector and column 1 is the signal vector. 
    sigtype: str, 'sine','pulse' or 'bpnoise'
        Signal type, either sine wave, pulse waveform or band-limited noise.
    sig_freq: float
        Signal frequency (sine, pulse).
    sig_amp: float
        Signal amplitude (sine).
    sig_cm: float
        Signal common-mode (sine).
    sig_phase: float
        Signal phase (sine).
    tau: float
        Signal delay (sine).
    fs: float
        Sampling frequency used for coherent frequency calculation (sine).
    nsamp: int
        Number of 'samples' in the output signal (sine,pulse).
    extra_sampl: int, default 0
        Number of extra 'samples' added to the output signal (sine,pulse).
    sig_osr: int, default 1
        Signal oversampling ratio which adds sig_osr points between every
        sample point (sine).
    coherent: bool, default False
        Calculate coherent signal frequency based on fs and nsamp (sine).
        Useful for clean FFTs.
    snr: float, default 0
        Target signal-to-noise ratio for the output signal. White noise is
        added to signal to reach this level. By default no noise is added.
        Experimental.
    jitter_sd: float, default NoneType 
        The standard deviation of jitter signal to be added to 'pulse' type
        rising and falling edges. By default, no jitter is added. 
    high: float, default 1
        High signal level (pulse).
    low: float, default 0
        Low signal level (pulse).
    after: float, default 0
        Time-domain delay (sine,pulse).
    duty: float, default 0.5
        Duty cycle (pulse).
    trise: float, default 5e-12
        Signal rise time (pulse).
    tfall: float, default 5e-12
        Signal fall time (pulse).
    slopetype: str, default 'rising'
        Sawtooth slope, either rising or falling.
    """
    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self,*arg): 
        self.print_log(type='I', msg='Initializing %s' %(__name__)) 
        self.proplist = ['sig_freq','lo_freq','sig_amp','sig_cm','coherent','tau','sig_phase','sig_osr','nsamp','fs','extra_sampl']
        self.sig_freq = 1e6
        self.lo_freq = 0
        self.sig_amp = 0.5
        self.tau = 0
        self.sig_cm = 0
        self.sig_phase = 0
        self.sig_osr = 1
        self.nsamp = 1024
        self.extra_sampl = 0
        self.fs = 2e9
        self.snr = 0
        self.jitter_sd = None
        self.coherent = False
        self.sigtype = 'sine'
        self.high = 1
        self.low = 0
        self.after = 0
        self.duty = 0.5
        self.trise = 5e-12
        self.tfall = 5e-12
        self.slopetype='rising'
        self.IOS=Bundle()
        self.IOS.Members['out']= IO()
        self.model='py'

        if len(arg)>=1:
            parent=arg[0]
            self.copy_propval(parent,self.proplist)
            self.parent =parent;

        self.init()

    def init(self):
        pass

    def main(self):
        if self.sigtype == 'sine' or self.sigtype=='sine_samp':
            if self.sigtype=='sine_samp' and self.sig_osr != 1: # Oversampling not supported
                self.sig_osr=1
            if not isinstance(self.sig_freq,list):
                self.sig_freq = [self.sig_freq]
            if not isinstance(self.sig_amp,list):
                self.sig_amp = [self.sig_amp]
            if not isinstance(self.sig_cm,list):
                self.sig_cm = [self.sig_cm]

            if not len(self.sig_freq) == len(self.sig_amp):
                self.print_log(msg='Length mismatch in sig_freq and sig_amp. Using first value for sig_amp.')
                self.sig_amp = list(np.ones((len(self.sig_freq)))*self.sig_amp[0])
            if not len(self.sig_freq) == len(self.sig_cm):
                self.print_log(msg='Length mismatch in sig_freq and sig_cm. Using first value for sig_cm.')
                self.sig_cm = list(np.ones((len(self.sig_freq)))*self.sig_cm[0])

            sig = None
            for i in range(len(self.sig_freq)):
                if self.coherent:
                    self.sig_freq[i] = self.get_coherent_fin(self.fs,self.sig_freq[i],self.nsamp)
                nsamp = self.nsamp + self.extra_sampl
                outmat = np.zeros((nsamp*self.sig_osr,2))
                tvec = np.linspace(0,nsamp/self.fs,num=nsamp*self.sig_osr, endpoint=False)
                if self.tau==0:
                    phase = self.sig_phase
                else:
                    phase = self.phase_from_delay()

                if sig is None:
                    sig = self.sig_amp[i]*np.sin(2.*np.pi*self.sig_freq[i]*tvec+phase*np.pi/180)+self.sig_cm[i]
                else:
                    sig += self.sig_amp[i]*np.sin(2.*np.pi*self.sig_freq[i]*tvec+phase*np.pi/180)+self.sig_cm[i]

            # This needs to be verified
            if self.snr > 0:
                k = 1/(10**(self.snr/20.0))
                sig = sig+np.random.normal(0,k*self.sig_amp[0],len(sig))
            outmat[:,0] = tvec+self.after
            outmat[:,1] = sig
            if self.sigtype == 'sine_samp':
                sine = np.copy(outmat)
                outmat = np.zeros((2*(self.nsamp+self.extra_sampl),2))
                # Timestamps
                outmat[0::2,0] = np.arange(0,(self.nsamp+self.extra_sampl)/self.fs,1/self.fs)+self.after
                outmat[1::2,0] = outmat[0::2,0] + 1 / self.fs - self.trise
                outmat[0::2,1] = sine[:,1]
                outmat[1::2,1] = sine[:,1]
                if not self.after==0:
                    outmat = np.vstack([(0,sine[0,1]),outmat])
        elif self.sigtype == 'bpnoise':
            # All of this is hard-coded or?
            self.nsamp += self.extra_sampl
            outmat = np.zeros((self.nsamp*self.sig_osr,2))
            tvec = np.linspace(0,self.nsamp/self.fs,num=self.nsamp*self.sig_osr, endpoint=False)
            order = 1000
            # sub 1-adc-nyquist
            desired = np.array([1, 0])
            bands = np.array([0, 0.05, 0.06, 1])
            bpf = scsig.remez(order,bands,desired,fs=2)
            noise = (self.sig_amp/6.6)*np.random.randn(self.nsamp*self.sig_osr)+self.sig_cm
            sig = scsig.lfilter(bpf,1,noise)
            outmat[:,0] = tvec+self.after
            outmat[:,1] = sig
        elif self.sigtype == 'pulse':
            if self.jitter_sd:
                self.print_log(type='I', msg='Applying jitter with SD of %.3g to the output signal!' % self.jitter_sd)
                jitter = np.random.normal(0,self.jitter_sd, 2*(self.nsamp+self.extra_sampl))
                if jitter[0] < 0 and abs(jitter[0] > self.after):
                    self.print_log(type='W', msg='First jitter sample makes first timestamp of the signal negative!')
            else:
                jitter = np.zeros(2*(self.nsamp+self.extra_sampl))
            outmat = np.zeros((4*(self.nsamp+self.extra_sampl),2))
            # Voltage levels
            outmat[::4,1].fill(self.low)
            outmat[1::4,1].fill(self.high)
            outmat[2::4,1].fill(self.high)
            outmat[3::4,1].fill(self.low)
            # Timestamps
            outmat[0::4,0] = np.arange(0,(self.nsamp+self.extra_sampl)/self.sig_freq,1/self.sig_freq)+self.after + jitter[::2]
            outmat[1::4,0] = outmat[0::4,0]+self.trise + jitter[::2]
            outmat[2::4,0] = outmat[1::4,0]+self.duty/self.sig_freq-self.trise + jitter[1::2]
            outmat[3::4,0] = outmat[2::4,0]+self.tfall + jitter[1::2]
            if not self.after==0:
                outmat = np.vstack([(0,self.low),outmat])
        elif self.sigtype=='sawtooth':
            self.print_log(type='W', msg='Sawtooth is currently experimental! Use with caution.')
            nsamp=self.nsamp+self.extra_sampl
            outmat = np.zeros((nsamp*self.sig_osr,2))
            tvec = np.linspace(0,self.nsamp/self.fs,num=nsamp*self.sig_osr, endpoint=False)
            sig = (np.mod(tvec, 1/self.sig_freq) * self.sig_freq)
            # Center around zero
            if self.slopetype=='falling':
                sig = 0.5 - sig
            else:
                sig -= 0.5
            sig *= self.sig_amp
            sig += self.sig_cm
            outmat[:,0] = tvec+self.after
            outmat[:,1] = sig
        else:
            self.print_log(type='F',msg='Signal type \'%s\' not supported.' % self.sigtype)

        self.IOS.Members['out'].Data=outmat

    def is_prime(self,n):
        if n % 2 == 0 and n > 2: 
            return False
        return all(n % i for i in range(3, int(np.sqrt(n)) + 1, 2))

    def get_coherent_fin(self,fs,fin,nsamp):
        success = False
        maxprime = 2**5
        while not success:
            try:
                a = np.arange(1, maxprime)
                foo = np.vectorize(self.is_prime)
                pbools = foo(a)
                primes = np.extract(pbools, a)
                window = np.floor(nsamp*fin/fs);
                window = primes[np.where(primes >= window)[0][0]];
                ratio = window/nsamp;
                success = True
            except:
                maxprime *= 2
        self.print_log(type='I',msg='Coherence set as: %g Hz -> %g Hz.' % (fin,ratio*fs))
        return ratio*fs

    def phase_from_delay(self):
        phase=-360*self.sig_freq*self.tau
        return phase

    def run(self,*arg):
        if self.model=='py':
            self.main()
        else: 
            pass

if __name__=="__main__":
    import matplotlib.pyplot as plt
    from  signal_generator import *
    from signal_analyser import signal_analyser
    import plot_format
    plot_format.set_style('ieeetran')
    #from  signal_generator.controller import controller as signal_generator_controller
    import pdb
    
    sig_freq = 1988e6 
    sig_amp = 0.5
    sig_cm = 0.5
    sig_phase = 0
    sig_osr = 100 
    nsamp = 2**10
    extra_samp=10
    jitter_pk = 45e-15
    jitter_sd = jitter_pk / 2
    fs = 4e9
    coherent=True

    sigtypes=['sine', 'sine_samp', 'sawtooth', 'pulse']

    duts=[signal_generator() for i in range(len(sigtypes)) ]
    duts[0].model='py'
    for i,dut in enumerate(duts): 
        dut.sigtype=sigtypes[i] 
        dut.sig_freq = sig_freq if dut.sigtype != 'pulse' else fs
        dut.sig_amp = sig_amp
        dut.sig_cm = sig_cm
        dut.sig_phase = sig_phase
        dut.sig_osr = sig_osr
        dut.snr=80
        dut.jitter_sd=jitter_sd
        dut.nsamp = nsamp
        dut.coherent=coherent
        dut.extra_sampl=extra_samp
        dut.fs = fs
        dut.init()
        dut.run()

    for k in range(len(duts)):
        outdata = duts[k].IOS.Members['out'].Data
        figure=plt.figure()
        plt.plot(outdata[:,0],outdata[:,1])
        plt.xlim(0,4/sig_freq)
        plt.grid(True);
        plt.show(block=False);
        # Test jitter
        if duts[k].sigtype=='pulse':
            tvec = duts[k].IOS.Members['out'].Data[:,0][2::4] # Falling edges
            sig = sig_amp*np.sin(2.*np.pi*duts[0].sig_freq[0]*tvec+sig_phase*np.pi/180)+sig_cm
            sigana=signal_analyser()
            sigana.IOS.Members['in'].Data=sig
            sigana.nsamp=nsamp
            sigana.fs=fs
            sigana.snr_order=20
            sigana.window=False
            sigana.annotate_harmonics=True
            sigana.annotations=['SFDR', 'SNR', 'SNDR', 'THD', 'ENOB', 'Range']
            sigana.rangeunit='V'
            sigana.ylim='noisecross'
            sigana.run()
            expsnr=-20*np.log10(2*np.pi*duts[0].sig_freq[0]*jitter_pk)
            obtsnr=sigana.snr
            print("Expected SNR (jitter) was: %.2f dB" % expsnr)
            print("Obtained SNR (jitter) was: %.2f dB" % obtsnr)
            diff=expsnr-obtsnr
            print("Diff: %.2f dB" %diff)
        # Test sine SNR
        if duts[k].sigtype=='sine':
            sigana=signal_analyser()
            sigana.IOS.Members['in']=duts[k].IOS.Members['out']
            sigana.nsamp=nsamp
            sigana.sig_osr=sig_osr
            sigana.fs=fs
            sigana.snr_order=20
            sigana.window=False
            sigana.annotate_harmonics=True
            sigana.annotations=['SFDR', 'SNR', 'SNDR', 'THD', 'ENOB', 'Range']
            sigana.rangeunit='V'
            sigana.ylim='noisecross'
            sigana.run()
            obtsnr=sigana.snr
            print("Expected SNR for sine was: %.2f dB" % duts[k].snr)
            print("Obtained SNR for sine was: %.2f dB" % obtsnr)
            diff=duts[k].snr-obtsnr
            print("Diff: %.2f dB" %diff)
    input()