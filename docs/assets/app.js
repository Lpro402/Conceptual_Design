"use strict";

/* MPRO software twin — public web HMI, Configuration 2.
 * Mirrors src/mpro/software_twin (Python reference). STATE_ORDER must equal
 * MISSION_SEQUENCE in states.py; tests/test_web_twins.py enforces it. */

const BASELINE = {
  nominalKw: 10, boostKw: 12, eventKwh: 3, stackV: 96, efficiency: 0.92,
  waterTargetL: 1.8, waterRejectL: 2.2, boostDisableC: 52, derateC: 55, shutdownC: 65,
};
const SIM_SECONDS_PER_TICK = 20;   // one real second = 20 simulated seconds
const FILL_BATCH_L = 0.6;

const STATE_ORDER = [
  "SYSTEM_STANDBY", "SELF_TEST", "ENVIRONMENT_CHECK", "AWAIT_DEPLOY", "AWAIT_CONNECT",
  "EV_HANDSHAKE", "FILL_SESSION", "CONFIRM_ACTIVATION", "WATER_ADMISSION", "PRIME_FLOW_CHECK",
  "PRECHARGE", "ACTIVE_POWER", "RAMP_DOWN", "PURGE_COOLDOWN", "SAFE_TO_DISCONNECT",
];

const STATES = {
  SYSTEM_STANDBY: { title: "Ready — Standby", copy: "Controller asleep; wakes only from defined sources. Unneeded power domains are off.", style: "ready", action: "Wake Up System", actionCopy: "User wake starts the guided rescue sequence." },
  SELF_TEST: { title: "System Self-Test", copy: "Sensors, interlocks and safety chain are checked with temperature-compensated thresholds.", style: "active", action: "Run Self-Test", actionCopy: "Only STOP / E-STOP are accepted during the test." },
  ENVIRONMENT_CHECK: { title: "Check the Surroundings", copy: "Is the vehicle in an enclosed space? If so, do not operate. Next to a wall, place the diffuser on the open side.", style: "active", action: "Open Air — Continue", actionCopy: "An enclosed space blocks operation; obstructed vents require clearing cargo." },
  AWAIT_DEPLOY: { title: "Deploy Cable and Vent", copy: "Take the whole perforated diffuser zone outside the vehicle and confirm on screen.", style: "active", action: "Confirm Diffuser Outside", actionCopy: "Cable and vent signals plus the driver's confirmation are all required." },
  AWAIT_CONNECT: { title: "Connect to the Vehicle", copy: "Plug the CCS2 connector into the vehicle inlet.", style: "active", action: "Verify Connection", actionCopy: "HVIL continuity over the check window, CP levels and isolation are verified." },
  EV_HANDSHAKE: { title: "Vehicle Handshake", copy: "Negotiating limits with the vehicle — please wait.", style: "active", action: "Start Handshake", actionCopy: "ISO 15118 first; a communication failure falls back to DIN 70121." },
  FILL_SESSION: { title: "Add 1.8 L of Water", copy: "Pour clean water into the fill port. You may pause and continue later.", style: "active", action: "Pour Batch", actionCopy: "Water collects in chamber 220; the valve to the cartridge stays closed." },
  CONFIRM_ACTIVATION: { title: "Confirm Activation", copy: "Confirm: this action cannot be undone for the selected cartridge.", style: "warning", action: "Confirm Activation", actionCopy: "Water enters the cartridge only after measurement, confirmation and all safety permissions." },
  WATER_ADMISSION: { title: "Activating Cartridge", copy: "Measured water is dissolving the dry KOH charge — please wait.", style: "active", action: "Complete Admission", actionCopy: "The reaction clock started with the real admission of water." },
  PRIME_FLOW_CHECK: { title: "Preparing the System", copy: "Flow, pressure, airflow, gas path and thermal readiness are verified (≤60 s).", style: "active", action: "Prime & Check", actionCopy: "No power permission is given during prime." },
  PRECHARGE: { title: "Connecting Power Path", copy: "Pre-charge and isolation verification before energy transfer.", style: "active", action: "Start Energy Transfer", actionCopy: "Transfer is enabled only when every safety guard is valid." },
  ACTIVE_POWER: { title: "Restoring Mobility", copy: "Delivering 10 kW to the vehicle under continuous supervision.", style: "charging", action: "Stop Transfer", actionCopy: "STOP begins a controlled ramp-down." },
  DERATED: { title: "Power Automatically Reduced", copy: "Thermal margin is narrowing; power is limited and may recover.", style: "warning", action: "Stop Transfer", actionCopy: "The event can still be ended in a controlled sequence." },
  RAMP_DOWN: { title: "Finishing Safely", copy: "Do not disconnect. Current is being reduced under control.", style: "active", action: "Isolate & Purge", actionCopy: "Contactors open after current reaches zero." },
  PURGE_COOLDOWN: { title: "Purge & Cooldown", copy: "Do not disconnect. Gas is vented and the cartridge cools.", style: "active", action: "Complete Purge", actionCopy: "The cartridge is now SPENT and keeps its products sealed." },
  SAFE_TO_DISCONNECT: { title: "Safe to Disconnect", copy: "Safe voltage verified; the connector is released. Close the cap and stow the cable and vent.", style: "ready", action: "Disconnect & Stow", actionCopy: "The system returns to standby or requests service." },
  SERVICE_REQUIRED: { title: "Service Required", copy: "All three cartridges have been used and must be replaced by service staff.", style: "fault", action: "Reset Demonstrator", actionCopy: "Reset simulates a complete cartridge swap at a service center." },
  POWER_ISOLATION: { title: "Fault — Power Isolated", copy: "The independent supervisor opened the power path; ventilation continues.", style: "fault", action: "Purge & Cooldown", actionCopy: "A wet cartridge completes purge before the lock." },
  FAULT_LOCKED: { title: "Fault Locked", copy: "Further operation is blocked pending service inspection.", style: "fault", action: "Reset Demonstrator", actionCopy: "Reset is for demonstration only and is not a real service procedure." },
};

const FAULTS = {
  E_STOP: { label: "Emergency stop pressed", value: "E-Stop" },
  HVIL_OPEN: { label: "HVIL / interlock open", value: "HVIL open", sensor: ["hvil", false] },
  ISOLATION_BLOCK: { label: "IMD below block threshold", value: "Isolation block", sensor: ["isolationKohm", 10] },
  OVERTEMPERATURE: { label: "Core overtemperature", value: "Overtemperature", sensor: ["temperature", 70] },
  HYDROGEN_ALARM: { label: "Hydrogen alarm at vent", value: "Hydrogen alarm", sensor: ["hydrogen", 40] },
  LEAK: { label: "Electrolyte leak detected", value: "Leak detected", sensor: ["leak", true] },
  ABNORMAL_PRESSURE: { label: "Abnormal reaction pressure", value: "Abnormal pressure", sensor: ["pressure", 1.8] },
  LOSS_OF_FLOW: { label: "Loss of electrolyte flow", value: "Loss of flow", sensor: ["flow", 0] },
  PUMP_FAILURE: { label: "Electrolyte pump failure", value: "Pump failure", sensor: ["pumpAvailable", false] },
  FAN_FAILURE: { label: "Blower 370 failure", value: "Blower failure", sensor: ["fanAvailable", false] },
  CONTACTOR_MISMATCH: { label: "Contactor feedback mismatch", value: "Contactor mismatch", sensor: ["contactorFeedback", false] },
};

/* Configuration 2 checks: operator-correctable conditions, not latched faults. */
const CHECKS = {
  ENCLOSED_SPACE: { label: "[4.1] Driver answers: enclosed space", state: "ENVIRONMENT_CHECK" },
  CARGO_BLOCKS_VENTS: { label: "[5.2] Cargo obstructs the vents", state: "ENVIRONMENT_CHECK" },
  VENT_SIGNAL_ONLY: { label: "[2.1] VENT_DEPLOYED without driver confirmation", state: "AWAIT_DEPLOY" },
  HVIL_WINDOW: { label: "[8.1] HVIL discontinuity in check window", state: "AWAIT_CONNECT" },
  ISOLATION_WARNING: { label: "[8.1] IMD warning threshold (indication only)", state: null },
  ISO15118_FAIL: { label: "[8.1] ISO 15118 communication fails → DIN 70121", state: "EV_HANDSHAKE" },
  RESTART_MID_FILL: { label: "[1.1] Controller restart during fill", state: "FILL_SESSION" },
  CANCEL_FILL: { label: "[1.1] Cancel before wetting", state: "FILL_SESSION" },
};

const CARTRIDGE_UI = {
  DRY_READY: ["READY", "404 g dry KOH sealed · event-ready", ""],
  SELECTED: ["SELECTED", "Isolated for this event · still dry and reversible", "is-selected"],
  ACTIVATING: ["ACTIVATING", "Water admitted · irreversible", "is-selected"],
  ACTIVE: ["ACTIVE", "Supplying the 96 V DC link", "is-active"],
  SPENT: ["SPENT", "Products retained · awaiting service", "is-spent"],
  FAULTED: ["FAULTED", "Wet and isolated · service lock", "is-faulted"],
};

const LCD_ACTIONS = {
  SYSTEM_STANDBY: "WAKE UP", SELF_TEST: "RUN SELF-TEST", ENVIRONMENT_CHECK: "OPEN AIR", AWAIT_DEPLOY: "CONFIRM VENT",
  AWAIT_CONNECT: "VERIFY LINK", EV_HANDSHAKE: "HANDSHAKE", FILL_SESSION: "POUR / CONFIRM", CONFIRM_ACTIVATION: "CONFIRM",
  WATER_ADMISSION: "CONTINUE", PRIME_FLOW_CHECK: "PRIME", PRECHARGE: "START TRANSFER", ACTIVE_POWER: "STOP TRANSFER",
  DERATED: "STOP TRANSFER", RAMP_DOWN: "ISOLATE", PURGE_COOLDOWN: "COMPLETE", SAFE_TO_DISCONNECT: "DISCONNECT",
  SERVICE_REQUIRED: "RESET DEMO", POWER_ISOLATION: "PURGE", FAULT_LOCKED: "RESET DEMO",
};

const SRC = "https://github.com/Lpro402/Conceptual_Design/blob/main/src/mpro/software_twin/";
const ARCHITECTURE_MODULES = {
  main: { code: "SW-CTRL-01", title: "Main System Controller", purpose: "Runs the Configuration 2 mission state machine and sets setpoints and permissions without owning the emergency decision.", responsibilities: ["Guarded mission-state transitions", "Operator blockers for correctable conditions", "Setpoints, permissions and operating limits"], inputs: "hmi_cmd | ev_status | reaction_status | power_status | fluid_status | safety_state", outputs: "mission_state | ev_cmd | reaction_cmd | power_cmd | fluid_cmd | log_event", safety: "The independent supervisor can override the controller and force safe outputs.", source: `${SRC}controller.py` },
  hmi: { code: "SW-HMI-01", title: "HMI Manager", purpose: "One clear message per state, including fill progress, deployment confirmation and minutes remaining.", responsibilities: ["Operator-state presentation", "Explicit confirmations (vent, activation)", "Warnings and SAFE_TO_DISCONNECT"], inputs: "mission_state | safety_state | measurements | service_state", outputs: "hmi_cmd | operator_ack | emergency_stop", safety: "The HMI cannot clear a latched fault; E-STOP goes straight to the safety path.", source: `${SRC}hmi.py` },
  safety: { code: "SW-SAFE-01", title: "Independent Safety Supervisor", purpose: "Hardware channel 620 with its own authority: GATE_DISABLE, contactor opening and FAULT_LOCK.", responsibilities: ["IMD 490 warning and block thresholds", "HVIL, E-STOP, temperature, H₂, leak, pressure, flow", "Hard trip independent of the RTOS"], inputs: "E-Stop | HVIL | IMD | temperature | H2 | leak | pressure | flow | contactor_feedback", outputs: "safety_state | gate_disable | contactor_open | fault_lock", safety: "A protocol switch never bypasses an HVIL or isolation block.", source: `${SRC}safety.py` },
  ev: { code: "SW-EV-01", title: "EV Communication Manager", purpose: "CP/PP checks and the vehicle session with ISO 15118 and DIN 70121 fallback.", responsibilities: ["CP level verification before handshake", "ISO 15118 → DIN 70121 on communication failure only", "Vehicle limits and session state"], inputs: "ev_cmd | cp_level | pp_state | plc_link", outputs: "ev_status | protocol | transfer_limits", safety: "Simulated only — no PLC/SLAC stack; invalid connection blocks transfer.", source: `${SRC}ev.py` },
  power: { code: "SW-PWR-01", title: "Power & LIC Manager", purpose: "Pre-charge, 10 kW reference, thermal-limited 12 kW Boost, derating and isolation.", responsibilities: ["Pre-charge sequencing", "Boost permission from thermal margin", "Controlled ramp-down and isolation"], inputs: "power_cmd | safety_state | voltage | current | thermal_margin", outputs: "power_status | converter_enable | contactor_commands", safety: "Safety trip disables the converter and opens both contactors.", source: `${SRC}power.py` },
  reaction: { code: "SW-REA-01", title: "Cartridge & Reaction Manager", purpose: "Three cartridges, one active; FILL_SESSION with the valve closed until measured 1.8 L and confirmation.", responsibilities: ["DRY_READY → SELECTED → ACTIVATING → ACTIVE → SPENT", "Batch filling, pause, restart and re-measure", "Cancel before wetting returns to DRY_READY"], inputs: "reaction_cmd | water_measured | flow_status | cartridge_id", outputs: "reaction_status | selected_cartridge | valve_cmd | spent_state", safety: "A wetted cartridge can never return to DRY_READY.", source: `${SRC}cartridge.py` },
  thermal: { code: "SW-TFM-01", title: "Thermal & Fluid Manager", purpose: "Pump, blowers and vent; cooling tunnel 390 over fins 380 keeps electronics in a closed compartment.", responsibilities: ["Feed-forward + PI airflow", "Boost disable 52 °C, derate 55 °C, shutdown 65 °C", "Purge and cooldown"], inputs: "fluid_cmd | temperature | flow | pressure | H2", outputs: "fluid_status | pump_cmd | blower_cmd | vent_cmd", safety: "Ventilation continues after a trip unless the blower itself failed.", source: "https://github.com/Lpro402/Conceptual_Design/blob/main/src/mpro/chemical_twin/plant.py" },
  service: { code: "SW-SVC-01", title: "Service, Logging & Storage", purpose: "Event log, cartridge usage and [9.1] storage supervision in SYSTEM_STANDBY.", responsibilities: ["Timestamped event logging", "Defined wake sources and D-BIT interval", "SERVICE_REQUIRED after three events"], inputs: "log_event | cartridge_state | lic_voltage | ambient", outputs: "service_state | event_history | dbit_interval", safety: "A service lock cannot be cleared by ordinary mission commands.", source: `${SRC}storage.py` },
  hal: { code: "SW-HAL-01", title: "Simulated HAL + Chemical Twin", purpose: "Stable boundary between the logic and the simulated plant; reaction values come from the chemical twin.", responsibilities: ["Sensor snapshot", "Actuator commands", "No real GPIO, CAN, PLC or contactor I/O"], inputs: "chemical twin plant | software actuator commands", outputs: "sensor snapshot | actuator feedback", safety: "Simulation only.", source: `${SRC}sensors.py` },
};

const ARCHITECTURE_PHASE_ORDER = ["standby", "self-test", "connect", "fill", "reaction", "transfer", "shutdown", "complete"];
const ARCHITECTURE_PHASE_BY_STATE = {
  SYSTEM_STANDBY: "standby", SELF_TEST: "self-test", ENVIRONMENT_CHECK: "self-test",
  AWAIT_DEPLOY: "connect", AWAIT_CONNECT: "connect", EV_HANDSHAKE: "connect",
  FILL_SESSION: "fill", CONFIRM_ACTIVATION: "fill", WATER_ADMISSION: "reaction", PRIME_FLOW_CHECK: "reaction",
  PRECHARGE: "transfer", ACTIVE_POWER: "transfer", DERATED: "transfer",
  RAMP_DOWN: "shutdown", PURGE_COOLDOWN: "shutdown", POWER_ISOLATION: "shutdown",
  SAFE_TO_DISCONNECT: "complete", SERVICE_REQUIRED: "complete", FAULT_LOCKED: "complete",
};

const runtime = {
  state: "SYSTEM_STANDBY", cartridges: ["DRY_READY", "DRY_READY", "DRY_READY"], selected: null,
  fault: null, blocker: null, protocol: null, waterL: 0, fillValid: true, isolationWarning: false,
  energyKwh: 0, sensors: {}, actuators: {}, log: [],
};

let transferTimer = null;
let selectedArchitectureModule = "main";
const byId = (id) => document.getElementById(id);
const queryAll = (selector) => [...document.querySelectorAll(selector)];
const approach = (value, target, rate) => value + (target - value) * Math.min(1, Math.max(0, rate));

function defaultSensors() {
  return { voltage: 0, current: 0, power: 0, temperature: 25, flow: 0, pressure: 1, hydrogen: 0,
    hvil: true, isolationKohm: 2000, leak: false, pumpAvailable: true, fanAvailable: true,
    contactorFeedback: true, ventPathClear: true };
}

function defaultActuators() {
  return { waterValve: false, pump: false, fan: false, tunnel: false, vent: false,
    inputContactor: false, outputContactor: false, converter: false, gateDisable: true };
}

function isolationLevel() {
  const ohmPerV = runtime.sensors.isolationKohm * 1000 / 400;
  if (ohmPerV < 100) return "BLOCK";
  if (ohmPerV < 500) return "WARNING";
  return "NORMAL";
}

function resetRuntime() {
  stopTransferTimer();
  Object.assign(runtime, {
    state: "SYSTEM_STANDBY", cartridges: ["DRY_READY", "DRY_READY", "DRY_READY"], selected: null,
    fault: null, blocker: null, protocol: null, waterL: 0, fillValid: true, isolationWarning: false,
    energyKwh: 0, sensors: defaultSensors(), actuators: defaultActuators(),
  });
  runtime.log = [];
  addLog("Demonstrator reset to SYSTEM_STANDBY");
  render();
}

function addLog(message, level = "INFO") {
  runtime.log.unshift({ time: new Date().toLocaleTimeString("en-GB", { hour12: false }), level, message });
  runtime.log = runtime.log.slice(0, 60);
}

function toast(message, critical = false) {
  const item = document.createElement("div");
  item.className = `toast${critical ? " is-critical" : ""}`;
  item.textContent = message;
  byId("toast-region").append(item);
  window.setTimeout(() => item.remove(), 3000);
}

function setState(state, message, level = "INFO") {
  runtime.state = state;
  runtime.blocker = null;
  if (message) addLog(`${state}: ${message}`, level);
  if (!["ACTIVE_POWER", "DERATED"].includes(state)) stopTransferTimer();
  render();
}

function block(message) {
  runtime.blocker = message;
  addLog(`${runtime.state} blocked: ${message}`, "WARNING");
  toast(message, true);
  render();
}

function remainingEvents() {
  return runtime.cartridges.filter((s) => s === "DRY_READY").length;
}

function abortBeforeWetting(reason) {
  if (runtime.selected !== null) runtime.cartridges[runtime.selected] = "DRY_READY";
  runtime.selected = null;
  runtime.waterL = 0;
  setState("SAFE_TO_DISCONNECT", `${reason}; cartridge returned to DRY_READY`);
}

function handlePrimaryAction() {
  const s = runtime.sensors;
  switch (runtime.state) {
    case "SERVICE_REQUIRED":
    case "FAULT_LOCKED":
      resetRuntime(); toast("Demonstrator reset"); return;
    case "SYSTEM_STANDBY":
      runtime.energyKwh = 0; runtime.sensors = defaultSensors(); runtime.actuators = defaultActuators();
      setState("SELF_TEST", "User wake-up"); return;
    case "SELF_TEST":
      setState("ENVIRONMENT_CHECK", "Self-test passed (temperature-compensated thresholds)"); return;
    case "ENVIRONMENT_CHECK":
      if (!s.ventPathClear) { s.ventPathClear = true; addLog("Driver cleared cargo from the vents; re-checking"); }
      setState("AWAIT_DEPLOY", "Open air confirmed; vent path clear"); return;
    case "AWAIT_DEPLOY":
      setState("AWAIT_CONNECT", "Cable, vent and driver confirmation received"); return;
    case "AWAIT_CONNECT":
      if (!s.hvil) { s.hvil = true; return block("HVIL continuity failed over the check window: connector reseated, verify again."); }
      if (isolationLevel() === "BLOCK") return block("Isolation below the block threshold: power transfer is prevented.");
      runtime.isolationWarning = isolationLevel() === "WARNING";
      if (runtime.isolationWarning) addLog("IMD warning threshold: indication only, all other conditions safe", "WARNING");
      setState("EV_HANDSHAKE", "HVIL window, CP levels and isolation verified"); return;
    case "EV_HANDSHAKE": {
      runtime.protocol = runtime.protocol === "DIN 70121" ? "DIN 70121" : "ISO 15118";
      const index = runtime.cartridges.findIndex((c) => c === "DRY_READY");
      runtime.selected = index; runtime.cartridges[index] = "SELECTED"; runtime.waterL = 0; runtime.fillValid = true;
      setState("FILL_SESSION", `${runtime.protocol} session; cartridge ${index + 1} SELECTED`); return;
    }
    case "FILL_SESSION":
      if (!runtime.fillValid) { runtime.fillValid = true; addLog(`Water re-measured: ${runtime.waterL.toFixed(1)} L`); render(); return; }
      if (runtime.waterL + 1e-9 < BASELINE.waterTargetL) {
        runtime.waterL = Math.min(BASELINE.waterTargetL, runtime.waterL + FILL_BATCH_L);
        addLog(`Received ${runtime.waterL.toFixed(1)} of 1.8 L. Missing ${(BASELINE.waterTargetL - runtime.waterL).toFixed(1)} L.`);
        render(); return;
      }
      setState("CONFIRM_ACTIVATION", "1.80 L measured; valve to cartridge still closed"); return;
    case "CONFIRM_ACTIVATION":
      runtime.cartridges[runtime.selected] = "ACTIVATING"; runtime.actuators.waterValve = true;
      setState("WATER_ADMISSION", "Irreversible: water admitted, reaction clock started"); return;
    case "WATER_ADMISSION":
      runtime.actuators.waterValve = false;
      setState("PRIME_FLOW_CHECK", "KOH dissolved to 4.0 M"); return;
    case "PRIME_FLOW_CHECK":
      Object.assign(runtime.actuators, { pump: true, fan: true, tunnel: true, vent: true });
      Object.assign(s, { flow: 2.2, voltage: 103.5, temperature: 30 });
      runtime.cartridges[runtime.selected] = "ACTIVE";
      setState("PRECHARGE", "Prime, airflow, gas path and thermal readiness within 60 s"); return;
    case "PRECHARGE":
      if (!transferGuardsSafe()) { injectFault("ISOLATION_BLOCK"); return; }
      Object.assign(runtime.actuators, { inputContactor: true, outputContactor: true, converter: true, gateDisable: false });
      setState("ACTIVE_POWER", `${runtime.protocol} DC transfer enabled at 10 kW`);
      startTransferTimer(); return;
    case "ACTIVE_POWER":
    case "DERATED":
      stopPower(); setState("RAMP_DOWN", "Operator STOP: controlled ramp-down"); return;
    case "RAMP_DOWN":
      runtime.actuators.inputContactor = false; runtime.actuators.pump = false; s.flow = 0;
      runtime.cartridges[runtime.selected] = "SPENT"; runtime.selected = null;
      setState("PURGE_COOLDOWN", "Cartridge SPENT; purge and cooldown"); return;
    case "POWER_ISOLATION":
      setState("PURGE_COOLDOWN", "Power isolated after critical fault; purge and cooldown", "CRITICAL"); return;
    case "PURGE_COOLDOWN":
      runtime.actuators.fan = false; runtime.actuators.tunnel = false; s.voltage = 0;
      if (runtime.fault) setState("FAULT_LOCKED", "Wet cartridge isolated; service required", "CRITICAL");
      else setState("SAFE_TO_DISCONNECT", "Safe voltage verified; connector released");
      return;
    case "SAFE_TO_DISCONNECT":
      runtime.actuators.vent = false; runtime.protocol = null;
      if (remainingEvents() === 0) setState("SERVICE_REQUIRED", "Three cartridges used");
      else setState("SYSTEM_STANDBY", `Stowed; ${remainingEvents()} event(s) ready`);
      return;
    default:
  }
}

function stopPower() {
  Object.assign(runtime.sensors, { current: 0, power: 0 });
  Object.assign(runtime.actuators, { converter: false, outputContactor: false, gateDisable: true });
}

function applyCheck(key) {
  const check = CHECKS[key];
  if (check.state && runtime.state !== check.state) { toast(`Available in ${check.state}`, true); return; }
  const s = runtime.sensors;
  switch (key) {
    case "ENCLOSED_SPACE": return block("Enclosed space: operation is blocked. Move the vehicle to open air.");
    case "CARGO_BLOCKS_VENTS": s.ventPathClear = false; return block("Vent path obstructed: clear cargo from the vents, then re-check.");
    case "VENT_SIGNAL_ONLY": return block("VENT_DEPLOYED alone is not enough: confirm the whole diffuser zone is outside the vehicle.");
    case "HVIL_WINDOW": s.hvil = false; return block("HVIL discontinuity detected in the check window.");
    case "ISOLATION_WARNING":
      s.isolationKohm = 150; runtime.isolationWarning = true;
      addLog("IMD warning threshold: indication, operation continues while all other conditions are safe", "WARNING");
      toast("IMD warning — indication only"); render(); return;
    case "ISO15118_FAIL":
      runtime.protocol = "DIN 70121"; addLog("ISO 15118 communication failed: DIN 70121 fallback", "WARNING");
      handlePrimaryAction(); return;
    case "RESTART_MID_FILL": runtime.fillValid = false; return block("Controller restarted: re-measure the water in chamber 220.");
    case "CANCEL_FILL": return abortBeforeWetting("Fill cancelled before wetting");
    default:
  }
}

function transferGuardsSafe() {
  const s = runtime.sensors;
  return runtime.protocol && runtime.selected !== null && s.hvil && isolationLevel() !== "BLOCK" && !s.leak
    && s.temperature < BASELINE.shutdownC && s.flow >= 0.5 && s.pumpAvailable && s.fanAvailable && s.contactorFeedback;
}

function injectFault(faultKey) {
  const fault = FAULTS[faultKey];
  if (!fault) { applyCheck(faultKey); return; }
  runtime.fault = faultKey;
  if (fault.sensor) runtime.sensors[fault.sensor[0]] = fault.sensor[1];
  safeOutputs();
  const wet = runtime.selected !== null && ["ACTIVATING", "ACTIVE"].includes(runtime.cartridges[runtime.selected]);
  if (wet) {
    runtime.cartridges[runtime.selected] = "FAULTED"; runtime.selected = null;
    setState("POWER_ISOLATION", `Safety trip: ${fault.value}; power isolated`, "CRITICAL");
  } else {
    if (runtime.selected !== null) runtime.cartridges[runtime.selected] = "DRY_READY";
    runtime.selected = null;
    setState("FAULT_LOCKED", `Safety trip before wetting: ${fault.value}`, "CRITICAL");
  }
  toast(`Injected fault: ${fault.label}`, true);
}

function safeOutputs() {
  Object.assign(runtime.sensors, { current: 0, power: 0 });
  const ventilate = runtime.sensors.fanAvailable;
  Object.assign(runtime.actuators, { waterValve: false, pump: false, inputContactor: false, outputContactor: false,
    converter: false, gateDisable: true, fan: ventilate, tunnel: ventilate, vent: true });
}

/* Simplified browser copy of the chemical-twin plant (the Python plant is the reference). */
function startTransferTimer() {
  stopTransferTimer();
  transferTimer = window.setInterval(() => {
    if (!["ACTIVE_POWER", "DERATED"].includes(runtime.state)) return;
    const s = runtime.sensors;
    const derate = s.temperature >= BASELINE.derateC ? Math.max(0.4, 1 - (s.temperature - BASELINE.derateC) / 10) : 1;
    const powerKw = BASELINE.nominalKw * derate;
    s.power = approach(s.power, powerKw, 0.5);
    s.voltage = 103.5 - 0.0711 * (s.power * 1000 / BASELINE.efficiency / 96);
    s.current = s.power * 1000 / BASELINE.efficiency / s.voltage;
    const ambientTarget = runtime.actuators.fan ? 48 : 70;
    s.temperature = approach(s.temperature, ambientTarget, SIM_SECONDS_PER_TICK / 420);
    s.hydrogen = approach(s.hydrogen, 10, 0.08);
    s.pressure = approach(s.pressure, 1.08, 0.1);
    runtime.energyKwh = Math.min(BASELINE.eventKwh, runtime.energyKwh + s.power * SIM_SECONDS_PER_TICK / 3600);
    if (runtime.state === "ACTIVE_POWER" && s.temperature >= BASELINE.derateC) setState("DERATED", "Core above 55 °C: power limited");
    if (runtime.energyKwh >= BASELINE.eventKwh) {
      stopPower(); setState("RAMP_DOWN", "3.00 kWh delivered; controlled ramp-down"); toast("Event energy delivered");
    }
    renderLiveValues();
  }, 1000);
}

function stopTransferTimer() {
  if (transferTimer !== null) window.clearInterval(transferTimer);
  transferTimer = null;
}

function stepIndex() {
  const i = STATE_ORDER.indexOf(runtime.state === "DERATED" ? "ACTIVE_POWER" : runtime.state);
  return i < 0 ? null : i;
}

function missionProgress() {
  if (["SERVICE_REQUIRED", "FAULT_LOCKED"].includes(runtime.state)) return 100;
  if (runtime.state === "POWER_ISOLATION") return 85;
  const i = stepIndex();
  return i === null ? 0 : Math.round((i / (STATE_ORDER.length - 1)) * 100);
}

function stateCopy() {
  if (runtime.blocker) return runtime.blocker;
  if (runtime.state === "FILL_SESSION") {
    return runtime.fillValid
      ? `Received ${runtime.waterL.toFixed(1)} of 1.8 L. Missing ${(BASELINE.waterTargetL - runtime.waterL).toFixed(1)} L. You may pause and continue later.`
      : "Controller restarted: re-measure the water in chamber 220.";
  }
  if (["ACTIVE_POWER", "DERATED"].includes(runtime.state) && runtime.sensors.power > 0.1) {
    const minutes = (BASELINE.eventKwh - runtime.energyKwh) / runtime.sensors.power * 60;
    return `${STATES[runtime.state].copy} About ${Math.ceil(minutes)} min remaining.`;
  }
  return STATES[runtime.state].copy;
}

function actionLabel() {
  if (runtime.state === "FILL_SESSION") {
    if (!runtime.fillValid) return "Re-measure Water";
    return runtime.waterL + 1e-9 < BASELINE.waterTargetL ? `Pour ${FILL_BATCH_L} L Batch` : "Confirm 1.8 L";
  }
  return STATES[runtime.state].action;
}

function render() {
  renderHeader(); renderMission(); renderLCD(); renderArchitecture(); renderCartridges();
  renderFlow(); renderDiagnostics(); renderService(); renderLog();
}

function renderHeader() {
  const faulted = Boolean(runtime.fault);
  byId("header-status").textContent = faulted ? "Active Fault" : STATES[runtime.state].title;
  byId("header-status").parentElement.classList.toggle("is-fault", faulted);
}

function renderMission() {
  const state = STATES[runtime.state];
  const progress = missionProgress();
  const i = stepIndex();
  byId("status-hero").className = `status-hero status-${runtime.blocker ? "warning" : state.style}`;
  byId("state-title").textContent = state.title;
  byId("state-copy").textContent = stateCopy();
  byId("progress-label").textContent = i === null ? runtime.state : `Step ${i + 1} of ${STATE_ORDER.length}`;
  byId("progress-percent").textContent = `${progress}%`;
  byId("progress-bar").style.width = `${progress}%`;
  byId("next-action-title").textContent = actionLabel();
  byId("next-action-copy").textContent = state.actionCopy;
  byId("primary-action-label").textContent = actionLabel();
  byId("primary-action").disabled = runtime.state === "ENVIRONMENT_CHECK" && runtime.blocker?.startsWith("Enclosed") === true;
  byId("remaining-events").textContent = `${remainingEvents()} of 3`;
  byId("vehicle-status").textContent = runtime.protocol ? `Connected · ${runtime.protocol}` : "Disconnected";
  byId("safety-status").textContent = runtime.fault ? "Active Fault" : runtime.isolationWarning ? "IMD Warning" : "Nominal";
  byId("safety-icon").className = `info-icon ${runtime.fault ? "info-icon--red" : "info-icon--green"}`;
  renderLiveValues();
}

function renderLiveValues() {
  const s = runtime.sensors;
  const energyPercent = Math.min(100, (runtime.energyKwh / BASELINE.eventKwh) * 100);
  byId("energy-value").textContent = runtime.energyKwh.toFixed(2);
  byId("energy-orbit").style.strokeDashoffset = String(541 - (541 * energyPercent) / 100);
  byId("power-summary").textContent = `${s.power.toFixed(1)} kW`;
  byId("sensor-voltage").textContent = s.voltage.toFixed(1);
  byId("sensor-current").textContent = s.current.toFixed(1);
  byId("sensor-temperature").textContent = s.temperature.toFixed(1);
  byId("sensor-flow").textContent = s.flow.toFixed(1);
  byId("sensor-pressure").textContent = s.pressure.toFixed(2);
  byId("sensor-hydrogen").textContent = s.hydrogen.toFixed(1);
  byId("lcd-power").textContent = s.power.toFixed(1);
  byId("lcd-energy").textContent = runtime.energyKwh.toFixed(2);
  byId("lcd-energy-bar").style.width = `${energyPercent}%`;
  byId("lcd-voltage").textContent = s.voltage.toFixed(1);
  byId("lcd-current").textContent = s.current.toFixed(1);
  byId("lcd-temperature").textContent = s.temperature.toFixed(1);
  byId("lcd-flow").textContent = s.flow.toFixed(1);
}

function renderLCD() {
  const state = STATES[runtime.state];
  const i = stepIndex();
  const live = ["ACTIVE_POWER", "DERATED"].includes(runtime.state);
  const faulted = Boolean(runtime.fault);
  const selected = runtime.selected !== null;
  byId("lcd-screen").classList.toggle("is-fault", faulted);
  byId("lcd-alert").classList.toggle("is-visible", faulted || Boolean(runtime.blocker));
  byId("lcd-alert-copy").textContent = runtime.fault ? FAULTS[runtime.fault].value : runtime.blocker || "Power path isolated";
  byId("lcd-alarm-count").textContent = faulted || runtime.blocker ? "1" : "0";
  byId("lcd-panel-status").textContent = faulted ? "SAFETY TRIP" : live ? "TRANSFER ENABLED" : runtime.blocker ? "ACTION REQUIRED" : "SYSTEM READY";
  byId("lcd-panel-status").parentElement.classList.toggle("is-fault", faulted);
  byId("lcd-state-title").textContent = state.title.toUpperCase();
  byId("lcd-state-copy").textContent = stateCopy();
  byId("lcd-progress-bar").style.width = `${missionProgress()}%`;
  byId("lcd-progress-label").textContent = faulted ? "INDEPENDENT SAFETY OVERRIDE" : i === null ? runtime.state : `STEP ${i + 1} / ${STATE_ORDER.length}`;
  byId("lcd-connection").classList.toggle("is-connected", Boolean(runtime.protocol));
  byId("lcd-vehicle-status").textContent = runtime.protocol ? runtime.protocol.toUpperCase() : "DISCONNECTED";
  const s = runtime.sensors;
  const permissives = {
    "lcd-permissive-hvil": s.hvil, "lcd-permissive-iso": isolationLevel() !== "BLOCK",
    "lcd-permissive-flow": !live || s.flow >= 0.5, "lcd-permissive-thermal": s.temperature < BASELINE.shutdownC,
  };
  Object.entries(permissives).forEach(([id, valid]) => {
    byId(id).classList.toggle("is-valid", valid);
    byId(id).classList.toggle("is-fault", !valid);
  });
  const a = runtime.actuators;
  const actuatorStates = {
    "lcd-pump-status": [a.pump, "RUN", "STOP"], "lcd-fan-status": [a.fan, "RUN", "STOP"],
    "lcd-input-status": [a.inputContactor, "CLOSED", "OPEN"], "lcd-output-status": [a.outputContactor, "CLOSED", "OPEN"],
  };
  Object.entries(actuatorStates).forEach(([id, [active, on, off]]) => {
    byId(id).textContent = active ? on : off;
    byId(id).classList.toggle("is-run", active);
  });
  const trendPath = faulted
    ? "M0 75 L22 72 L45 58 L70 38 L96 29 L125 25 L158 24 L193 24 L226 23 L260 23 L297 24 L330 24 L350 31 L370 67 L395 79 L420 80"
    : live ? "M0 75 L22 72 L45 58 L70 38 L96 29 L125 25 L158 24 L193 24 L226 23 L260 23 L297 24 L333 23 L370 23 L420 23" : "M0 80 L420 80";
  byId("lcd-trend-line").setAttribute("d", trendPath);
  byId("lcd-trend-line").classList.toggle("is-fault", faulted);
  byId("lcd-primary-label").textContent = runtime.state === "FILL_SESSION" ? actionLabel().toUpperCase() : LCD_ACTIONS[runtime.state];
  byId("lcd-primary-action").classList.toggle("is-stop", live);
  const nodes = {
    cassette: selected || runtime.cartridges.some((c) => c !== "DRY_READY"),
    stack: ["PRIME_FLOW_CHECK", "PRECHARGE", "ACTIVE_POWER", "DERATED", "RAMP_DOWN", "PURGE_COOLDOWN"].includes(runtime.state),
    converter: live, vehicle: Boolean(runtime.protocol),
  };
  byId("lcd-energy-path").classList.toggle("is-live", live);
  Object.entries(nodes).forEach(([name, active]) => document.querySelector(`[data-lcd-flow="${name}"]`).classList.toggle("is-active", active));
  byId("lcd-cartridge-state").textContent = faulted ? "FAULTED" : selected ? `C${runtime.selected + 1} ${runtime.cartridges[runtime.selected]}` : "READY";
  byId("lcd-stack-state").textContent = a.pump ? "REACTION" : "IDLE";
  byId("lcd-converter-state").textContent = a.converter ? "ACTIVE" : "ISOLATED";
  byId("lcd-ev-state").textContent = runtime.protocol ? "ONLINE" : "OFFLINE";
  byId("lcd-cassette-summary").innerHTML = runtime.cartridges.map((c, index) => {
    const css = { DRY_READY: "is-ready", SELECTED: "is-active", ACTIVATING: "is-active", ACTIVE: "is-active", SPENT: "is-spent", FAULTED: "is-fault" }[c];
    return `<span class="lcd-mini-cassette ${css}" title="Cartridge ${index + 1}: ${c}">C${index + 1}</span>`;
  }).join("");
  renderLiveValues();
}

function updateLCDClock() {
  byId("lcd-clock").textContent = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function architectureActiveModules() {
  const active = new Set(["main", "hmi", "safety", "service", "hal"]);
  const st = runtime.state;
  if (runtime.protocol || ["AWAIT_CONNECT", "EV_HANDSHAKE"].includes(st)) active.add("ev");
  if (runtime.selected !== null || ["FILL_SESSION", "CONFIRM_ACTIVATION", "WATER_ADMISSION", "PRIME_FLOW_CHECK"].includes(st)) active.add("reaction");
  if (["PRECHARGE", "ACTIVE_POWER", "DERATED", "RAMP_DOWN"].includes(st)) active.add("power");
  if (["WATER_ADMISSION", "PRIME_FLOW_CHECK", "PRECHARGE", "ACTIVE_POWER", "DERATED", "RAMP_DOWN", "PURGE_COOLDOWN", "POWER_ISOLATION"].includes(st)) active.add("thermal");
  return active;
}

function architectureModuleStatus(name, active) {
  if (name === "safety") return runtime.fault ? "TRIPPED" : runtime.isolationWarning ? "IMD WARN" : "ARMED";
  if (name === "main") return runtime.fault ? "OVERRIDDEN" : runtime.blocker ? "BLOCKED" : "ACTIVE";
  if (name === "hmi") return "MONITOR";
  if (name === "hal") return "ONLINE";
  if (name === "service") return runtime.state === "SERVICE_REQUIRED" ? "LOCKOUT" : runtime.state === "SYSTEM_STANDBY" ? "SLEEP" : "LOGGING";
  if (name === "ev" && runtime.protocol) return runtime.protocol === "DIN 70121" ? "DIN 70121" : "ISO 15118";
  if (name === "reaction" && runtime.selected !== null) return `C${runtime.selected + 1} ${runtime.cartridges[runtime.selected]}`;
  if (name === "power" && ["ACTIVE_POWER", "DERATED"].includes(runtime.state)) return "TRANSFER";
  if (name === "thermal" && (runtime.actuators.pump || runtime.actuators.fan)) return "RUNNING";
  return active ? "ACTIVE" : "STANDBY";
}

function renderArchitecture() {
  const faulted = Boolean(runtime.fault);
  const activeModules = architectureActiveModules();
  byId("architecture-runtime-state").textContent = runtime.state;
  byId("architecture-runtime-state").closest(".architecture-runtime-badge").classList.toggle("is-fault", faulted);
  queryAll(".architecture-module").forEach((el) => {
    const name = el.dataset.architectureModule;
    const active = activeModules.has(name);
    el.classList.toggle("is-active", active);
    el.classList.toggle("is-alert", faulted && name === "safety");
    el.classList.toggle("is-selected", name === selectedArchitectureModule);
    el.querySelector(".module-live").textContent = architectureModuleStatus(name, active);
  });
  const current = ARCHITECTURE_PHASE_ORDER.indexOf(ARCHITECTURE_PHASE_BY_STATE[runtime.state] || "standby");
  queryAll("[data-architecture-phase]").forEach((el) => {
    const i = ARCHITECTURE_PHASE_ORDER.indexOf(el.dataset.architecturePhase);
    el.classList.toggle("is-complete", !faulted && i < current);
    el.classList.toggle("is-current", !faulted && i === current);
    el.classList.toggle("is-fault", faulted && i === current);
  });
  const m = ARCHITECTURE_MODULES[selectedArchitectureModule];
  byId("architecture-detail-code").textContent = m.code;
  byId("architecture-detail-title").textContent = m.title;
  byId("architecture-detail-purpose").textContent = m.purpose;
  byId("architecture-detail-responsibilities").innerHTML = m.responsibilities.map((r) => `<li>${r}</li>`).join("");
  byId("architecture-detail-inputs").textContent = m.inputs;
  byId("architecture-detail-outputs").textContent = m.outputs;
  byId("architecture-detail-safety").textContent = m.safety;
  byId("architecture-source-link").href = m.source;
  byId("architecture-detail-runtime").textContent = architectureModuleStatus(selectedArchitectureModule, activeModules.has(selectedArchitectureModule));
  byId("architecture-detail-runtime").parentElement.classList.toggle("is-alert", selectedArchitectureModule === "safety" && faulted);
}

function renderCartridges() {
  byId("cassette-grid").innerHTML = runtime.cartridges.map((state, index) => {
    const [label, description, css] = CARTRIDGE_UI[state];
    return `<article class="cassette-card ${css}">
      <div class="cassette-top"><span class="cassette-number">CARTRIDGE ${index + 1}</span><span class="cassette-state">${label}</span></div>
      <h3>Al-Air Cartridge · 3 kWh</h3><p>${description}</p></article>`;
  }).join("");
}

function renderFlow() {
  const live = ["ACTIVE_POWER", "DERATED"].includes(runtime.state);
  const selected = runtime.selected !== null;
  const nodes = {
    cassette: selected || runtime.cartridges.some((c) => c !== "DRY_READY"),
    stack: ["PRIME_FLOW_CHECK", "PRECHARGE", "ACTIVE_POWER", "DERATED", "RAMP_DOWN", "PURGE_COOLDOWN"].includes(runtime.state),
    converter: live, vehicle: Boolean(runtime.protocol),
  };
  byId("system-flow").classList.toggle("is-live", live);
  Object.entries(nodes).forEach(([name, active]) => document.querySelector(`[data-flow="${name}"]`).classList.toggle("is-active", active));
  byId("flow-cassette").textContent = selected ? `Cartridge ${runtime.selected + 1}` : "Waiting";
  byId("flow-stack").textContent = runtime.actuators.pump ? "Reaction Active" : "Inactive";
  byId("flow-converter").textContent = runtime.actuators.converter ? "Converter Active" : "Isolated";
  byId("flow-vehicle").textContent = runtime.protocol ? runtime.protocol : "Disconnected";
  byId("flow-chip").classList.toggle("is-live", live);
  byId("flow-chip").lastChild.textContent = live ? " TRANSFER ACTIVE" : " STANDBY";
}

function renderDiagnostics() {
  const s = runtime.sensors;
  const iso = isolationLevel();
  const chain = [
    ["HVIL / Interlock", s.hvil ? "NOMINAL" : "FAULT"],
    ["IMD 490 Isolation", iso === "NORMAL" ? "NOMINAL" : iso],
    ["Leak Detection", s.leak ? "FAULT" : "NOMINAL"],
    ["Contactor Feedback", s.contactorFeedback ? "NOMINAL" : "FAULT"],
    ["Hydrogen at Vent", s.hydrogen < 25 ? "NOMINAL" : "FAULT"],
    ["Vent Path (5.2)", s.ventPathClear ? "NOMINAL" : "BLOCKED"],
  ];
  byId("safety-chain").innerHTML = chain.map(([name, status]) =>
    `<div class="chain-row"><span>${name}</span><span class="chain-status${status === "NOMINAL" ? "" : " is-fault"}">${status}</span></div>`).join("");
  const a = runtime.actuators;
  const actuators = [
    ["Water Valve → Cartridge", a.waterValve], ["Electrolyte Pump", a.pump], ["Process Blower", a.fan],
    ["Tunnel 390 Blower 370", a.tunnel], ["External Vent", a.vent], ["Input Contactor", a.inputContactor],
    ["Output Contactor", a.outputContactor], ["DC/DC Converter", a.converter], ["Gate Disable", a.gateDisable],
  ];
  byId("actuator-list").innerHTML = actuators.map(([name, active]) =>
    `<div class="actuator-row"><span>${name}</span><span class="actuator-status ${active ? "is-active" : ""}">${active ? "ON" : "OFF"}</span></div>`).join("");
}

function renderService() {
  const remaining = remainingEvents();
  const score = Math.round((remaining / 3) * 100);
  const serviceRequired = runtime.state === "SERVICE_REQUIRED" || Boolean(runtime.fault);
  byId("readiness-ring").style.setProperty("--score", `${score}%`);
  byId("readiness-score").textContent = String(score);
  byId("readiness-title").textContent = serviceRequired ? "System Requires Service" : "System Ready";
  byId("readiness-copy").textContent = serviceRequired ? "A professional inspection is required before another rescue event." : `${remaining} cartridges are available for rescue events.`;
  byId("service-readiness").textContent = serviceRequired ? "Service Required" : "Ready";
  byId("service-self-test").textContent = runtime.state === "SYSTEM_STANDBY" ? "Scheduled D-BIT in storage" : "PASS — temperature-compensated";
  byId("service-capacity").textContent = `${remaining} rescue events available`;
}

function renderLog() {
  const log = byId("event-log");
  if (!runtime.log.length) { log.innerHTML = "<li><span></span><span></span><span>No events to display</span></li>"; return; }
  log.innerHTML = runtime.log.map((r) => `<li><time>${r.time}</time><span class="log-level${r.level === "CRITICAL" ? " is-critical" : ""}">${r.level}</span><span>${r.message}</span></li>`).join("");
}

function selectView(viewName) {
  queryAll(".view-tab").forEach((b) => b.classList.toggle("is-active", b.dataset.view === viewName));
  queryAll(".view-panel").forEach((p) => p.classList.toggle("is-active", p.id === `view-${viewName}`));
  document.body.classList.toggle("lcd-standalone", viewName === "lcd" && new URLSearchParams(window.location.search).get("view") === "lcd");
}

function initializeFaultSelect() {
  const checks = Object.entries(CHECKS).map(([k, c]) => `<option value="${k}">${c.label}</option>`).join("");
  const faults = Object.entries(FAULTS).map(([k, f]) => `<option value="${k}">${f.label}</option>`).join("");
  byId("fault-select").innerHTML = `<optgroup label="Configuration 2 checks">${checks}</optgroup><optgroup label="Critical faults (latched)">${faults}</optgroup>`;
}

function initializeShowcaseScenario() {
  if (new URLSearchParams(window.location.search).get("scenario") !== "charging") return false;
  Object.assign(runtime, { state: "ACTIVE_POWER", cartridges: ["ACTIVE", "DRY_READY", "DRY_READY"], selected: 0, protocol: "ISO 15118", energyKwh: 1.38 });
  runtime.sensors = defaultSensors();
  Object.assign(runtime.sensors, { power: 10, voltage: 95.4, current: 113.9, temperature: 43.8, flow: 2.2, pressure: 1.08, hydrogen: 9.6 });
  runtime.actuators = defaultActuators();
  Object.assign(runtime.actuators, { pump: true, fan: true, tunnel: true, vent: true, inputContactor: true, outputContactor: true, converter: true, gateDisable: false });
  addLog("ACTIVE_POWER: Presentation scenario loaded");
  startTransferTimer();
  return true;
}

function initializeRequestedView() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view");
  if (!["mission", "lcd", "architecture", "diagnostics", "service"].includes(view)) return;
  selectView(view);
  document.body.classList.toggle("lcd-standalone", view === "lcd");
  document.body.classList.toggle("architecture-capture", view === "architecture" && params.get("capture") === "architecture");
}

queryAll(".view-tab").forEach((b) => b.addEventListener("click", () => selectView(b.dataset.view)));
queryAll(".architecture-module").forEach((b) => b.addEventListener("click", () => { selectedArchitectureModule = b.dataset.architectureModule; renderArchitecture(); }));
byId("primary-action").addEventListener("click", handlePrimaryAction);
byId("emergency-action").addEventListener("click", () => injectFault("E_STOP"));
byId("lcd-primary-action").addEventListener("click", handlePrimaryAction);
byId("lcd-emergency-action").addEventListener("click", () => injectFault("E_STOP"));
byId("lcd-diagnostics-link").addEventListener("click", () => selectView("diagnostics"));
byId("lcd-service-link").addEventListener("click", () => selectView("service"));
byId("inject-fault").addEventListener("click", () => injectFault(byId("fault-select").value));
byId("diagnostics-reset").addEventListener("click", () => resetRuntime());
byId("clear-log").addEventListener("click", () => { runtime.log = []; renderLog(); toast("Event log cleared"); });

initializeFaultSelect();
runtime.sensors = defaultSensors();
runtime.actuators = defaultActuators();
if (!initializeShowcaseScenario()) addLog("System in SYSTEM_STANDBY — Configuration 2 software twin");
updateLCDClock();
window.setInterval(updateLCDClock, 1000);
render();
initializeRequestedView();
