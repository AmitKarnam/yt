import numpy as np

from yt.testing import \
    assert_equal, \
    fake_sph_orientation_ds

# The number of particles along each slice axis at that coordinate
SLICE_ANSWERS = {
    ('x', 0): 6,
    ('x', 0.5): 0,
    ('x', 1): 1,
    ('y', 0): 5,
    ('y', 1): 1,
    ('y', 2): 1,
    ('z', 0): 4,
    ('z', 1): 1,
    ('z', 2): 1,
    ('z', 3): 1,
}

def test_slice():
    ds = fake_sph_orientation_ds()
    for (ax, coord), answer in SLICE_ANSWERS.items():
        # test that we can still select particles even if we offset the slice
        # within each particle's smoothing volumes
        for i in range(-1, 2):
            sl = ds.slice(ax, coord + i*0.1)
            assert_equal(sl['gas', 'density'].shape[0], answer)


REGION_ANSWERS = {
    ((-4, -4, -4), (4, 4, 4)): 7,
    ((0, 0, 0), (4, 4, 4)): 7,
    ((1, 0, 0), (4, 4, 4)): 1,
    ((0, 1, 0), (4, 4, 4)): 2,
    ((0, 0, 1), (4, 4, 4)): 3,
    ((0, 0, 0), (4, 4, 2)): 6,
    ((0, 0, 0), (4, 4, 1)): 5,
    ((0, 0, 0), (4, 1, 4)): 6,
    ((0, 0, 0), (1, 1, 4)): 6,
}

def test_region():
    ds = fake_sph_orientation_ds()
    for (left_edge, right_edge), answer in REGION_ANSWERS.items():
        # test that regions enclosing a particle's smoothing region
        # correctly select SPH particles
        for i in range(-1, 2):
            for j in range(-1, 2):
                le = np.array([le + i*0.1 for le in left_edge])
                re = np.array([re + j*0.1 for re in right_edge])

                # check if we went off the edge of the domain
                whl = le < ds.domain_left_edge
                le[whl] = ds.domain_left_edge[whl]
                whr = re > ds.domain_right_edge
                re[whr] = ds.domain_right_edge[whr]

                reg = ds.box(le, re)
                assert_equal(reg['gas', 'density'].shape[0], answer)


SPHERE_ANSWERS = {
    ((0, 0, 0), 4): 7,
    ((0, 0, 0), 3): 7,
    ((0, 0, 0), 2): 6,
    ((0, 0, 0), 1): 4,
    ((0, 0, 0), 0.5): 1,
    ((1, 0, 0), 0.5): 1,
    ((1, 0, 0), 1.0): 2,
    ((0, 1, 0), 1.0): 3,
    ((0, 0, 1), 1.0): 3,
}

def test_sphere():
    ds = fake_sph_orientation_ds()
    for (center, radius), answer in SPHERE_ANSWERS.items():
        # test that spheres enclosing a particle's smoothing region
        # correctly select SPH particles
        for i in range(-1, 2):
            for j in range(-1, 2):
                cent = np.array([c + i*0.1 for c in center])
                rad = radius + 0.1*j
                sph = ds.sphere(cent, rad)
                assert_equal(sph['gas', 'density'].shape[0], answer)


DISK_ANSWERS = {
    ((0, 0, 0), (0, 0, 1), 4, 3): 7,
    ((0, 0, 0), (0, 0, 1), 4, 2): 6,
    ((0, 0, 0), (0, 0, 1), 4, 1): 5,
    ((0, 0, 0), (0, 0, 1), 4, 0.5): 4,
    ((0, 0, 0), (0, 1, 0), 4, 3): 7,
    ((0, 0, 0), (0, 1, 0), 4, 2): 7,
    ((0, 0, 0), (0, 1, 0), 4, 1): 6,
    ((0, 0, 0), (0, 1, 0), 4, 0.5): 5,
    ((0, 0, 0), (1, 0, 0), 4, 3): 7,
    ((0, 0, 0), (1, 0, 0), 4, 2): 7,
    ((0, 0, 0), (1, 0, 0), 4, 1): 7,
    ((0, 0, 0), (1, 0, 0), 4, 0.5): 6,
    ((0, 0, 0), (1, 1, 1), 1, 1): 4,
    ((-0.5, -0.5, -0.5), (1, 1, 1), 4, 4): 7,
}

def test_disk():
    ds = fake_sph_orientation_ds()
    for (center, normal, radius, height), answer in DISK_ANSWERS.items():
        # test that disks enclosing a particle's smoothing region
        # correctly select SPH particles
        for i in range(-1, 2):
            cent = np.array([c + i*0.1 for c in center])
            disk = ds.disk(cent, normal, radius, height)
            assert_equal(disk['gas', 'density'].shape[0], answer)


RAY_ANSWERS = {
    ((0, 0, 0), (3, 0, 0)): 2,
    ((0, 0, 0), (0, 3, 0)): 3,
    ((0, 0, 0), (0, 0, 3)): 4,
    ((0, 1, 0), (0, 2, 0)): 2,
    ((1, 0, 0), (0, 2, 0)): 2,
    ((0.5, 0.5, 0.5), (0.5, 0.5, 3.5)): 0,
}

def test_ray():
    ds = fake_sph_orientation_ds()
    for (start_point, end_point), answer in RAY_ANSWERS.items():
        for i in range(-1, 2):
            start = np.array([s + i*0.1 for s in start_point])
            end = np.array([e + i*0.1 for e in end_point])
            ray = ds.ray(start, end)
            assert_equal(ray['gas', 'density'].shape[0], answer)


CUTTING_ANSWERS = {
    ((1, 0, 0), (0, 0, 0)): 6,
    ((0, 1, 0), (0, 0, 0)): 5,
    ((0, 0, 1), (0, 0, 0)): 4,
    ((1, 1, 1), (1./3, 1./3, 1./3)): 3,
    ((1, 1, 1), (2./3, 2./3, 2./3)): 2,
    ((1, 1, 1), (1, 1, 1)): 1,
}

def test_cutting():
    ds = fake_sph_orientation_ds()
    for (normal, center), answer in CUTTING_ANSWERS.items():
        for i in range(-1, 2):
            cen = [c + 0.1*c for c in center]
            cut = ds.cutting(normal, cen)
            assert_equal(cut['gas', 'density'].shape[0], answer)

def test_chained_selection():
    ds = fake_sph_orientation_ds()

    for (center, radius), answer in SPHERE_ANSWERS.items():
        sph = ds.sphere(center, radius)
        region = ds.box(ds.domain_left_edge, ds.domain_right_edge,
                        data_source=sph)
        assert_equal(region['gas', 'density'].shape[0], answer)

def test_boolean_selection():
    ds = fake_sph_orientation_ds()

    sph = ds.sphere([0, 0, 0], 0.5)

    sph2 = ds.sphere([1, 0, 0], 0.5)

    reg = ds.all_data()

    neg = reg - sph

    assert_equal(neg['gas', 'density'].shape[0], 6)

    plus = sph + sph2

    assert_equal(plus['gas', 'density'].shape[0], 2)

    intersect = sph & sph2

    assert_equal(intersect['gas', 'density'].shape[0], 0)

    intersect = reg & sph2

    assert_equal(intersect['gas', 'density'].shape[0], 1)

    exclusive = sph ^ sph2

    assert_equal(exclusive['gas', 'density'].shape[0], 2)

    exclusive = sph ^ reg

    assert_equal(exclusive['gas', 'density'].shape[0], 6)

    intersect = ds.intersection([sph, sph2])

    assert_equal(intersect['gas', 'density'].shape[0], 0)

    intersect = ds.intersection([reg, sph2])

    assert_equal(intersect['gas', 'density'].shape[0], 1)

    union = ds.union([sph, sph2])

    assert_equal(union['gas', 'density'].shape[0], 2)
