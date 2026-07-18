"""User-instruction mapping for the local dashboard."""

from dataclasses import dataclass

from .states import SystemState


INSTRUCTIONS = {
    SystemState.STANDBY: "הפעל את המערכת כדי להתחיל.",
    SystemState.WAKE_UP_SELF_TEST: "בצע בדיקה אוטומטית.",
    SystemState.VEHICLE_CONNECTION: "חבר את המערכת לרכב.",
    SystemState.CASSETTE_SELECTION: "בחר מחסנית זמינה.",
    SystemState.WATER_ACTIVATION: "הוסף מים ואשר.",
    SystemState.PRIMING: "הכן את נתיבי הזרימה והאוורור.",
    SystemState.PRE_CHARGE: "בצע Pre-Charge והתחל העברת אנרגיה.",
    SystemState.POWER_TRANSFER: "העברת האנרגיה פעילה.",
    SystemState.DERATING: "ההספק הופחת להגנת המערכת.",
    SystemState.RAMP_DOWN: "המשך לכיבוי מבוקר.",
    SystemState.PURGE_COOLDOWN: "השלם אוורור וקירור לפני ניתוק.",
    SystemState.READY: "ניתן להתחיל אירוע חילוץ נוסף.",
    SystemState.SERVICE_REQUIRED: "שלושה אירועים הושלמו; נדרש שירות.",
    SystemState.FAULT_LOCKED: "התקלה נעולה; יש לאפס את ההדגמה.",
    SystemState.EMERGENCY_SHUTDOWN: "עצירת חירום פעילה.",
}


@dataclass
class HMIManager:
    def instruction_for(self, state: SystemState) -> str:
        return INSTRUCTIONS[state]
