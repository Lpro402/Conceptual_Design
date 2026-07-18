"""User-facing Streamlit HMI for the Metalyte academic demonstrator."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from metalyte.controller import MainSystemController, TransitionError
from metalyte.states import FaultType, SystemState


st.set_page_config(
    page_title="Metalyte PRO-MPRO",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


STATE_UI = {
    SystemState.STANDBY: ("מוכנה להפעלה", "המערכת מאוחסנת ומוכנה לאירוע חילוץ.", "ready"),
    SystemState.WAKE_UP_SELF_TEST: ("בדיקת מערכת", "יש לבצע בדיקה אוטומטית לפני החיבור.", "active"),
    SystemState.VEHICLE_CONNECTION: ("ממתינה לחיבור", "חבר את כבל הטעינה לרכב.", "active"),
    SystemState.CASSETTE_SELECTION: ("בחירת מחסנית", "המערכת תבחר מחסנית זמינה.", "active"),
    SystemState.WATER_ACTIVATION: ("הוספת מים", "הוסף מים בפתח הייעודי ואשר.", "active"),
    SystemState.PRIMING: ("הכנת התגובה", "המערכת מכינה את נתיבי הזרימה והאוורור.", "active"),
    SystemState.PRE_CHARGE: ("הכנת מתח", "בדיקת החיבור החשמלי לפני העברת אנרגיה.", "active"),
    SystemState.POWER_TRANSFER: ("מעבירה אנרגיה", "העברת האנרגיה לרכב פעילה.", "charging"),
    SystemState.DERATING: ("הספק מופחת", "המערכת הפחיתה הספק לשמירה על תנאי הפעולה.", "warning"),
    SystemState.RAMP_DOWN: ("סיום מבוקר", "העברת האנרגיה הופסקה; נדרש כיבוי בטוח.", "active"),
    SystemState.PURGE_COOLDOWN: ("אוורור וקירור", "המערכת מפנה גזים וחום לפני ניתוק.", "active"),
    SystemState.READY: ("האירוע הושלם", "ניתן להתחיל אירוע חילוץ נוסף.", "ready"),
    SystemState.SERVICE_REQUIRED: ("נדרש שירות", "שלוש המחסניות נוצלו ויש להגיע לעמדת שירות.", "fault"),
    SystemState.FAULT_LOCKED: ("תקלה נעולה", "המערכת נעולה עד לאיפוס ההדגמה.", "fault"),
    SystemState.EMERGENCY_SHUTDOWN: ("עצירת חירום", "ההספק נותק והמערכת עוברת למצב בטוח.", "fault"),
}

FAULT_LABELS = {
    FaultType.E_STOP: "לחצן חירום",
    FaultType.HVIL_OPEN: "לולאת HVIL פתוחה",
    FaultType.ISOLATION_FAULT: "כשל בידוד",
    FaultType.OVERTEMPERATURE: "טמפרטורה גבוהה",
    FaultType.HYDROGEN_ALARM: "ריכוז מימן חריג",
    FaultType.LEAK: "דליפה",
    FaultType.ABNORMAL_PRESSURE: "לחץ חריג",
    FaultType.LOSS_OF_FLOW: "אובדן זרימה",
    FaultType.PUMP_FAILURE: "כשל משאבה",
    FaultType.FAN_FAILURE: "כשל מאוורר",
    FaultType.CONTACTOR_MISMATCH: "אי־התאמת קונטקטור",
}

CASSETTE_LABELS = {
    "DRY_READY": ("מוכנה", "●", "ready"),
    "SELECTED": ("נבחרה", "●", "active"),
    "ACTIVATING": ("בהפעלה", "●", "active"),
    "ACTIVE": ("פעילה", "●", "charging"),
    "SPENT": ("משומשת", "●", "spent"),
    "FAULTED": ("תקלה", "●", "fault"),
}

MISSION_STATES = [
    SystemState.STANDBY,
    SystemState.WAKE_UP_SELF_TEST,
    SystemState.VEHICLE_CONNECTION,
    SystemState.CASSETTE_SELECTION,
    SystemState.WATER_ACTIVATION,
    SystemState.PRIMING,
    SystemState.PRE_CHARGE,
    SystemState.POWER_TRANSFER,
    SystemState.RAMP_DOWN,
    SystemState.PURGE_COOLDOWN,
    SystemState.READY,
]


st.markdown(
    """
    <style>
      :root { --ink:#10233f; --muted:#64748b; --line:#dce5ef; --blue:#1769e0; }
      .stApp { background:linear-gradient(180deg,#f7f9fc 0%,#eef3f8 100%);
        font-family:"Segoe UI",Arial,sans-serif; }
      .block-container { max-width:1180px; padding-top:1.4rem; padding-bottom:3rem; }
      #MainMenu, footer, header { visibility:hidden; }
      div[data-testid="stToolbar"] { display:none; }
      .brand { display:flex; align-items:center; gap:14px; margin-bottom:18px; }
      .brand-mark { width:46px; height:46px; border-radius:14px; display:grid; place-items:center;
        background:linear-gradient(145deg,#0d4fb9,#28a3ff); color:white; font-size:24px;
        box-shadow:0 10px 24px rgba(23,105,224,.22); }
      .brand-name { color:var(--ink); font-size:1.35rem; font-weight:800; letter-spacing:.02em; }
      .brand-sub { color:var(--muted); font-size:.88rem; }
      .hero { border-radius:24px; padding:28px 30px; color:white; margin-bottom:14px;
        box-shadow:0 18px 45px rgba(15,35,65,.16); position:relative; overflow:hidden; }
      .hero:after { content:""; position:absolute; width:260px; height:260px; border-radius:50%;
        background:rgba(255,255,255,.08); right:-85px; top:-115px; }
      .hero.ready { background:linear-gradient(120deg,#12335e,#126b79); }
      .hero.active { background:linear-gradient(120deg,#12335e,#1769e0); }
      .hero.charging { background:linear-gradient(120deg,#075c4f,#0e9f6e); }
      .hero.warning { background:linear-gradient(120deg,#7c3f00,#d97706); }
      .hero.fault { background:linear-gradient(120deg,#6e1020,#d12846); }
      .eyebrow { font-size:.72rem; font-weight:800; letter-spacing:.14em; opacity:.78; }
      .hero-title { font-size:2rem; font-weight:850; margin:.25rem 0 .35rem; }
      .hero-copy { font-size:1rem; opacity:.9; max-width:650px; }
      .progress-shell { background:rgba(255,255,255,.18); height:7px; border-radius:999px;
        overflow:hidden; margin-top:22px; max-width:690px; }
      .progress-fill { background:white; height:100%; border-radius:999px; }
      .mini-label { color:var(--muted); font-size:.74rem; font-weight:750; letter-spacing:.06em; }
      .value { color:var(--ink); font-size:1.38rem; font-weight:800; margin-top:4px; }
      .soft-card { background:rgba(255,255,255,.92); border:1px solid var(--line); border-radius:18px;
        padding:18px 20px; min-height:106px; box-shadow:0 6px 20px rgba(15,35,65,.05); }
      .cassette-row { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
      .cassette { background:white; border:1px solid var(--line); border-radius:16px; padding:15px; }
      .cassette .number { color:var(--muted); font-size:.78rem; }
      .cassette .state { font-weight:800; font-size:1.05rem; margin-top:6px; }
      .cassette.ready .state { color:#0f8a68; } .cassette.active .state { color:#1769e0; }
      .cassette.charging .state { color:#0d9b6c; } .cassette.spent .state { color:#7b8798; }
      .cassette.fault .state { color:#cf2441; }
      .disclaimer { color:#718096; text-align:center; font-size:.72rem; margin-top:16px; }
      div[data-testid="stButton"] > button { border-radius:13px; min-height:48px; font-weight:750; }
      div[data-testid="stButton"] > button[kind="primary"] { color:white !important; border:0 !important;
        background:linear-gradient(120deg,#145bc4,#228ae6) !important;
        box-shadow:0 8px 20px rgba(23,105,224,.22); }
      .st-key-emergency-stop button { color:#b4233d !important; border-color:#f1a1ae !important;
        background:#fff6f7 !important; }
      .st-key-emergency-stop button:hover { color:white !important; border-color:#c91f3d !important;
        background:#c91f3d !important; }
      div[data-testid="stExpander"] { background:rgba(255,255,255,.82); border:1px solid var(--line);
        border-radius:16px; overflow:hidden; }
      @media (max-width:700px) { .cassette-row { grid-template-columns:1fr; }
        .hero { padding:22px; } .hero-title { font-size:1.6rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def controller() -> MainSystemController:
    if "controller" not in st.session_state:
        st.session_state.controller = MainSystemController()
    return st.session_state.controller


def run_action(action: Callable[[], None]) -> None:
    try:
        action()
        st.rerun()
    except (TransitionError, ValueError) as exc:
        st.error(str(exc))


def primary_action(ctrl: MainSystemController) -> tuple[str, Callable[[], None]] | None:
    actions: dict[SystemState, tuple[str, Callable[[], None]]] = {
        SystemState.STANDBY: ("הפעלת המערכת", ctrl.wake_up),
        SystemState.WAKE_UP_SELF_TEST: ("ביצוע בדיקה אוטומטית", ctrl.run_self_test),
        SystemState.VEHICLE_CONNECTION: ("אישור חיבור לרכב", ctrl.connect_vehicle),
        SystemState.CASSETTE_SELECTION: ("בחירת מחסנית זמינה", ctrl.select_cassette),
        SystemState.WATER_ACTIVATION: ("הוספתי מים", ctrl.add_water),
        SystemState.PRIMING: ("הכנת המערכת", ctrl.prime),
        SystemState.POWER_TRANSFER: ("סיום העברת האנרגיה", ctrl.stop),
        SystemState.DERATING: ("סיום העברת האנרגיה", ctrl.stop),
        SystemState.RAMP_DOWN: ("המשך לכיבוי בטוח", ctrl.advance_shutdown),
        SystemState.PURGE_COOLDOWN: ("סיום אוורור וקירור", ctrl.advance_shutdown),
        SystemState.READY: ("התחלת חילוץ נוסף", ctrl.wake_up),
        SystemState.EMERGENCY_SHUTDOWN: ("אבטחת המערכת", ctrl.advance_shutdown),
    }
    if ctrl.state is SystemState.PRE_CHARGE:
        if ctrl.power.precharge_complete:
            return "התחלת העברת אנרגיה", ctrl.start_power_transfer
        return "בדיקת מתח וחיבור", ctrl.precharge
    return actions.get(ctrl.state)


def mission_progress(state: SystemState) -> int:
    if state in {SystemState.SERVICE_REQUIRED, SystemState.FAULT_LOCKED}:
        return 100
    if state is SystemState.EMERGENCY_SHUTDOWN:
        return 78
    if state is SystemState.DERATING:
        return 70
    try:
        return round(MISSION_STATES.index(state) / (len(MISSION_STATES) - 1) * 100)
    except ValueError:
        return 0


ctrl = controller()
state_title, state_copy, state_style = STATE_UI[ctrl.state]
progress = mission_progress(ctrl.state)

st.markdown(
    """
    <div class="brand">
      <div class="brand-mark">⚡</div>
      <div><div class="brand-name">METALYTE PRO</div>
      <div class="brand-sub">ממשק הדגמה להשבת ניידות לרכב חשמלי</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="hero {state_style}" dir="rtl">
      <div class="eyebrow">מצב המערכת</div>
      <div class="hero-title">{state_title}</div>
      <div class="hero-copy">{state_copy}</div>
      <div class="progress-shell"><div class="progress-fill" style="width:{progress}%"></div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

action = primary_action(ctrl)
action_col, emergency_col = st.columns([4, 1])
with action_col:
    if action and st.button(action[0], type="primary", use_container_width=True, key=f"action-{ctrl.state.name}-{ctrl.power.precharge_complete}"):
        run_action(action[1])
    elif not action:
        st.button("אין פעולה זמינה", disabled=True, use_container_width=True)
with emergency_col:
    if st.button("עצירת חירום", use_container_width=True, key="emergency-stop"):
        run_action(lambda: ctrl.inject_fault(FaultType.E_STOP))

st.write("")
summary_cols = st.columns(3)
with summary_cols[0]:
    st.markdown(
        f'<div class="soft-card"><div class="mini-label">אירועי חילוץ שנותרו</div><div class="value">{ctrl.remaining_events} / 3</div></div>',
        unsafe_allow_html=True,
    )
with summary_cols[1]:
    vehicle = "מחובר" if ctrl.ev.connected else "לא מחובר"
    st.markdown(
        f'<div class="soft-card"><div class="mini-label">חיבור לרכב</div><div class="value">{vehicle}</div></div>',
        unsafe_allow_html=True,
    )
with summary_cols[2]:
    safety = "תקלה פעילה" if ctrl.active_faults else "תקין"
    st.markdown(
        f'<div class="soft-card"><div class="mini-label">מצב בטיחות</div><div class="value">{safety}</div></div>',
        unsafe_allow_html=True,
    )

st.write("")
st.markdown("#### מצב המחסניות")
cassette_html = '<div class="cassette-row" dir="rtl">'
for cassette in ctrl.cassette_manager.cassettes:
    label, dot, style = CASSETTE_LABELS[cassette.state.name]
    cassette_html += (
        f'<div class="cassette {style}"><div class="number">מחסנית {cassette.cassette_id}</div>'
        f'<div class="state">{dot} {label}</div></div>'
    )
cassette_html += "</div>"
st.markdown(cassette_html, unsafe_allow_html=True)

if ctrl.state in {SystemState.POWER_TRANSFER, SystemState.DERATING}:
    st.write("")
    s = ctrl.hal.sensors
    power_kw = s.stack_voltage_v * s.stack_current_a / 1000
    charge_cols = st.columns(4)
    charge_cols[0].metric("הספק נוכחי", f"{power_kw:.1f} kW")
    charge_cols[1].metric("מתח", f"{s.stack_voltage_v:.1f} V")
    charge_cols[2].metric("זרם", f"{s.stack_current_a:.1f} A")
    charge_cols[3].metric("טמפרטורה", f"{s.temperature_c:.1f} °C")

if ctrl.active_faults:
    labels = [FAULT_LABELS.get(fault, fault.value) for fault in ctrl.safety.latched_faults]
    st.error("תקלה נעולה: " + ", ".join(labels))

st.write("")
with st.expander("סימולציית תקלות — מצב הנדסי"):
    st.caption("מיועד להמחשת תגובת הבטיחות בלבד. כל הספים והערכים מדומים.")
    fault_col, inject_col, reset_col = st.columns([2, 1, 1])
    with fault_col:
        selected_fault = st.selectbox(
            "בחר תקלה",
            list(FaultType),
            format_func=lambda fault: FAULT_LABELS[fault],
            label_visibility="collapsed",
        )
    with inject_col:
        if st.button("הזרקת תקלה", use_container_width=True):
            run_action(lambda: ctrl.inject_fault(selected_fault))
    with reset_col:
        if st.button("איפוס הדגמה", use_container_width=True):
            ctrl.reset_demonstrator()
            st.rerun()

with st.expander("נתוני מערכת מדומים"):
    s = ctrl.hal.sensors
    a = ctrl.hal.actuators
    sensor_cols = st.columns(6)
    sensor_cols[0].metric("מתח Stack", f"{s.stack_voltage_v:.1f} V")
    sensor_cols[1].metric("זרם Stack", f"{s.stack_current_a:.1f} A")
    sensor_cols[2].metric("טמפרטורה", f"{s.temperature_c:.1f} °C")
    sensor_cols[3].metric("לחץ", f"{s.pressure_bar:.2f} bar")
    sensor_cols[4].metric("זרימה", f"{s.electrolyte_flow_lpm:.1f} L/min")
    sensor_cols[5].metric("מימן", f"{s.hydrogen_pct:.2f} %")
    st.caption(
        "פקודות: "
        f"משאבה {'פעילה' if a.pump_on else 'כבויה'} · "
        f"מאוורר {'פעיל' if a.fan_on else 'כבוי'} · "
        f"ממיר {'פעיל' if a.converter_enabled else 'כבוי'} · "
        f"קונטקטורים {'סגורים' if a.output_contactor_closed else 'פתוחים'}"
    )

with st.expander("יומן אירועים"):
    if ctrl.logger.records:
        st.dataframe(
            [record.__dict__ for record in reversed(ctrl.logger.records)],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("טרם נרשמו אירועים.")

st.markdown(
    '<div class="disclaimer">הדגמה אקדמית בלבד · ללא חיבור לחומרה, לרכב או ל־CCS2 · כל הערכים מדומים</div>',
    unsafe_allow_html=True,
)
