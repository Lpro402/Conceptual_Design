# Independent safety supervisor

## Intent

Conceptual model of hardware channel 620: an authority separate from the main
controller and from the RTOS. It is not a functional-safety design and makes no
SIL, ASIL, diagnostic-coverage, timing or compliance claim.

## Supervised conditions

E-Stop, HVIL, IMD 490 isolation, overtemperature (≥ 65 °C), hydrogen at the
vent, leak, contactor feedback, and — while the reaction runs — pressure,
electrolyte flow, pump and blower availability.

## IMD 490 thresholds [8.1, 8.3]

| Level | Placeholder (Ω/V of output voltage) | Response |
|---|---|---|
| Normal | ≥ 500 | — |
| Warning | 100 – 500 | Indication only; continue while every other condition is safe |
| Block | < 100 | Prevents transfer before it starts; trips during transfer |

Isolation is checked before transfer and monitored continuously during it.
A protocol fallback (ISO 15118 → DIN 70121) never bypasses an HVIL or
isolation block.

## Protective response

A trip immediately disables conversion, asserts gate disable, opens the input
and output contactors, closes the cartridge water valve, stops the pump, keeps
ventilation and the external vent open (unless the blower itself failed),
latches the fault and logs a critical record. After wetting, the controller
then completes purge and cooldown before `FAULT_LOCKED`.

Reset exists only to make demonstrations repeatable; it is not a service
procedure.
