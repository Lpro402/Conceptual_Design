"""Streamlit dashboard for the Metalyte academic concept demonstrator."""

from __future__ import annotations

import streamlit as st

from metalyte.controller import MainSystemController, TransitionError
from metalyte.states import FaultType, SystemState


st.set_page_config(page_title="Metalyte PRO-MPRO", page_icon="⚡", layout="wide")


def controller() -> MainSystemController:
    if "controller" not in st.session_state:
        st.session_state.controller = MainSystemController()
    return st.session_state.controller


def run_action(action, success: str | None = None) -> None:
    try:
        action()
        if success:
            st.toast(success, icon="✅")
    except (TransitionError, ValueError) as exc:
        st.error(str(exc))


ctrl = controller()
state_color = (
    "#16a34a"
    if ctrl.state in {SystemState.STANDBY, SystemState.READY, SystemState.POWER_TRANSFER}
    else "#dc2626"
    if ctrl.state in {SystemState.EMERGENCY_SHUTDOWN, SystemState.FAULT_LOCKED, SystemState.SERVICE_REQUIRED}
    else "#d97706"
)

st.title("Metalyte PRO-MPRO")
st.caption("Tier-0 academic software concept demonstrator — no real hardware or CCS2 control")
st.warning(
    "All values and thresholds are SIMULATED PLACEHOLDERS. "
    "This dashboard must not be used to operate equipment."
)

st.markdown(
    f"""
    <div style="padding:1rem;border-radius:0.75rem;background:{state_color}18;border:2px solid {state_color}">
      <div style="font-size:0.8rem;color:#64748b">CURRENT SYSTEM STATE</div>
      <div style="font-size:1.8rem;font-weight:700;color:{state_color}">{ctrl.state.name}</div>
      <div>{ctrl.instruction}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Mission controls")
rows = st.columns(5)
if rows[0].button("1 · Wake Up", use_container_width=True):
    run_action(ctrl.wake_up)
if rows[1].button("2 · Run Self-Test", use_container_width=True):
    run_action(ctrl.run_self_test)
if rows[2].button("3 · Connect Vehicle", use_container_width=True):
    run_action(ctrl.connect_vehicle)
if rows[3].button("4 · Select Cassette", use_container_width=True):
    run_action(ctrl.select_cassette)
if rows[4].button("5 · Add Water", use_container_width=True):
    run_action(ctrl.add_water)

rows = st.columns(5)
if rows[0].button("6 · Prime", use_container_width=True):
    run_action(ctrl.prime)
if rows[1].button("7 · Pre-Charge", use_container_width=True):
    run_action(ctrl.precharge)
if rows[2].button("8 · Start Power Transfer", type="primary", use_container_width=True):
    run_action(ctrl.start_power_transfer)
if rows[3].button("Stop", use_container_width=True):
    run_action(ctrl.stop)
if rows[4].button("Advance Shutdown Step", use_container_width=True):
    run_action(ctrl.advance_shutdown)

st.divider()
left, middle, right = st.columns([1.1, 1.1, 1.4])

with left:
    st.subheader("Cassette status")
    for cassette in ctrl.cassette_manager.cassettes:
        color = "green" if cassette.state.name == "DRY_READY" else "red" if cassette.state.name in {"FAULTED", "SPENT"} else "orange"
        st.markdown(f"**Cassette {cassette.cassette_id}:** :{color}[{cassette.state.name}]")
    st.metric("Remaining rescue events", ctrl.remaining_events)
    st.metric("Self-test", "PASS" if ctrl.self_test_passed else "NOT PASSED")
    st.metric("Vehicle", "CONNECTED" if ctrl.ev.connected else "DISCONNECTED")

with middle:
    st.subheader("Simulated measurements")
    s = ctrl.hal.sensors
    m1, m2 = st.columns(2)
    m1.metric("Stack voltage", f"{s.stack_voltage_v:.1f} V")
    m2.metric("Stack current", f"{s.stack_current_a:.1f} A")
    m1.metric("Temperature", f"{s.temperature_c:.1f} °C")
    m2.metric("Pressure", f"{s.pressure_bar:.2f} bar")
    m1.metric("Flow", f"{s.electrolyte_flow_lpm:.1f} L/min")
    m2.metric("H₂", f"{s.hydrogen_pct:.2f} %")
    st.write("HVIL:", "✅ Closed" if s.hvil_closed else "❌ Open")
    st.write("Isolation:", "✅ Valid" if s.isolation_valid else "❌ Fault")

with right:
    st.subheader("Simulated actuator commands")
    a = ctrl.hal.actuators
    actuator_rows = {
        "Water valve": a.water_valve_open,
        "Pump": a.pump_on,
        "Fan": a.fan_on,
        "Vent / purge": a.vent_on,
        "Input contactor": a.input_contactor_closed,
        "Output contactor": a.output_contactor_closed,
        "Converter": a.converter_enabled,
        "Gate disable": a.gate_disable,
    }
    for name, active in actuator_rows.items():
        st.write(f"{'🟢' if active else '⚪'} {name}: {'ON' if active else 'OFF'}")

st.divider()
fault_col, safety_col = st.columns([1, 2])
with fault_col:
    st.subheader("Safety simulation")
    fault = st.selectbox("Fault to inject", list(FaultType), format_func=lambda f: f.value)
    if st.button("Inject Fault", type="secondary", use_container_width=True):
        run_action(lambda: ctrl.inject_fault(fault))
    if st.button("E-Stop", type="primary", use_container_width=True):
        run_action(lambda: ctrl.inject_fault(FaultType.E_STOP))
    if st.button("Reset Demonstrator", use_container_width=True):
        ctrl.reset_demonstrator()
        st.rerun()

with safety_col:
    st.subheader("Independent safety supervisor")
    if ctrl.active_faults:
        st.error("FAULT LATCHED — " + ", ".join(ctrl.active_faults))
    else:
        st.success("No latched simulated fault")
    st.caption(
        "Critical faults directly disable conversion, open simulated contactors, "
        "stop water admission, and retain ventilation when available."
    )

st.subheader("Chronological event log")
if ctrl.logger.records:
    st.dataframe(
        [r.__dict__ for r in reversed(ctrl.logger.records)],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No events recorded.")

