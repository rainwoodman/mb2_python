"""
File I/O related to the gadget snapshot MBII files
"""

from __future__ import print_function, division
import sys
import os
import numpy as np
import time
import pygadgetreader as pyg
from readgadget.modules import header as pyg_header
from readgadget.modules.common import pollOptions, initUnits, gadgetPrinter
from readgadget.modules import gadget1, gadget2
from mb2_python.data import BLOCKORDERING, pNames


__all__ = ['snapPath', 'snapHeader', 'getNumPart', 'readSnap']
__author__ = ['Duncan Campbell']


def snapPath(basePath, snapNum, chunkNum=None):
    """
    Return absolute path to a snapshot file
    """
    if chunkNum is None:
        chunkNum = 0

    snapPath = basePath + '/snapdir'
    snapPath += '/snapdir_' + str(snapNum).zfill(3) + '/'
    filePath = snapPath + 'snapshot_' + str(snapNum).zfill(3)
    filePath += '.' + str(chunkNum)
    return filePath


def snapHeader(basePath, snapNum, chunkNum=None):
    """
    Return snapshot header
    """

    if chunkNum is None:
        chunkNum = 0

    fname = snapPath(basePath, snapNum, chunkNum)
    header = pyg.readheader(fname, 'header')
    return header


def getNumPart(header):
    """
    Calculate number of particles of all types given a snapshot header.
    """
    nTypes = 6

    nPart = np.zeros(nTypes, dtype=np.int64)
    for j in range(nTypes):
        nPart[j] = header['npartTotal'][j]

    return nPart


def readSnap(basePath, snapNum, partType, fields=None, chunkNum=None, sq=True, sample_rate=1.0, seed=None, verbose=False, **kwargs):
    """
    Load a subset of fields for all particles/cells of a given particle type

    Parameters
    ----------
    basePath : string
        base path

    snapNum : int
        snapshot number

    partType : int
        particle type

    fields : list, optional
        list of field names (strings)

    chunkNum : int, optional
        chunk number, must be in the range [0,1024]. 
        If None, all chunks are read. 
        If a list of legnth 2 is passed, the range is read in

    sq : Boolean, optional
        If True, return a numpy array instead of a dict if len(fields)==1.

    sample_rate : float, optional
        random sampling rate, must be in the range (0,1.0].  
        Note that for sampling purposes, each particle is weighed "evenly".

    seed : int
        random seed used when sample_rate<1.0

    Returns
    -------
    dict : dictionary
        dictionary storing requested fields

    Notes
    -----
    The Gadget snapshot files for MBII use a custom block ordering.
    This block ordering is defined in ``mb2_python.data.py``.
    In order to use the pygadgetreader module,
    the block ordering attribute of the header object is replaced
    within this function.
    """

    # check to see if requested file exists
    if not os.path.isdir(basePath):
        msg = ('`basePath` does not point to directory on this machine!')
        raise ValueError(msg)
    if not os.path.exists(snapPath(basePath, snapNum, chunkNum)):
        msg = ('snapshot file not found: {0}'.format(snapPath(basePath, snapNum, chunkNum)))
        raise ValueError(msg)

    # enforce a reasonable random sampling rate
    assert (sample_rate<=1.0) & (sample_rate>0.0)

    # load header information
    snap = snapPath(basePath, snapNum, chunkNum=chunkNum)
    h = pyg_header.Header(snap, 0, kwargs)
    h.BLOCKORDER = BLOCKORDERING['CMU']

    f = h.f

    # intialize dictionary to store results
    return_dict = {}
    for key in fields:
        if key in h.BLOCKORDER.keys():
            return_dict[key] = None
        else:
            msg = ('key: {0}, not available.'.format(key))
            raise ValueError(msg)
    
    if chunkNum is None:
        min_chunk = 0
        max_chunk = h.nfiles
    elif isinstance(chunkNum, list):
        if len != 2:
            msg = ('chunkNum keyword not valid.'.format(key))
            raise ValueError(msg)
        assert chunkNum[0]<chunkNum[1]
    else:
        min_chunk = int(chunkNum)
        max_chunk = min_chunk+1

    f.close()
    
    if verbose:
        avg_time_per_chunk = 0.0
        num_chunks_read = 0
        start_time = time.time()

    for i in range(min_chunk, max_chunk):
        if verbose:
            step_start_time = time.time()
            print("reading in chunk {0} out {1}".format(i+1, max_chunk))
        for field in fields:
            h = pyg_header.Header(snap, i, kwargs)
            h.BLOCKORDER = BLOCKORDERING['CMU']
            f = h.f
            d, p = pollOptions(h, kwargs, field, partType)
            h.reading = d
            initUnits(h)

            if h.fileType == 'gadget1':
                arr = gadget1.gadget_read(f, h, p, d)
            elif h.fileType == 'gadget2':
                arr = gadget2.gadget_type2_read(f, h, p)

            if sample_rate < 1.0:
                n_ptcls = len(arr)
                mask = down_sample_ptcls(n_ptcls, rate=0.01, seed=seed)
                arr = arr[mask]

            # put arrays together
            if return_dict[field] is None:
                return_dict[field] = arr
            else:
                return_dict[field] = np.concatenate((return_dict[key], arr))

            if verbose:
                num_chunks_read += 1
                time_so_far = time.time() - start_time
                avg_time_per_chunk = (1.0*time_so_far)/(1.0*num_chunks_read)
                num_chunks_to_go = (max_chunk - min_chunk) - num_chunks_read
                print("     time to read chunk: {0} seconds.".format(time.time()-step_start_time))
                print("     estimated time remaining: {0} minutes".format(avg_time_per_chunk*num_chunks_to_go/60.0))

        f.close()

    # only a single field--return the array instead of a single item dict
    if sq and len(fields) == 1:
        return return_dict[fields[0]]

    f.close()

    return return_dict


def down_sample_ptcls(n_ptcls, rate=0.01, seed=None):
    """
    return a mask array to randomly down-sample
    
    Parameters
    ----------
    n_ptcls : int
        number of parrticles
    
    rate : float
        sampling rate--must be in the range [0,1].
    
    Returns
    -------
    mask : numpy.array
        boolean array
    """

    if seed is not None:
        np.random.seed(seed)

    ran = np.random.random(n_ptcls)
    return ran<rate


