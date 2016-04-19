"""
Particle-only geometry handler




"""

#-----------------------------------------------------------------------------
# Copyright (c) 2013, yt Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

import numpy as np
import os
import weakref

from yt.funcs import get_pbar, only_on_root
from yt.utilities.logger import ytLogger as mylog
from yt.data_objects.octree_subset import ParticleOctreeSubset
from yt.geometry.geometry_handler import Index, YTDataChunk
from yt.geometry.particle_oct_container import \
    ParticleOctreeContainer, ParticleBitmap
from yt.utilities.definitions import MAXLEVEL
from yt.utilities.io_handler import io_registry
from yt.utilities.parallel_tools.parallel_analysis_interface import \
    ParallelAnalysisInterface
from yt.extern.functools32 import lru_cache

from yt.data_objects.data_containers import data_object_registry
from yt.data_objects.octree_subset import ParticleOctreeSubset
from yt.data_objects.particle_container import ParticleContainer

class ParticleIndex(Index):
    """The Index subclass for particle datasets"""
    _global_mesh = False

    def __init__(self, ds, dataset_type):
        self.dataset_type = dataset_type
        self.dataset = weakref.proxy(ds)
        self.index_filename = self.dataset.parameter_filename
        self.directory = os.path.dirname(self.index_filename)
        self.float_type = np.float64
        super(ParticleIndex, self).__init__(ds, dataset_type)

    def _setup_geometry(self):
        self.regions = None
        mylog.debug("Initializing Particle Geometry Handler.")
        self._initialize_particle_handler()

    def get_smallest_dx(self):
        """
        Returns (in code units) the smallest cell size in the simulation.
        """
        ML = self.regions.index_order1 # was self.oct_handler.max_level
        dx = 1.0/(self.dataset.domain_dimensions*2**ML)
        dx = dx * (self.dataset.domain_right_edge -
                   self.dataset.domain_left_edge)
        return dx.min()

    def convert(self, unit):
        return self.dataset.conversion_factors[unit]

    def _initialize_particle_handler(self):
        self._setup_data_io()
        template = self.dataset.filename_template
        ndoms = self.dataset.file_count
        cls = self.dataset._file_class
        self.data_files = [cls(self.dataset, self.io, template % {'num':i}, i)
                           for i in range(ndoms)]
        N = min(len(4*self.data_files), 256) 
        self.ds.domain_dimensions[:] = N*(1<<self.ds.over_refine_factor)
        self.total_particles = sum(
                sum(d.total_particles.values()) for d in self.data_files)
        self._initialize_index()

    def _index_filename(self,o1,o2):
        import shutil
        # Uses parameter file
        fname_old = os.path.join(self.dataset.fullpath, 
                                 "index{}_{}.ewah".format(o1,o2))
        fname_new = self.index_filename + ".index{}_{}.ewah".format(o1,o2)
        if os.path.isfile(fname_old):
            shutil.move(fname_old,fname_new)
        return fname_new

    def _initialize_index(self, fname=None, noref=False,
                          order1=None, order2=None, dont_cache=False):
        ds = self.dataset
        only_on_root(mylog.info, "Allocating for %0.3e particles",
          self.total_particles)
        # No more than 256^3 in the region finder.
        N = self.ds.domain_dimensions / (1<<self.ds.over_refine_factor)
        self.regions = ParticleBitmap(
                ds.domain_left_edge, ds.domain_right_edge,
                len(self.data_files), 
                index_order1=order1, index_order2=order2)
        # Load indices from file if provided
        if fname is None: 
            fname = self._index_filename(self.regions.index_order1,
                                         self.regions.index_order2)
        try:
            rflag = self.regions.load_bitmasks(fname)
            if rflag == 0:
                self._initialize_owners()
                self.regions.save_bitmasks(fname)
            # else: # Save pcounts in file?
            #     self._initialize_owners()
        except IOError:
            self._initialize_coarse_index()
            if not noref:
                self._initialize_refined_index()
                self.regions.set_owners()
            else:
                self._initialize_owners()
            if not dont_cache:
                self.regions.save_bitmasks(fname)
        # These are now invalid, but I don't know what to replace them with:
        #self.max_level = self.oct_handler.max_level
        #self.dataset.max_level = self.max_level

    def _initialize_coarse_index(self):
        pb = get_pbar("Initializing coarse index ", len(self.data_files))
        for i, data_file in enumerate(self.data_files):
            pb.update(i)
            for pos in self.io._yield_coordinates(data_file):
                self.regions._coarse_index_data_file(pos, data_file.file_id)
        pb.finish()
        self.regions.find_collisions_coarse()

    def _initialize_refined_index(self):
        mask = self.regions.masks.sum(axis=1).astype('uint8')
        max_npart = max(sum(d.total_particles.values())
                        for d in self.data_files)
        sub_mi1 = np.zeros(max_npart, "uint64")
        sub_mi2 = np.zeros(max_npart, "uint64")
        pb = get_pbar("Initializing refined index", len(self.data_files))
        for i, data_file in enumerate(self.data_files):
            pb.update(i)
            for pos in self.io._yield_coordinates(data_file):
                self.regions._refined_index_data_file(pos, mask, 
                    sub_mi1, sub_mi2, data_file.file_id)
        pb.finish()
        self.regions.find_collisions_refined()

    def _initialize_owners(self):
        pb = get_pbar("Initializing owners", len(self.data_files))
        for i, data_file in enumerate(self.data_files):
            pb.update(i)
            for pos in self.io._yield_coordinates(data_file):
                self.regions._owners_data_file(pos, data_file.file_id)
        pb.finish()
        self.regions.set_owners()
            
    def _detect_output_fields(self):
        # TODO: Add additional fields
        dsl = []
        units = {}
        for dom in self.data_files:
            fl, _units = self.io._identify_fields(dom)
            units.update(_units)
            dom._calculate_offsets(fl)
            for f in fl:
                if f not in dsl: dsl.append(f)
        self.field_list = dsl
        ds = self.dataset
        ds.particle_types = tuple(set(pt for pt, ds in dsl))
        # This is an attribute that means these particle types *actually*
        # exist.  As in, they are real, in the dataset.
        ds.field_units.update(units)
        ds.particle_types_raw = ds.particle_types

    # def _chunk(self, dobj, chunking_style, ngz = 0, **kwargs):
    #     if ngz != 0 and chunking_style != "spatial":
    #         raise NotImplementedError
    #     if dobj._current_chunk is None:
    #         self._identify_base_chunk(dobj, ngz=ngz)
    #     if chunking_style == "all":
    #         return self._chunk_all(dobj, **kwargs)
    #     elif chunking_style == "spatial":
    #         return self._chunk_spatial(dobj, ngz, **kwargs)
    #     elif chunking_style == "io":
    #         return self._chunk_io(dobj, **kwargs)
    #     else:
    #         raise NotImplementedError

    def _identify_base_chunk(self, dobj, ngz=0):
        if self.regions is None:
            self._initialize_index()
        # Must check that chunk_info contains the right number of ghost zones
        buffer_ngz = getattr(dobj, "_buffer_ngz", ngz)
        chunk_ngz = getattr(dobj, "_chunk_ngz", ngz)
        if (getattr(dobj, "_chunk_info", None) is None) or (chunk_ngz != ngz):
            # Check for cached selector/buffer octtree subsets
            _chunk_info_selector = getattr(dobj, "_chunk_info_selector", None) 
            _chunk_info_buffer = getattr(dobj, "_chunk_info_buffer", None)
            if (ngz == 0) and (_chunk_info_selector is not None):
                dobj._chunk_info = _chunk_info_selector
            elif (ngz == buffer_ngz) and (_chunk_info_buffer is not None):
                dobj._chunk_info = _chunk_info_buffer
            else:
                data_files = getattr(dobj, "data_files", None)
                buffer_files = getattr(dobj, "buffer_files", None)
                dmask = getattr(dobj, "selector_mask", None)
                gmask = getattr(dobj, "buffer_mask", None)
                # Get info for new buffer
                if (data_files is None) or (ngz not in [buffer_ngz,0]):
                    (dfi, gzi), (dmask, gmask) = self.regions.identify_data_files(dobj.selector, ngz=ngz)
                    data_files = [self.data_files[i] for i in dfi]
                    buffer_files = [self.data_files[i] for i in gzi]
                    dobj.data_files = data_files
                    dobj.buffer_files = buffer_files
                    dobj.selector_mask = dmask
                    dobj.buffer_mask = gmask
                    dobj._buffer_ngz = ngz
                # NOTE: One fun thing about the way IO works is that it
                # consolidates things quite nicely.  So we should feel free to
                # create as many objects as part of the chunk as we want, since
                # it'll take the set() of them.  So if we break stuff up like this
                # here, we end up in a situation where we have the ability to break
                # things down further later on for buffer zones and the like.
                #
                # If the _current_chunk should never include ghost zones, 
                # _chunk_info should be set to _chunk_info_selector every time.
                # However, if creating the ParticleOctreeSubsets is costly,
                # this should remain to skip creating the _chunk_info_selector 
                # when it is not needed.
                dobj._chunk_info_selector = [ParticleOctreeSubset(dobj, df, self.ds,
                    over_refine_factor = self.ds.over_refine_factor,
                    selector_mask = dmask) for df in data_files]
                dobj._chunk_info = dobj._chunk_info_selector
                if ngz != 0:
                    dobj._chunk_info_buffer = [ParticleOctreeSubset(dobj, df, self.ds,
                        over_refine_factor = self.ds.over_refine_factor,
                        selector_mask = dmask, buffer_mask = gmask, 
                        base_grid = dobj._chunk_info_selector[i]) for i,df in enumerate(data_files)]
                    # No base_grid for files that only touch ghost zones
                    # dobj._chunk_info_buffer += [ParticleOctreeSubset(dobj, df, self.ds,
                    #     over_refine_factor = self.ds.over_refine_factor,
                    #     selector_mask = dmask, buffer_mask = gmask, 
                    #     base_grid = False) for i,df in enumerate(buffer_files)]
            dobj._chunk_ngz = 0
        dobj._current_chunk, = self._chunk_all(dobj)

    def _chunk_all(self, dobj):
        oobjs = getattr(dobj._current_chunk, "objs", dobj._chunk_info)
        yield YTDataChunk(dobj, "all", oobjs, None)

    def _chunk_spatial(self, dobj, ngz, sort = None, preload_fields = None,
                       ghost_particles = False):
        import time
        if ngz == 0 and ghost_particles:
            ngz = 1
        print 'ngz = {}, ghost_particles = {}'.format(ngz, ghost_particles)
        # We actually do not really use the data files except as input to the
        # ParticleOctreeSubset.
        # This is where we will perform cutting of the Octree and
        # load-balancing.  That may require a specialized selector object to
        # cut based on some space-filling curve index.
        if dobj._chunk_ngz == ngz:
            sobjs = getattr(dobj._current_chunk, "objs", dobj._chunk_info)
            for obj in sobjs:
                yield YTDataChunk(dobj, "spatial", [obj])
        else:
            if getattr(dobj,'_buffer_ngz',None) != ngz:
                t1 = time.time()
                gzi, gmask = self.regions.get_ghost_zones(dobj.selector,
                    ngz, dobj.selector_mask)
                t2 = time.time()
                print "{} seconds to get_ghost_zones".format(t2-t1)
                dobj.buffer_mask = gmask
                dobj.buffer_files = [self.data_files[i] for i in gzi]
                dobj._buffer_ngz = ngz
                dobj._chunk_info_buffer = None
            if getattr(dobj, "_chunk_info_buffer", None) is None:
                dobj._chunk_info_buffer = [ParticleOctreeSubset(dobj, df, self.ds,
                    over_refine_factor = self.ds.over_refine_factor,
                    selector_mask = dobj.selector_mask, 
                    buffer_mask = dobj.buffer_mask,
                    base_grid = dobj._chunk_info_selector[i]) for i,df in enumerate(dobj.data_files)]
                # No base_grid for files that only touch ghost zones
                # dobj._chunk_info_buffer += [ParticleOctreeSubset(dobj, df, self.ds,
                #     over_refine_factor = self.ds.over_refine_factor,
                #     selector_mask = dobj.selector_mask, 
                #     buffer_mask = dobj.buffer_mask,
                #     base_grid = False) for df in dobj.buffer_files]
            for obj in dobj._chunk_info_buffer:
                yield YTDataChunk(dobj, "spatial", [obj])

    def old_chunk_spatial(self, dobj, ngz, sort = None, preload_fields = None):
        (dfi, gzi), (dmask, gmask) = self.regions.identify_data_files(
                                dobj.selector)
        # We actually do not really use the data files except as input to the
        # ParticleOctreeSubset.
        # This is where we will perform cutting of the Octree and
        # load-balancing.  That may require a specialized selector object to
        # cut based on some space-filling curve index.
        for df in (self.data_files[i] for i in dfi):
            if ngz > 0:
                raise NotImplementedError
            else:
                oct_handler = self.regions.construct_octree(
                        df.file_id, dobj.selector, self.io, self.data_files,
                        (dfi, count, omask))
                g = ParticleOctreeSubset(dobj, df, self.ds,
                        over_refine_factor = self.ds.over_refine_factor)
            yield YTDataChunk(dobj, "spatial", [g])

    def _chunk_io(self, dobj, cache = True, local_only = False):
        oobjs = getattr(dobj._current_chunk, "objs", dobj._chunk_info)
        for container in oobjs:
            yield YTDataChunk(dobj, "io", [container], None, cache = cache)
