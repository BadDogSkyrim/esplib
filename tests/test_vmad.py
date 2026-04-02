"""Tests for VMAD (Virtual Machine Adapter) parser."""

import struct
import pytest

from esplib.vmad import (
    VmadData, VmadScript, VmadProperty, VmadObject,
    PROP_NONE, PROP_OBJECT, PROP_STRING, PROP_INT32,
    PROP_FLOAT, PROP_BOOL, PROP_OBJECT_ARRAY, PROP_STRING_ARRAY,
    PROP_INT32_ARRAY, PROP_FLOAT_ARRAY, PROP_BOOL_ARRAY,
    _Writer, _Reader,
)


def _build_simple_vmad(scripts=None, version=5, obj_format=2):
    """Build a minimal VMAD byte sequence."""
    w = _Writer()
    w.int16(version)
    w.int16(obj_format)
    scripts = scripts or []
    w.uint16(len(scripts))
    for name, props in scripts:
        w.wstring(name)
        w.uint8(0)  # flags = Local
        w.uint16(len(props))
        for pname, ptype, pflags, pvalue_bytes in props:
            w.wstring(pname)
            w.uint8(ptype)
            w.uint8(pflags)
            w._parts.append(pvalue_bytes)
    return w.get_bytes()


class TestVmadRoundTrip:


    def test_empty_vmad(self):
        """Empty VMAD with no scripts round-trips."""
        data = struct.pack('<hhH', 5, 2, 0)
        vmad = VmadData.parse(data)
        assert vmad.version == 5
        assert vmad.obj_format == 2
        assert len(vmad.scripts) == 0
        assert vmad.to_bytes() == data


    def test_single_script_no_properties(self):
        """Script with no properties round-trips."""
        data = _build_simple_vmad([('MyScript', [])])
        vmad = VmadData.parse(data)
        assert len(vmad.scripts) == 1
        assert vmad.scripts[0].name == 'MyScript'
        assert len(vmad.scripts[0].properties) == 0
        assert vmad.to_bytes() == data


    def test_object_property_v2(self):
        """Object property (format v2) round-trips."""
        obj_data = struct.pack('<HhI', 0, -1, 0x00014000)  # unused=0, alias=-1, formid
        data = _build_simple_vmad([
            ('TestScript', [
                ('MyObj', PROP_OBJECT, 1, obj_data),
            ])
        ])
        vmad = VmadData.parse(data)
        prop = vmad.scripts[0].properties[0]
        assert prop.name == 'MyObj'
        assert prop.type == PROP_OBJECT
        assert prop.value.form_id == 0x00014000
        assert prop.value.alias == -1
        assert vmad.to_bytes() == data


    def test_string_property(self):
        """String property round-trips."""
        s = 'Hello World'
        s_bytes = struct.pack('<H', len(s)) + s.encode('utf-8')
        data = _build_simple_vmad([
            ('TestScript', [
                ('MyStr', PROP_STRING, 1, s_bytes),
            ])
        ])
        vmad = VmadData.parse(data)
        assert vmad.scripts[0].properties[0].value == 'Hello World'
        assert vmad.to_bytes() == data


    def test_int32_property(self):
        data = _build_simple_vmad([
            ('TestScript', [
                ('MyInt', PROP_INT32, 1, struct.pack('<i', -42)),
            ])
        ])
        vmad = VmadData.parse(data)
        assert vmad.scripts[0].properties[0].value == -42
        assert vmad.to_bytes() == data


    def test_float_property(self):
        data = _build_simple_vmad([
            ('TestScript', [
                ('MyFloat', PROP_FLOAT, 1, struct.pack('<f', 3.14)),
            ])
        ])
        vmad = VmadData.parse(data)
        assert abs(vmad.scripts[0].properties[0].value - 3.14) < 0.001
        assert vmad.to_bytes() == data


    def test_bool_property(self):
        data = _build_simple_vmad([
            ('TestScript', [
                ('MyBool', PROP_BOOL, 1, struct.pack('<B', 1)),
            ])
        ])
        vmad = VmadData.parse(data)
        assert vmad.scripts[0].properties[0].value is True
        assert vmad.to_bytes() == data


    def test_object_array_property(self):
        """Array of objects round-trips."""
        w = _Writer()
        w.uint32(2)  # count
        w.uint16(0); w.int16(-1); w.uint32(0x100)  # obj 1
        w.uint16(0); w.int16(-1); w.uint32(0x200)  # obj 2
        arr_bytes = w.get_bytes()

        data = _build_simple_vmad([
            ('TestScript', [
                ('ObjArr', PROP_OBJECT_ARRAY, 1, arr_bytes),
            ])
        ])
        vmad = VmadData.parse(data)
        arr = vmad.scripts[0].properties[0].value
        assert len(arr) == 2
        assert arr[0].form_id == 0x100
        assert arr[1].form_id == 0x200
        assert vmad.to_bytes() == data


    def test_int32_array_property(self):
        w = _Writer()
        w.uint32(3)
        w.int32(10); w.int32(-20); w.int32(30)
        arr_bytes = w.get_bytes()

        data = _build_simple_vmad([
            ('TestScript', [
                ('IntArr', PROP_INT32_ARRAY, 1, arr_bytes),
            ])
        ])
        vmad = VmadData.parse(data)
        arr = vmad.scripts[0].properties[0].value
        assert arr == [10, -20, 30]
        assert vmad.to_bytes() == data


    def test_multiple_scripts_and_properties(self):
        """Multiple scripts with mixed property types round-trip."""
        obj_data = struct.pack('<hHI', -1, 0, 0x500)
        data = _build_simple_vmad([
            ('Script1', [
                ('IntProp', PROP_INT32, 1, struct.pack('<i', 99)),
                ('StrProp', PROP_STRING, 1,
                 struct.pack('<H', 3) + b'abc'),
            ]),
            ('Script2', [
                ('ObjProp', PROP_OBJECT, 1, obj_data),
            ]),
        ])
        vmad = VmadData.parse(data)
        assert len(vmad.scripts) == 2
        assert vmad.scripts[0].name == 'Script1'
        assert len(vmad.scripts[0].properties) == 2
        assert vmad.scripts[1].name == 'Script2'
        assert vmad.to_bytes() == data


class TestVmadAccess:


    def test_get_script(self):
        data = _build_simple_vmad([('TestScript', []), ('Other', [])])
        vmad = VmadData.parse(data)
        assert vmad.get_script('TestScript').name == 'TestScript'
        assert vmad.get_script('testscript').name == 'TestScript'
        assert vmad.get_script('nonexistent') is None


    def test_get_property(self):
        data = _build_simple_vmad([
            ('TestScript', [
                ('MyProp', PROP_INT32, 1, struct.pack('<i', 42)),
            ])
        ])
        vmad = VmadData.parse(data)
        script = vmad.get_script('TestScript')
        assert script.get_property('MyProp').value == 42
        assert script.get_property('myprop').value == 42
        assert script.get_property('nonexistent') is None


class TestVmadObjectFormatV1:


    def test_object_v1(self):
        """Object property in format v1 (formid, alias, unused)."""
        w = _Writer()
        w.int16(5)   # version
        w.int16(1)   # obj_format = 1
        w.uint16(1)  # script count
        w.wstring('Test')
        w.uint8(0)
        w.uint16(1)  # prop count
        w.wstring('Obj')
        w.uint8(PROP_OBJECT)
        w.uint8(1)
        # v1 object: formid, alias, unused
        w.uint32(0x300)
        w.int16(5)
        w.uint16(0)
        data = w.get_bytes()

        vmad = VmadData.parse(data)
        assert vmad.obj_format == 1
        obj = vmad.scripts[0].properties[0].value
        assert obj.form_id == 0x300
        assert obj.alias == 5
        assert vmad.to_bytes() == data


class TestVmadNoneProperty:


    def test_none_property(self):
        data = _build_simple_vmad([
            ('TestScript', [
                ('NoProp', PROP_NONE, 1, b''),
            ])
        ])
        vmad = VmadData.parse(data)
        assert vmad.scripts[0].properties[0].value is None
        assert vmad.to_bytes() == data
