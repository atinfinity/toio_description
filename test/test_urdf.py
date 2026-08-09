# Copyright (C) 2026 atinfinity
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
import xml.etree.ElementTree as ElementTree

import pytest
import xacro

PACKAGE_DIR = Path(__file__).resolve().parents[1]
XACRO_FILE = PACKAGE_DIR / 'robot' / 'toio.urdf.xacro'

EXPECTED_LINKS = {
    'center',
    'base_footprint',
    'base_link',
    'base_r_drive_wheel_link',
    'base_l_drive_wheel_link',
    'rear_caster_link',
    'led_link',
}

EXPECTED_JOINTS = {
    'base_footprint_joint': ('fixed', 'center', 'base_footprint'),
    'base_link_joint': ('fixed', 'base_footprint', 'base_link'),
    'base_r_drive_wheel_joint': ('continuous', 'base_link', 'base_r_drive_wheel_link'),
    'base_l_drive_wheel_joint': ('continuous', 'base_link', 'base_l_drive_wheel_link'),
    'rear_caster_joint': ('fixed', 'base_footprint', 'rear_caster_link'),
    'led_joint': ('fixed', 'center', 'led_link'),
}

# hardware constants shared with the toio_ros2 node
# https://toio.github.io/toio-spec/en/docs/hardware_shape
WHEEL_SEPARATION = 0.0266
WHEEL_RADIUS = 0.00625

# The lamp is the ball on the bottom of the cube, which the bottom view puts
# 11.1 mm behind the centre, on the centre line.
# https://toio.github.io/toio-spec/en/docs/hardware_components
LAMP_OFFSET_X = -0.0111
LAMP_RADIUS = 0.0035


@pytest.fixture(scope='module')
def robot():
    doc = xacro.process_file(str(XACRO_FILE))
    return ElementTree.fromstring(doc.toxml())


def test_xacro_expands_to_valid_xml(robot):
    assert robot.tag == 'robot'
    assert robot.get('name') == 'toio'


def test_expected_links_exist(robot):
    links = {link.get('name') for link in robot.findall('link')}
    assert links == EXPECTED_LINKS


def test_expected_joints_exist(robot):
    joints = {
        joint.get('name'): (
            joint.get('type'),
            joint.find('parent').get('link'),
            joint.find('child').get('link'),
        )
        for joint in robot.findall('joint')
    }
    assert joints == EXPECTED_JOINTS


def test_joints_connect_existing_links(robot):
    links = {link.get('name') for link in robot.findall('link')}
    for joint in robot.findall('joint'):
        assert joint.find('parent').get('link') in links
        assert joint.find('child').get('link') in links


def test_drive_wheels_are_symmetric(robot):
    origins = {}
    for joint in robot.findall('joint'):
        name = joint.get('name')
        if name.endswith('_drive_wheel_joint'):
            origins[name] = [float(v) for v in joint.find('origin').get('xyz').split()]
            assert joint.find('axis').get('xyz') == '0 0 1'
    right = origins['base_r_drive_wheel_joint']
    left = origins['base_l_drive_wheel_joint']
    assert right[0] == left[0]
    assert right[1] == pytest.approx(-left[1])
    assert right[2] == left[2]
    assert abs(right[1] - left[1]) == pytest.approx(WHEEL_SEPARATION)


def test_wheel_radius_matches_hardware_spec(robot):
    for link in robot.findall('link'):
        if link.get('name').endswith('_drive_wheel_link'):
            cylinder = link.find('visual/geometry/cylinder')
            assert float(cylinder.get('radius')) == pytest.approx(WHEEL_RADIUS)


def test_inertials_are_positive(robot):
    for link in robot.findall('link'):
        inertial = link.find('inertial')
        if inertial is None:
            continue
        name = link.get('name')
        assert float(inertial.find('mass').get('value')) > 0.0, name
        inertia = inertial.find('inertia')
        for axis in ('ixx', 'iyy', 'izz'):
            assert float(inertia.get(axis)) > 0.0, f'{name} {axis}'


def test_mesh_reference_resolves(robot):
    mesh = robot.find("link[@name='center']/visual/geometry/mesh")
    filename = mesh.get('filename')
    prefix = 'package://toio_description/'
    assert filename.startswith(prefix)
    assert (PACKAGE_DIR / filename[len(prefix):]).is_file()


@pytest.fixture(scope='module')
def plugins(robot):
    return {
        plugin.get('name'): plugin
        for gazebo in robot.findall('gazebo')
        for plugin in gazebo.findall('plugin')
    }


def test_diff_drive_plugin_matches_hardware_spec(plugins):
    diff_drive = plugins['gz::sim::systems::DiffDrive']
    assert diff_drive.find('left_joint').text == 'base_l_drive_wheel_joint'
    assert diff_drive.find('right_joint').text == 'base_r_drive_wheel_joint'
    assert float(diff_drive.find('wheel_separation').text) == pytest.approx(WHEEL_SEPARATION)
    assert float(diff_drive.find('wheel_radius').text) == pytest.approx(WHEEL_RADIUS)


def test_led_plugin_is_scoped_to_the_model(plugins):
    led = plugins['toio_gazebo::ToioLedSystem']
    assert led.get('filename') == 'ToioLedSystem'
    # Same scoping as DiffDrive, so that spawning several cubes does not make
    # them share a topic.
    assert led.find('topic').text == '/model/toio/led'
    assert led.find('led_duration_ms').text == '0'


def test_led_marker_matches_only_the_led_visual(robot, plugins):
    # The LED joint is fixed, so the SDF conversion lumps it into "center" and
    # rewrites the visual name. The plugin therefore matches the visual by
    # substring, which only works while nothing else in the model matches.
    marker = plugins['toio_gazebo::ToioLedSystem'].find('led_visual').text

    named_visuals = [
        visual.get('name')
        for link in robot.findall('link')
        for visual in link.findall('visual')
        if visual.get('name') is not None
    ]
    assert [name for name in named_visuals if marker in name] == [marker]

    # Visuals without a name are named after their link during the conversion.
    unnamed_visual_links = [
        link.get('name')
        for link in robot.findall('link')
        for visual in link.findall('visual')
        if visual.get('name') is None
    ]
    assert [name for name in unnamed_visual_links if marker in name] == []


def test_led_is_the_ball_on_the_bottom_of_the_cube(robot):
    origin = robot.find("joint[@name='led_joint']/origin")
    x, y, z = (float(value) for value in origin.get('xyz').split())
    assert x == pytest.approx(LAMP_OFFSET_X, abs=0.0005)
    assert y == pytest.approx(0.0)

    sphere = robot.find("link[@name='led_link']/visual/geometry/sphere")
    assert sphere is not None, 'the lamp of the real cube is a ball'
    radius = float(sphere.get('radius'))
    assert radius == pytest.approx(LAMP_RADIUS, abs=0.0005)

    # The ball reaches the ground, which is z = 0 in the frame of "center",
    # so that the cap below the flat underside of the body is visible.
    assert z - radius <= 0.0
    assert z > 0.0
