#!/usr/bin/env python3
"""Check the contributed FLX4 full preset and its RX3 browser bindings."""

from collections import Counter
from hashlib import sha256
from pathlib import Path
import xml.etree.ElementTree as ET


directory = Path(__file__).resolve().parents[1] / "controllers/Pioneer_DDJ_FLX4_RX3"
root = ET.parse(directory / "Pioneer-DDJ-FLX4-RX3.midi.xml").getroot()
assert root.tag == "MixxxControllerPreset"
assert root.find("./controller").get("id") == "DDJ-FLX4"

scripts = {entry.get("filename") for entry in root.findall("./controller/scriptfiles/file")}
assert scripts == {"Pioneer-DDJ-FLX4-script.js", "Pioneer-DDJ-FLX4-RX3-Browser.js", "Nautic-RX3-Encoder-FLX4.js"}
assert all((directory / name).is_file() for name in scripts)

controls = root.findall("./controller/controls/control")
assert len(controls) >= 200  # Keep the original full controller mapping.
assert len(root.findall("./controller/outputs/output")) >= 100
messages = [(control.findtext("status"), control.findtext("midino")) for control in controls]
assert not [message for message, count in Counter(messages).items() if count > 1]
added_messages = {("0x96", "0x68"), ("0x96", "0x7A"),
                  ("0x96", "0x00"), ("0x96", "0x08")}
original_messages = sorted(set(messages) - added_messages)
original_signature = sha256(
    "\n".join(f"{status}:{number}" for status, number in original_messages).encode()
).hexdigest()
assert original_signature == "1a78d846b07b7263cab4f455251ed4b98692065a99ece68717d29a97cb7849ed", \
    "An original Mixxx 2.5.6 FLX4 MIDI message was lost or changed"

expected = {
    ("0xB6", "0x40"): ("[Library]", "NauticFLX4Browser.turn"),
    ("0x96", "0x41"): ("[Library]", "NauticFLX4Browser.enter"),
    ("0x96", "0x42"): ("[Library]", "NauticFLX4Browser.shortcut"),
    ("0x96", "0x68"): ("[Library]", "NauticFLX4Browser.source"),
    ("0x96", "0x7A"): ("[Library]", "NauticFLX4Browser.view"),
    ("0x96", "0x46"): ("[Channel1]", "LoadSelectedTrack"),
    ("0x96", "0x47"): ("[Channel2]", "LoadSelectedTrack"),
    ("0xB4", "0x02"): ("[EffectRack1_EffectUnit1]", "PioneerDDJFLX4.beatFxLevelDepthRotate"),
    ("0x94", "0x10"): ("[EffectRack1_EffectUnit1]", "PioneerDDJFLX4.beatFxChannel1"),
    ("0x95", "0x11"): ("[EffectRack1_EffectUnit1]", "PioneerDDJFLX4.beatFxChannel2"),
    ("0x94", "0x47"): ("[EffectRack1_EffectUnit1]", "PioneerDDJFLX4.beatFxOnOffPressed"),
    ("0x95", "0x47"): ("[EffectRack1_EffectUnit1]", "PioneerDDJFLX4.beatFxOnOffPressed"),
    ("0x94", "0x4A"): ("[EffectRack1_EffectUnit1]", "PioneerDDJFLX4.beatFxLeftPressed"),
    ("0x94", "0x4B"): ("[EffectRack1_EffectUnit1]", "PioneerDDJFLX4.beatFxRightPressed"),
    ("0x96", "0x00"): ("[RX3SmartFx]", "PioneerDDJFLX4.smartFxPressed"),
    ("0x96", "0x08"): ("[RX3SmartFx]", "PioneerDDJFLX4.smartFxPresetPressed"),
    ("0xB6", "0x17"): ("[QuickEffectRack1_[Channel1]]", "PioneerDDJFLX4.cfxKnobMSB"),
    ("0xB6", "0x18"): ("[QuickEffectRack1_[Channel2]]", "PioneerDDJFLX4.cfxKnobMSB"),
    ("0xB6", "0x37"): ("[QuickEffectRack1_[Channel1]]", "PioneerDDJFLX4.cfxKnobLSB"),
    ("0xB6", "0x38"): ("[QuickEffectRack1_[Channel2]]", "PioneerDDJFLX4.cfxKnobLSB"),
}
by_message = dict(zip(messages, controls))
for message, (group, key) in expected.items():
    control = by_message[message]
    assert (control.findtext("group"), control.findtext("key")) == (group, key)

# This note is not a physical FLX4 control; it came from the FLX6 template.
assert ("0x96", "0x65") not in by_message
print("DDJ-FLX4 full preset and RX3 browser MIDI bindings: OK")
