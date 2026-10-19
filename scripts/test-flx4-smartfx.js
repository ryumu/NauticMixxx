#!/usr/bin/env node
// Replay the actual preset's MIDI bindings, including both halves of CFX CCs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const directory = path.join(__dirname, '../controllers/Pioneer_DDJ_FLX4_RX3');
const xml = fs.readFileSync(path.join(directory, 'Pioneer-DDJ-FLX4-RX3.midi.xml'), 'utf8');
const bindings = new Map();
for (const match of xml.matchAll(/<control>([\s\S]*?)<\/control>/g)) {
    const tag = name => match[1].match(new RegExp(`<${name}>(.*?)</${name}>`))?.[1];
    bindings.set(`${Number(tag('status'))}:${Number(tag('midino'))}`, {
        group: tag('group'), key: tag('key'), script: match[1].includes('<script-binding'),
    });
}

function setup(native) {
    const values = new Map(), writes = [], lights = [], callbacks = new Map();
    const engine = {
        getValue(g, k) { return values.get(`${g}:${k}`) || 0; },
        setValue(g, k, v) {
            const changed = this.getValue(g, k) !== v;
            values.set(`${g}:${k}`, v); writes.push([g, k, v]);
            if (changed) for (const cb of callbacks.get(`${g}:${k}`) || []) cb(v, g, k);
        },
        setParameter(g, k, v) { this.setValue(g, k, v); },
        makeConnection(g, k, cb) {
            const key = `${g}:${k}`;
            callbacks.set(key, [...(callbacks.get(key) || []), cb]);
        },
        softTakeover() {}, beginTimer() { return 1; }, stopTimer() {},
    };
    engine.setValue('[RX3SmartFx]', 'available', Number(native));
    const context = vm.createContext({engine, script: {}, midi: {
        sendShortMsg(...args) { lights.push(args); }, sendSysexMsg() {},
    }});
    vm.runInContext(fs.readFileSync(path.join(directory, 'Pioneer-DDJ-FLX4-script.js'), 'utf8'), context);
    const m = context.PioneerDDJFLX4;
    m.init(); writes.length = 0;
    function send(status, number, value) {
        const binding = bindings.get(`${status}:${number}`);
        assert.ok(binding, `missing MIDI binding ${status}:${number}`);
        assert.ok(binding.script);
        m[binding.key.split('.')[1]](status & 0x0F, number, value, status, binding.group);
    }
    const knob = (deck, raw) => {
        send(0xB6, 0x17 + deck, raw >> 7);
        send(0xB6, 0x37 + deck, raw & 127);
    };
    const lit = () => lights.filter(([s, n]) => s === 0x96 && n === 0).at(-1)[2];
    return {m, engine, writes, send, knob, lit};
}

const {m, engine: e, writes, send, knob, lit} = setup(true);
assert.equal(lit(), 0);
send(0xB6, 0x37, 127);
assert.equal(writes.length, 0, 'ignore an orphaned LSB');
for (let deck = 0; deck < 2; ++deck) for (const raw of [0, 1, 8191, 8192, 16382, 16383]) {
    knob(deck, raw);
    assert.equal(e.getValue('[RX3SmartFx]', `knob${deck + 1}`), raw / 16383);
    assert.equal(e.getValue(`[QuickEffectRack1_[Channel${deck + 1}]]`, 'super1'), raw / 16383);
}
send(0x96, 0x00, 127);
assert.equal(e.getValue('[RX3SmartFx]', 'enabled'), 1);
assert.equal(lit(), 127);
let count = writes.length;
send(0x96, 0x00, 0);
assert.equal(writes.length, count, 'release must not toggle');
knob(0, 0);
assert.equal(e.getValue('[RX3SmartFx]', 'knob1'), 0);
assert.equal(e.getValue('[RX3SmartFx]', 'knob2'), 1, 'deck knobs remain independent');
assert.equal(e.getValue('[QuickEffectRack1_[Channel1]]', 'super1'), 1,
    'Smart CFX must not also move the normal filter superknob');
count = writes.length;
send(0x96, 0x08, 127); send(0x96, 0x08, 0);
assert.deepEqual(writes.slice(count), [
    ['[RX3SmartFx]', 'preset_open', 1], ['[RX3SmartFx]', 'preset_open', 0],
]);
assert.equal(e.getValue('[RX3SmartFx]', 'enabled'), 1, 'preset chooser leaves enable state alone');
e.setValue('[RX3SmartFx]', 'enabled', 0);
assert.equal(lit(), 0, 'screen changes update the physical LED');
knob(0, 8192);
assert.equal(e.getValue('[QuickEffectRack1_[Channel1]]', 'super1'), 8192 / 16383);
send(0x96, 0x00, 127);
m.smartFxPressed(6, 0, 64, 0x86);
assert.equal(e.getValue('[RX3SmartFx]', 'enabled'), 1, 'note-off with release velocity is ignored');
assert.equal(writes.some(([g]) => /EffectUnit|\[Channel\d\]/.test(g) && !g.startsWith('[QuickEffect')), false,
    'Smart CFX must not write Beat FX, tempo, loops or mixer transport');
m.shutdown();
assert.equal(e.getValue('[RX3SmartFx]', 'enabled'), 0, 'disconnect releases Smart CFX');
assert.equal(lit(), 0);

const stock = setup(false);
stock.send(0x96, 0x00, 127); stock.send(0x96, 0x08, 127);
assert.equal(stock.writes.length, 0, 'unavailable native API leaves Smart buttons inert');
stock.knob(1, 12345);
assert.deepEqual(stock.writes, [['[QuickEffectRack1_[Channel2]]', 'super1', 12345 / 16383]],
    'stock Mixxx retains full-resolution filter operation');
console.log('DDJ-FLX4 Smart CFX MIDI, center, chooser, LED and lifecycle: OK');
