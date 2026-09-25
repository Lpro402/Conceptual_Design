"""Streamlit operator console: the software twin driving the chemical twin.

Run with ``python -m streamlit run apps/software_twin_app.py``.
"""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from mpro.software_twin import FaultType, MainSystemController, SystemState, TransitionError
from mpro.software_twin.states import MISSION_SEQUENCE
from mpro.twin_services import assess

st.set_page_config(page_title="MPRO Software Twin", page_icon="⚡", layout="wide")

STYLE = {
    SystemState.ACTIVE_POWER: "#0e9f6e", SystemState.DERATED: "#d97706",
    SystemState.POWER_ISOLATION: "#d12846", SystemState.FAULT_LOCKED: "#d12846",
    SystemState.SERVICE_REQUIRED: "#7c3aed", SystemState.SAFE_TO_DISCONNECT: "#126b79",
}


def ctrl() -> MainSystemController:
    if "ctrl" not in st.session_state:
        st.session_state.ctrl = MainSystemController()
    return st.session_state.ctrl


def act(fn: Callable[[], None]) -> None:
    try:
        fn()
    except (TransitionError, ValueError) as exc:
        st.session_state.error = str(exc)
    st.rerun()


c = ctrl()
color = STYLE.get(c.state, "#1769e0")
step = MISSION_SEQUENCE.index(c.state) + 1 if c.state in MISSION_SEQUENCE else None
st.markdown(
    f"""<div style="border-radius:20px;padding:22px 26px;color:white;background:{color}">
    <div style="font-size:.75rem;letter-spacing:.14em;opacity:.8">MPRO · CONFIGURATION 2 · SOFTWARE TWIN
    {f'· STEP {step}/{len(MISSION_SEQUENCE)}' if step else ''}</div>
    <div style="font-size:1.9rem;font-weight:800">{c.state.name}</div>
    <div dir="rtl" style="font-size:1.05rem">{c.instruction}</div></div>""",
    unsafe_allow_html=True,
)
if err := st.session_state.pop("error", None):
    st.error(err)

left, right = st.columns([1.05, 1])
with left:
    st.subheader("Operator actions")
    s = c.state
    if s is SystemState.SYSTEM_STANDBY:
        b1, b2 = st.columns(2)
        if b1.button("Wake (user)", type="primary", width="stretch"):
            act(lambda: c.wake("USER_WAKE"))
        if b2.button("Scheduled D-BIT", width="stretch"):
            act(lambda: (c.wake("DBIT_TIMER"), c.run_storage_check()))
    elif s is SystemState.SELF_TEST:
        if st.button("Run self-test", type="primary"):
            act(c.run_self_test)
    elif s is SystemState.ENVIRONMENT_CHECK:
        enclosed = st.toggle("Vehicle is in an enclosed space")
        wall = st.toggle("Vehicle is next to a wall")
        open_side = st.toggle("Diffuser placed on the open side", disabled=not wall)
        c.hal.sensors.vent_path_clear = not st.toggle("Cargo obstructs the vents")
        if st.button("Submit answers", type="primary"):
            act(lambda: c.answer_environment(enclosed, wall, open_side))
    elif s is SystemState.AWAIT_DEPLOY:
        c.hal.sensors.cable_deployed = st.toggle("CABLE_DEPLOYED", value=True)
        c.hal.sensors.vent_deployed = st.toggle("VENT_DEPLOYED", value=True)
        outside = st.checkbox("I confirm the whole perforated diffuser zone is outside the vehicle")
        if st.button("Confirm deployment", type="primary"):
            act(lambda: c.confirm_deployment(outside))
    elif s is SystemState.AWAIT_CONNECT:
        c.hal.sensors.hvil_closed = st.toggle("HVIL continuous", value=True)
        c.hal.sensors.cp_voltage_v = st.slider("CP level [V]", 0.0, 12.0, 9.0, 0.5)
        c.hal.sensors.isolation_kohm = st.select_slider("IMD reading [kΩ]", [10, 30, 120, 500, 2000], 2000)
        if st.button("Verify connection", type="primary"):
            act(c.verify_connection)
    elif s is SystemState.EV_HANDSHAKE:
        iso = st.toggle("ISO 15118 communication OK", value=True)
        din = st.toggle("DIN 70121 communication OK", value=True)
        if st.button("Handshake", type="primary"):
            act(lambda: c.handshake(iso, din))
    elif s is SystemState.FILL_SESSION:
        st.progress(min(c.fill.measured_l / 1.8, 1.0), text=c.fill.progress_message())
        pour = st.number_input("Pour batch [L]", 0.1, 2.5, 0.6, 0.1)
        b1, b2, b3, b4 = st.columns(4)
        if b1.button("Pour", type="primary", width="stretch"):
            act(lambda: c.pour_water(pour))
        if b2.button("Confirm volume", width="stretch"):
            act(c.confirm_fill)
        if b3.button("Controller restart", width="stretch"):
            act(c.restart_controller)
        if b4.button("Re-measure", width="stretch"):
            act(c.remeasure_water)
        if st.button("Cancel (returns cartridge to DRY_READY)"):
            act(c.cancel_fill)
    elif s is SystemState.CONFIRM_ACTIVATION:
        st.warning("Water admission is irreversible for this cartridge.")
        if st.button("Confirm activation", type="primary"):
            act(c.confirm_activation)
    elif s is SystemState.WATER_ADMISSION:
        if st.button("Complete admission", type="primary"):
            act(c.complete_admission)
    elif s is SystemState.PRIME_FLOW_CHECK:
        if st.button("Prime & flow check", type="primary"):
            act(c.prime)
    elif s is SystemState.PRECHARGE:
        kw = st.radio("Requested power", [10.0, 12.0], horizontal=True, format_func=lambda v: f"{v:.0f} kW")
        if st.button("Pre-charge & start transfer", type="primary"):
            act(lambda: c.start_power_transfer(kw))
    elif s in {SystemState.ACTIVE_POWER, SystemState.DERATED}:
        kw = st.radio("Requested power", [10.0, 12.0], horizontal=True, index=int(c.requested_kw > 10),
                      format_func=lambda v: f"{v:.0f} kW")
        if kw != c.requested_kw:
            c.request_power(kw)
        b1, b2 = st.columns(2)
        if b1.button("Run 2 minutes", type="primary", width="stretch"):
            act(lambda: c.tick(120))
        if b2.button("STOP", width="stretch"):
            act(c.stop)
    elif s in {SystemState.RAMP_DOWN, SystemState.PURGE_COOLDOWN, SystemState.POWER_ISOLATION}:
        if st.button("Next shutdown step", type="primary"):
            act(c.advance_shutdown)
    elif s is SystemState.SAFE_TO_DISCONNECT:
        if st.button("Disconnect and stow", type="primary"):
            act(c.disconnect)
    if s not in {SystemState.SYSTEM_STANDBY, SystemState.FAULT_LOCKED, SystemState.SERVICE_REQUIRED}:
        if s in {SystemState.ENVIRONMENT_CHECK, SystemState.AWAIT_DEPLOY, SystemState.AWAIT_CONNECT,
                 SystemState.EV_HANDSHAKE, SystemState.CONFIRM_ACTIVATION}:
            if st.button("STOP (before wetting)"):
                act(c.stop)
    with st.expander("Fault injection (independent safety supervisor)"):
        fault = st.selectbox("Fault", list(FaultType), format_func=lambda f: f.value)
        if st.button("Inject"):
            act(lambda: c.inject_fault(fault))
    if st.button("Reset demonstrator"):
        act(c.reset_demonstrator)

with right:
    st.subheader("Cartridges")
    cols = st.columns(3)
    for col, cart in zip(cols, c.cartridges.cartridges):
        col.metric(f"C{cart.cartridge_id}", cart.state.name, f"{cart.delivered_kwh:.2f} kWh" if cart.delivered_kwh else None)
    sns = c.hal.sensors
    st.subheader("Chemical twin telemetry")
    m = st.columns(4)
    m[0].metric("EV power", f"{sns.net_power_kw:.1f} kW")
    m[1].metric("Energy", f"{c.delivered_kwh:.2f} / 3.00 kWh")
    m[2].metric("Stack", f"{sns.stack_voltage_v:.0f} V · {sns.stack_current_a:.0f} A")
    m[3].metric("Core", f"{sns.temperature_c:.1f} °C")
    if c.plant:
        st.caption(f"KOH {c.plant.molarity:.2f} M · Al left {c.plant.state.aluminum_kg:.3f} kg · "
                   f"H₂ {c.plant.state.hydrogen_rate_l_min:.2f} L/min · protocol {c.ev.protocol}")
    if c.telemetry:
        st.line_chart({"power kW": [t["power_kw"] for t in c.telemetry],
                       "core °C": [t["temperature_c"] for t in c.telemetry]})
        a = assess(c.telemetry)
        st.subheader("Twin layers")
        for f in a.monitoring + a.diagnostics:
            (st.error if f.severity == "CRITICAL" else st.warning if f.severity == "WARNING" else st.info)(
                f"[{f.layer}] {f.message}")
        if a.prognosis and a.prognosis.minutes_to_event_complete:
            st.write(f"**Prognosis:** {a.prognosis.minutes_to_event_complete:.1f} min to 3 kWh; "
                     f"Al margin {a.prognosis.aluminum_margin_kg:.3f} kg")
        for rx in a.prescriptions:
            st.write(f"➜ {rx}")
    st.subheader("Event log")
    st.dataframe([{"level": r.level, "message": r.message} for r in reversed(c.logger.records[-30:])],
                 hide_index=True, width="stretch")

st.caption("Academic Tier 0-1 twin. Simulated values only — not firmware, not a charger, not test evidence.")
