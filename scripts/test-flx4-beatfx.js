#!/usr/bin/env node
// Exercise the real callbacks with stateful controls and live LED feedback.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const unit = '[EffectRack1_EffectUnit1]';
const slot = n => `[EffectRack1_EffectUnit1_Effect${n}]`;

function setup(native) {
    const values = new Map(), writes = [], lights = [], connections = new Map();
    const takeovers = [], ignoredValues = [];
    const engine = {
        getValue(g, k) { return values.get(`${g}:${k}`) || 0; },
        setValue(g, k, v) {
            const old = this.getValue(g, k);
            values.set(`${g}:${k}`, Number(v));
            writes.push([g, k, Number(v)]);
            if (old !== Number(v)) {
                for (const cb of connections.get(`${g}:${k}`) || []) cb(v, g, k);
            }
        },
        setParameter(g, k, v) { this.setValue(g, k, v); },
        makeConnection(g, k, cb) {
            const key = `${g}:${k}`;
            connections.set(key, [...(connections.get(key) || []), cb]);
        },
        softTakeover(...args) { takeovers.push(args); },
        softTakeoverIgnoreNextValue(...args) { ignoredValues.push(args); },
        beginTimer() { return 1; }, stopTimer() {},
    };
    engine.setValue('[RX3BeatFx]', 'controller_api', native ? 1 : 0);
    engine.setValue(unit, 'focused_effect', 2);
    engine.setValue(unit, 'enabled', 1);
    for (let i = 1; i <= 3; ++i) {
        engine.setValue(slot(i), 'enabled', 1);
        engine.setValue(slot(i), 'loaded', 1);
    }
    const context = vm.createContext({engine, script: {}, midi: {
        sendShortMsg(...message) { lights.push(message); }, sendSysexMsg() {},
    }});
    vm.runInContext(fs.readFileSync(path.join(__dirname,
        '../controllers/Pioneer_DDJ_FLX4_RX3/Pioneer-DDJ-FLX4-script.js'), 'utf8'), context);
    const m = context.PioneerDDJFLX4;
    m.init();
    const press = fn => m[fn](4, 0, 127, 0x94, unit);
    const release = fn => m[fn](4, 0, 0, 0x94, unit);
    const lit = () => lights.filter(([s, n]) => s === 0x94 && n === 0x47).at(-1)[2];
    return {m, engine, writes, lights, press, release, lit, takeovers, ignoredValues};
}

const {m, engine: e, writes, press, release, lit, takeovers, ignoredValues} = setup(true);
assert.deepEqual(takeovers.filter(([g, k]) => g === '[RX3BeatFx]' && k === 'amount'),
    [['[RX3BeatFx]', 'amount', false]], 'the hardware amount knob must not require pickup');
assert.equal(e.getValue(unit, 'enabled'), 0, 'connection starts with FX off');
for (let i = 1; i <= 3; ++i) assert.equal(e.getValue(slot(i), 'enabled'), 0);
assert.equal(lit(), 0);
press('beatFxOnOffPressed');
assert.equal(e.getValue(unit, 'enabled'), 1);
assert.equal(e.getValue(slot(1), 'enabled'), 1, 'activate the displayed slot despite focus=2');
assert.equal(e.getValue(slot(2), 'enabled'), 0);
assert.equal(lit(), 127);
const count = writes.length;
release('beatFxOnOffPressed');
assert.equal(writes.length, count, 'release must not toggle FX');

// A bank recall or X-PAD can enable slot 1 while the legacy focus points elsewhere.
e.setValue('[RX3BeatFx]', 'xpad_hold', 1);
e.setValue(slot(3), 'enabled', 1);
press('beatFxOnOffPressed');
assert.equal(e.getValue(unit, 'enabled'), 0, 'OFF closes the whole audio gate');
assert.equal(e.getValue('[RX3BeatFx]', 'xpad_hold'), 0);
for (let i = 1; i <= 3; ++i) assert.equal(e.getValue(slot(i), 'enabled'), 0);
assert.equal(lit(), 0);

e.setValue(slot(1), 'enabled', 1);
assert.equal(lit(), 0, 'an enabled slot behind a closed gate is off');
e.setValue(unit, 'enabled', 1);
assert.equal(lit(), 127, 'screen activation updates the hardware LED');
e.setValue(unit, 'enabled', 0);
assert.equal(lit(), 0, 'X-PAD release updates the hardware LED');
press('beatFxOnOffPressed');
assert.equal(e.getValue(unit, 'enabled'), 1, 'ON works after a momentary pad release');
press('beatFxOnOffPressed');
assert.equal(e.getValue(unit, 'enabled'), 0);
e.setValue(slot(1), 'loaded', 0);
press('beatFxOnOffPressed');
assert.equal(e.getValue(unit, 'enabled'), 0, 'empty slot cannot activate hidden FX');
e.setValue(slot(1), 'loaded', 1);

// The switch reports independent CH1/CH2 states, including both event orders.
for (const reverse of [false, true]) {
    for (const [ch1, ch2] of [[127, 0], [127, 127], [0, 127], [127, 0]]) {
        e.setValue(unit, 'group_[Master]_enable', 1);
        const events = [['beatFxChannel1', ch1], ['beatFxChannel2', ch2]];
        if (reverse) events.reverse();
        for (const [fn, value] of events) m[fn](4, 0, value, 0x94, unit);
        assert.equal(e.getValue(unit, 'group_[Master]_enable'), 0);
        assert.equal(e.getValue(unit, 'group_[Channel1]_enable'), ch1 / 127);
        assert.equal(e.getValue(unit, 'group_[Channel2]_enable'), ch2 / 127);
        assert.equal(e.getValue(unit, 'enabled'), 0, 'routing never activates FX');
    }
}

for (const [fn, key, value] of [
    ['beatFxSelectPressed', 'effect_step', 1],
    ['beatFxSelectShiftPressed', 'effect_step', -1],
    ['beatFxLeftPressed', 'beat_step', -1],
    ['beatFxRightPressed', 'beat_step', 1],
]) {
    const start = writes.length;
    press(fn); press(fn); release(fn);
    assert.deepEqual(writes.slice(start), [
        ['[RX3BeatFx]', key, value], ['[RX3BeatFx]', key, 0],
        ['[RX3BeatFx]', key, value], ['[RX3BeatFx]', key, 0],
    ], 'native operations pulse on every press and ignore release');
}
// The knob has one role even if either deck's SHIFT is held. Its first event
// replaces a saved/screen amount without changing the processor or enable state.
e.setValue(slot(1), 'meta', 0.37);
for (const [leftShift, rightShift] of [[false, false], [true, false], [false, true], [true, true]]) {
    m.shiftButtonDown[0] = leftShift;
    m.shiftButtonDown[1] = rightShift;
    e.setValue('[RX3BeatFx]', 'amount', 0.91);
    for (const value of [0, 1, 64, 127]) {
        const start = writes.length;
        m.beatFxLevelDepthRotate(4, 0x02, value);
        assert.deepEqual(writes.slice(start), [['[RX3BeatFx]', 'amount', value / 127]]);
        assert.equal(e.getValue('[RX3BeatFx]', 'amount'), value / 127);
        assert.equal(e.getValue(slot(1), 'meta'), 0.37);
        assert.equal(e.getValue(unit, 'enabled'), 0, 'turning the knob never enables FX');
        assert.equal(lit(), 0);
    }
}
press('beatFxOnOffPressed');
m.beatFxLevelDepthRotate(4, 0x02, 64);
assert.equal(e.getValue('[RX3BeatFx]', 'amount'), 64 / 127);
assert.equal(e.getValue(unit, 'enabled'), 1, 'adjusting active FX keeps it on');
assert.equal(lit(), 127);
press('beatFxOnOffShiftPressed');
assert.equal(e.getValue(unit, 'enabled'), 0);
assert.equal(e.getValue('[RX3BeatFx]', 'amount'), 0);
assert.equal(lit(), 0);
m.beatFxLevelDepthRotate(4, 0x02, 32);
assert.equal(e.getValue('[RX3BeatFx]', 'amount'), 32 / 127, 'first turn after reset applies immediately');
assert.equal(e.getValue(unit, 'enabled'), 0);
assert.equal(ignoredValues.filter(([g, k]) => g === '[RX3BeatFx]' && k === 'amount').length, 0);

const stock = setup(false);
assert.deepEqual(stock.takeovers.filter(([g, k]) => g === unit && k === 'mix'),
    [[unit, 'mix', true]], 'stock Mixxx retains pickup');
stock.m.beatFxLevelDepthRotate(4, 0x02, 64);
assert.equal(stock.engine.getValue(unit, 'mix'), 64 / 127);
stock.m.shiftButtonDown[1] = true;
stock.m.beatFxLevelDepthRotate(4, 0x02, 32);
assert.equal(stock.engine.getValue(slot(2), 'meta'), 32 / 127, 'stock retains SHIFT metaknob');
stock.press('beatFxOnOffPressed');
assert.equal(stock.engine.getValue(slot(2), 'enabled'), 0, 'stock retains focused-slot toggle');
stock.press('beatFxRightPressed');
assert.equal(stock.engine.getValue(unit, 'focused_effect'), 3);
stock.press('beatFxSelectPressed');
assert.equal(stock.engine.getValue(slot(3), 'next_effect'), 127);
console.log('DDJ-FLX4 Beat FX: native gating, channel routing, LED feedback and stock fallback OK');
