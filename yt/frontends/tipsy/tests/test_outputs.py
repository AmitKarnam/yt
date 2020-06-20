from collections import OrderedDict

from yt.testing import \
    assert_equal, \
    requires_file, \
    ParticleSelectionComparison
from yt.utilities.answer_testing.framework import \
    requires_ds, \
    data_dir_load, \
    sph_answer, \
    create_obj, \
    FieldValuesTest, \
    PixelizedProjectionValuesTest
from yt.frontends.tipsy.api import TipsyDataset

_fields = (("deposit", "all_density"),
           ("deposit", "all_count"),
           ("deposit", "DarkMatter_density"),
)

pkdgrav = "halo1e11_run1.00400/halo1e11_run1.00400"
pkdgrav_cosmology_parameters = dict(current_redshift = 0.0,
                                omega_lambda = 0.728,
                                omega_matter = 0.272,
                                hubble_constant = 0.702)
pkdgrav_kwargs = dict(cosmology_parameters = pkdgrav_cosmology_parameters,
                  unit_base = {'length': (60.0, "Mpccm/h")})
@requires_ds(pkdgrav, big_data = True, file_check = True)
def test_pkdgrav():
    ds = data_dir_load(pkdgrav, TipsyDataset, (), kwargs = pkdgrav_kwargs)
    assert_equal(str(ds), "halo1e11_run1.00400")
    dso = [ None, ("sphere", ("c", (0.3, 'unitary')))]
    dd = ds.all_data()
    assert_equal(dd["Coordinates"].shape, (26847360, 3))
    tot = sum(dd[ptype,"Coordinates"].shape[0]
              for ptype in ds.particle_types if ptype != "all")
    assert_equal(tot, 26847360)
    psc = ParticleSelectionComparison(ds)
    psc.run_defaults()
    for dobj_name in dso:
        for field in _fields:
            for axis in [0, 1, 2]:
                for weight_field in [None]:
                    yield PixelizedProjectionValuesTest(
                        ds, axis, field, weight_field,
                        dobj_name)
            yield FieldValuesTest(ds, field, dobj_name)
        dobj = create_obj(ds, dobj_name)
        s1 = dobj["ones"].sum()
        s2 = sum(mask.sum() for block, mask in dobj.blocks)
        assert_equal(s1, s2)

gasoline_dmonly = "agora_1e11.00400/agora_1e11.00400"
@requires_ds(gasoline_dmonly, big_data = True, file_check = True)
def test_gasoline_dmonly():
    cosmology_parameters = dict(current_redshift = 0.0,
                                omega_lambda = 0.728,
                                omega_matter = 0.272,
                                hubble_constant = 0.702)
    kwargs = dict(cosmology_parameters = cosmology_parameters,
                  unit_base = {'length': (60.0, "Mpccm/h")})
    ds = data_dir_load(gasoline_dmonly, TipsyDataset, (), kwargs)
    assert_equal(str(ds), "agora_1e11.00400")
    dso = [ None, ("sphere", ("c", (0.3, 'unitary')))]
    dd = ds.all_data()
    assert_equal(dd["Coordinates"].shape, (10550576, 3))
    tot = sum(dd[ptype,"Coordinates"].shape[0]
              for ptype in ds.particle_types if ptype != "all")
    assert_equal(tot, 10550576)
    psc = ParticleSelectionComparison(ds)
    psc.run_defaults()
    for dobj_name in dso:
        for field in _fields:
            for axis in [0, 1, 2]:
                for weight_field in [None]:
                    yield PixelizedProjectionValuesTest(
                        ds, axis, field, weight_field,
                        dobj_name)
            yield FieldValuesTest(ds, field, dobj_name)
        dobj = create_obj(ds, dobj_name)
        s1 = dobj["ones"].sum()
        s2 = sum(mask.sum() for block, mask in dobj.blocks)
        assert_equal(s1, s2)

tg_fields = OrderedDict(
    [
        (('gas', 'density'), None),
        (('gas', 'temperature'), None),
        (('gas', 'temperature'), ('gas', 'density')),
        (('gas', 'velocity_magnitude'), None),
        (('gas', 'Fe_fraction'), None),
        (('Stars', 'Metals'), None),
    ]
)

tipsy_gal = 'TipsyGalaxy/galaxy.00300'
@requires_ds(tipsy_gal)
def test_tipsy_galaxy():
    ds = data_dir_load(tipsy_gal, kwargs = {'bounding_box': [[-2000, 2000],
                                                             [-2000, 2000],
                                                             [-2000, 2000]]})
    # These tests should be re-enabled.  But the holdup is that the region
    # selector does not offset by domain_left_edge, and we have inelegant
    # selection using bboxes.
    #psc = ParticleSelectionComparison(ds)
    #psc.run_defaults()
    for test in sph_answer(ds, 'galaxy.00300', 315372, tg_fields):
        test_tipsy_galaxy.__name__ = test.description
        yield test

@requires_file(gasoline_dmonly)
@requires_file(pkdgrav)
def test_TipsyDataset():
    assert isinstance(data_dir_load(pkdgrav, kwargs = pkdgrav_kwargs), TipsyDataset)
    assert isinstance(data_dir_load(gasoline_dmonly), TipsyDataset)


@requires_file(tipsy_gal)
def test_tipsy_index():
    ds = data_dir_load(tipsy_gal)
    sl = ds.slice('z', 0.0)
    assert sl['gas', 'density'].shape[0]!=0
