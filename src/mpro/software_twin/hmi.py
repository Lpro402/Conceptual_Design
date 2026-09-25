"""HMI Manager: one clear operator message per state (Configuration 2 HMI table)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .states import SystemState

if TYPE_CHECKING:
    from .controller import MainSystemController

MESSAGES = {
    SystemState.SYSTEM_STANDBY: "מוכן - נותרו {remaining} אירועים",
    SystemState.SELF_TEST: "המערכת בודקת - המתן",
    SystemState.ENVIRONMENT_CHECK: "האם הרכב במקום סגור? אם כן, אין להפעיל. ליד קיר - הנח את המפזר בצד הפתוח.",
    SystemState.AWAIT_DEPLOY: "פרוס את הכבל ואת הוונט. הוצא את כל אזור המפזר המחורר מחוץ לרכב ואשר במסך.",
    SystemState.AWAIT_CONNECT: "חבר את המחבר לרכב",
    SystemState.EV_HANDSHAKE: "מתאם מול הרכב - המתן",
    SystemState.FILL_SESSION: "הוסף 1.8 ליטר מים. התקבלו {measured:.1f} מתוך 1.8 ליטר. אפשר לעצור את המזיגה ולהמשיך אחר כך.",
    SystemState.CONFIRM_ACTIVATION: "אישור: פעולה זו אינה הפיכה",
    SystemState.WATER_ADMISSION: "מפעיל מחסנית - המתן",
    SystemState.PRIME_FLOW_CHECK: "מכין מערכת - המתן",
    SystemState.PRECHARGE: "מתחבר לרכב - המתן",
    SystemState.ACTIVE_POWER: "מחזיר ניידות - {minutes} דקות משוערות",
    SystemState.DERATED: "ההספק הופחת להגנת המערכת - {minutes} דקות משוערות",
    SystemState.RAMP_DOWN: "מסיים בבטחה - אל תנתק",
    SystemState.PURGE_COOLDOWN: "מסיים בבטחה - אל תנתק",
    SystemState.SAFE_TO_DISCONNECT: "ניתן לנתק בבטחה",
    SystemState.SERVICE_REQUIRED: "נדרש שירות - שלוש מחסניות נוצלו",
    SystemState.POWER_ISOLATION: "תקלה - ההספק נותק, מבצע אוורור",
    SystemState.FAULT_LOCKED: "תקלה נעולה - נדרש שירות",
}


def instruction_for(state: SystemState, controller: "MainSystemController | None" = None) -> str:
    remaining = controller.remaining_events if controller else 3
    measured = controller.fill.measured_l if controller else 0.0
    minutes = "--"
    if controller and controller.plant and controller.hal.sensors.net_power_kw > 0.1:
        left = max(0.0, 3.0 - controller.delivered_kwh)
        minutes = f"{left / controller.hal.sensors.net_power_kw * 60:.0f}"
    return MESSAGES[state].format(remaining=remaining, measured=measured, minutes=minutes)
